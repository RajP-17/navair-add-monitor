# Laser Beam Breaker Defect Detection System

## Overview

This system implements real-time FDM print defect detection using a 36-laser beam breaker array that monitors print quality by comparing expected build volume (from G-code) with actual material position (from laser breaks).

## How It Works

### Hardware Setup
- **36 Infrared Laser Beams** arranged along the Y-axis of the Ultimaker S5 printer
- **Beam Spacing**: ~9.17mm (330mm / 36 sensors)
- **Coverage**: Full Y-axis range (0-330mm)
- **Z-Axis Activation**: Lasers become active when bed drops below Z=25mm (15mm into the print)

### Detection Principle

1. **G-code Parsing**: When a print starts, the system parses the G-code file to extract the expected build volume at each layer height.

2. **Real-time Monitoring**: As the print progresses and the bed descends:
   - Lasers inside the expected build volume SHOULD be broken (blocked by the print)
   - Lasers outside the expected build volume SHOULD be unbroken (clear)

3. **Anomaly Detection**: If a laser **outside** the expected volume breaks → defect detected:
   - Material extending beyond expected boundaries
   - Possible warping, over-extrusion, layer shift, or stringing

4. **Persistence Tracking**: System waits for anomalies to persist across multiple layers (default: 3 layers) before flagging as a real defect, filtering out temporary issues like stringing.

## System Architecture

###  Components

1. **LaserDefectDetector** (`/monitoring/laser_defect_detector.py`)
   - Core defect detection logic
   - Tracks 36 laser states
   - Compares against expected build volume
   - Classifies defect types (warping, over-extrusion, layer shift, stringing)
   - Calculates severity levels (low, medium, high, critical)

2. **LaserArrayHandler** (`/sensors/laser_array_handler.py`)
   - Communicates with Arduino controllers via serial
   - Reads laser beam states from hardware
   - Integrates LaserDefectDetector
   - Provides `set_gcode_geometry()` method for G-code integration

3. **GCodeParser** (`/monitoring/gcode_parser.py`)
   - Parses G-code files to extract layer geometries
   - Calculates build volume boundaries at each Z height
   - Provides expected vs actual position comparison

4. **PrintJobMonitor** (`/monitoring/print_job_monitor.py`)
   - Tracks print job lifecycle
   - Fetches G-code when new job starts
   - Coordinates between printer API, G-code parser, and laser array

## Data Flow

```
Print Job Starts
       ↓
PrintJobMonitor detects new job
       ↓
Fetch G-code from printer/file
       ↓
GCodeParser extracts layer geometries
       ↓
PrintJobMonitor.set_gcode_geometry() → LaserArrayHandler.set_gcode_geometry()
       ↓
During Print:
   Printer Position Updates (Z, Layer#) → LaserArrayHandler.update_printer_position()
   Laser States (36 beams) → LaserArrayHandler reads from Arduino
       ↓
   LaserDefectDetector.update_laser_states(laser_readings)
   LaserDefectDetector.check_for_defects(expected_y_min, expected_y_max, layer_number)
       ↓
   If anomaly persists → DefectRecord created
       ↓
   Defects logged to database and alerts triggered
```

## Defect Types

### 1. Warping
- **Pattern**: Edge lasers (0 or 35) consistently broken
- **Cause**: Print edges curling up beyond expected boundaries
- **Example**: Lasers 0-2 broken when they should be clear

### 2. Over-Extrusion
- **Pattern**: Continuous band of lasers broken beyond expected volume
- **Cause**: Too much material being deposited
- **Example**: Lasers 15-20 broken when build volume ends at laser 18

### 3. Layer Shift
- **Pattern**: Non-continuous laser breaks in unexpected locations
- **Cause**: Print head shifted during layer
- **Example**: Lasers 5, 10, 15 broken in non-contiguous pattern

### 4. Stringing
- **Pattern**: 1-2 isolated lasers temporarily broken
- **Cause**: Material oozing/stringing between print areas
- **Example**: Single laser 12 broken for 1-2 layers

## Severity Levels

Severity is calculated based on:
- **Persistence**: Number of times defect has been observed
- **Extent**: Number of lasers affected

| Severity | Criteria | Action |
|----------|----------|--------|
| LOW | 1-4 occurrences, 1-2 lasers | Monitor |
| MEDIUM | 5-9 occurrences, 3-5 lasers | Log warning |
| HIGH | 10-14 occurrences, 6-10 lasers | Alert operator |
| CRITICAL | 15+ occurrences or 10+ lasers | Consider stopping print |

## Configuration Parameters

### LaserDefectDetector
```python
LaserDefectDetector(
    num_lasers=36,                    # Number of lasers in array
    y_min=0.0,                       # Minimum Y coordinate
    y_max=330.0,                     # Maximum Y coordinate (Ultimaker S5)
    laser_monitoring_start_z=25.0,   # Z height when monitoring activates
    persistence_threshold=3,          # Layers before flagging persistent defect
    defect_threshold_mm=2.0          # Acceptable deviation in mm
)
```

### Integration Points

**In PrintJobMonitor:**
```python
# When job starts and G-code is parsed
if self.laser_array_handler:
    self.laser_array_handler.set_gcode_geometry(self.current_gcode_geometry)
```

**In Main Application:**
```python
# Update printer position during print
if printer_position_data:
    laser_array_handler.update_printer_position([x, y, z])
```

## API Endpoints

### Get Defect Status
```bash
GET /api/sensors/laser_array/defects
```

Returns:
```json
{
  "total_active_defects": 2,
  "defects_by_type": {
    "warping": 1,
    "over_extrusion": 1
  },
  "defects_by_severity": {
    "high": 1,
    "medium": 1
  },
  "current_layer": 45,
  "current_z_height": 9.0,
  "monitoring_active": true
}
```

### Get Active Defects
```bash
GET /api/sensors/laser_array/defects/active
```

Returns detailed list of all active defect records.

## Database Schema

Defects are stored in the `print_defects` table:
```sql
CREATE TABLE print_defects (
    id SERIAL PRIMARY KEY,
    print_job_id VARCHAR(255),
    defect_type VARCHAR(50),
    severity VARCHAR(20),
    layer_number INT,
    z_height FLOAT,
    laser_ids_affected INT[],
    y_positions_affected FLOAT[],
    first_detected TIMESTAMP,
    last_detected TIMESTAMP,
    occurrence_count INT,
    description TEXT,
    metadata JSONB
);
```

## Testing

### Unit Tests
```bash
pytest tests/monitoring/test_laser_defect_detector.py
```

### Integration Tests
```bash
pytest tests/integration/test_defect_detection_workflow.py
```

### Manual Testing
1. Start a print job
2. Monitor logs for "G-code geometry loaded" message
3. Watch for "Monitoring active" when Z > 25mm
4. Trigger artificial defect by placing object in laser path
5. Verify defect is detected and logged after 3 layers

## Troubleshooting

### "Monitoring not active" even during print
- Check Z height: Must be >= 25mm for lasers to see print
- Verify printer position is being updated
- Check G-code was successfully parsed

### False positives (defects detected when print is good)
- Increase `persistence_threshold` (default: 3 layers)
- Increase `defect_threshold_mm` (default: 2.0mm)
- Check laser calibration

### Defects not detected
- Verify lasers are aligned with print area
- Check Arduino communication is working
- Confirm G-code boundaries are correct

## Future Enhancements

1. **ML-based Classification**: Train model to distinguish defect types more accurately
2. **Predictive Alerts**: Predict failure before it happens based on trends
3. **Automatic Print Stopping**: Integration with printer to pause/stop on critical defects
4. **3D Visualization**: Real-time 3D view showing expected vs actual build volume
5. **Per-Object Tracking**: Track defects for specific objects in multi-object prints

## Related Files

- `/monitoring/laser_defect_detector.py` - Core detection logic
- `/sensors/laser_array_handler.py` - Hardware interface with defect integration
- `/monitoring/gcode_parser.py` - G-code parsing and geometry extraction
- `/monitoring/print_job_monitor.py` - Print job lifecycle management
- `/main.py` - System initialization and integration

## References

- Ultimaker S5 API Documentation
- G-code Specification
- Arduino Mega 2560 Serial Protocol
