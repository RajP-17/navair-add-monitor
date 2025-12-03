# Laser Array Calibration System - Main Dashboard Integration

## Summary
Successfully integrated the calibration-based laser monitoring system from `voltages.html` into the main NAVAIR dashboard (`index.html`). The system now uses per-sensor baseline ranges instead of global thresholds.

## What Was Changed

### 1. HTML Dashboard (index.html)
**Location**: Lines 812-887

**Added Components**:
- **Calibration Panel**: Blue gradient panel with Start/Reset buttons
- **Updated Summary Stats**: Changed from "Active/Inactive" to "Clear/Partial/Blocked" counts
- **New Labels**: Shows sensors by calibration status instead of ADC thresholds
- **Legend**: Updated to show Green (Clear), Orange (Partial), Red (Blocked), Gray (Not Calibrated)

**Removed Components**:
- Sample averaging controls (functionality kept in JavaScript)
- Old "Active/Inactive" threshold display

### 2. JavaScript (dashboard.js)

#### Added to Constructor (Lines 69-75):
```javascript
this.laserBaselines = {}; // Per-sensor min/max ranges
this.isLaserCalibrating = false;
this.laserCalibrationStartTime = null;
this.LASER_CALIBRATION_DURATION = 10000; // 10 seconds
this.BLOCKED_THRESHOLD_MV = 25; // >25mV below min = blocked
this.PARTIAL_THRESHOLD_MV = 10; // >10mV below min = partial
```

#### New Methods Added (Lines 1646-1744):

1. **startLaserCalibration()**
   - Initiates 10-second calibration period
   - Clears existing baselines
   - Updates UI to show calibration in progress
   - Auto-stops after 10 seconds

2. **stopLaserCalibration()**
   - Ends calibration period
   - Updates UI with calibration results
   - Shows count of calibrated sensors

3. **resetLaserCalibration()**
   - Clears all stored baselines
   - Resets calibration status

4. **getLaserSensorStatus(voltage, sensorNum, baseline)**
   - Determines sensor status: clear/partial/blocked/not-calibrated
   - Digital sensors (27-30): Uses 0-5V thresholds
   - Analog sensors: Compares to individual baseline min
     - CLEAR: < 10mV below baseline min
     - PARTIAL: 10-25mV below baseline min
     - BLOCKED: > 25mV below baseline min

#### Updated fetchLaserArrayData() Method (Lines 1519-1683):

**Calibration Logic**:
- During calibration: Records min/max voltage for each sensor
- Updates countdown timer during calibration
- Each sensor gets its own baseline range

**Rendering Logic**:
- Color codes sensors based on calibration status:
  - **Green (#27ae60)**: Clear (within range)
  - **Orange (#f39c12)**: Partial (10-25mV low)
  - **Red (#e74c3c)**: Blocked (>25mV low)
  - **Gray (#95a5a6)**: Not calibrated

**Display Updates**:
- Shows current voltage in mV
- Shows drop below baseline min (Δ25mV format)
- Tooltip shows baseline range and current status
- Summary shows clear/partial/blocked counts

## How To Use

### Step 1: Open Dashboard
Navigate to http://localhost:8000 (main dashboard port)

### Step 2: Prepare for Calibration
1. Close the 3D printer door
2. Ensure all lasers are powered on
3. Wait for readings to stabilize (~5-10 seconds)

### Step 3: Run Calibration
1. Click "Start Calibration (10s)" button in the blue calibration panel
2. Keep door closed and don't move anything for 10 seconds
3. System records min/max voltage for each sensor during this period
4. Button shows countdown: "Calibrating... 9s", "8s", etc.
5. After 10 seconds, status shows "Calibrated! 36 sensors with baseline ranges recorded"

### Step 4: Monitor Sensors
- **Green sensors**: Operating normally (within 10mV of baseline)
- **Orange sensors**: Slight reduction (10-25mV below baseline)
- **Red sensors**: Significantly blocked (>25mV below baseline)
- **Gray sensors**: Not calibrated yet

### Step 5: Reset If Needed
Click "Reset" button to clear all baselines and recalibrate

## Threshold Details

### Analog Laser Sensors (1-26, 31-36)

Each sensor is compared to its OWN baseline minimum:

| Status | Condition | Color | Meaning |
|--------|-----------|-------|---------|
| CLEAR | < 10mV below min | Green | Normal operation |
| PARTIAL | 10-25mV below min | Orange | Slight blockage/warning |
| BLOCKED | > 25mV below min | Red | Significant blockage |
| NOT CALIBRATED | No baseline | Gray | Need to calibrate |

### Digital Door Sensors (27-30)

Fixed thresholds (not calibration-based):

| Status | Voltage | Meaning |
|--------|---------|---------|
| CLEAR | > 4.0V | Door closed (HIGH) |
| PARTIAL | 1.0-4.0V | Transition |
| BLOCKED | < 1.0V | Door open (LOW) |

## Display Format

### Sensor Box Shows:
```
#1          ← Sensor number
A-A10       ← Arduino pin mapping
350mV       ← Current voltage
Δ5mV        ← Drop below baseline min
```

### Tooltip Shows:
```
Laser 1 (Pin: A-A10)
Status: CLEAR
Current: 350.2mV
Baseline: 345.0 - 355.0mV
Drop below min: 5.0mV
```

### Summary Panel Shows:
```
Status: Calibrated (36/36)
Clear (<10mV low): 34
Partial (10-25mV): 2
Blocked (>25mV): 0
Avg Voltage: 320 mV
```

## Benefits Over Previous System

| Old System | New System |
|------------|------------|
| Single global threshold (ADC > 100) | Per-sensor baseline ranges |
| All sensors same threshold | Each sensor has own min/max |
| Binary active/inactive | 4 states: clear/partial/blocked/not-calibrated |
| No accounting for sensor variation | Adapts to each sensor's characteristics |
| False positives from low-reading sensors | Only triggers on significant drops |

## Example Scenarios

### Scenario 1: Clean Operation
- **Sensor 1 baseline**: 520-550mV, Current: 540mV → **GREEN** (within range)
- **Sensor 35 baseline**: 260-280mV, Current: 270mV → **GREEN** (within range)

Even though Sensor 1 reads higher voltage, both are green because they're within their own baselines!

### Scenario 2: Partial Blockage
- **Sensor 10 baseline**: 300-330mV, Current: 285mV → **ORANGE** (15mV below min)

### Scenario 3: Full Blockage
- **Sensor 5 baseline**: 310-340mV, Current: 280mV → **RED** (30mV below min)

## Files Modified

1. `/home/navair/Desktop/navair-add-monitor/Navair_Project/navair_additive/web_dashboard/index.html`
   - Lines 812-887: Replaced laser array section with calibration-enabled version

2. `/home/navair/Desktop/navair-add-monitor/Navair_Project/navair_additive/web_dashboard/dashboard.js`
   - Lines 69-75: Added calibration state variables
   - Lines 1646-1744: Added calibration methods
   - Lines 1519-1683: Updated fetchLaserArrayData() with calibration logic

3. `/home/navair/Desktop/navair-add-monitor/Navair_Project/navair_additive/web_dashboard/voltages.html`
   - Already had calibration system (this was the source)
   - Remains available on port 5001 as standalone laser monitor

## Calibration Data Storage

- **Location**: JavaScript variable `dashboard.laserBaselines`
- **Format**: `{ sensorNum: { min: 0.310, max: 0.340 } }`
- **Persistence**: Lost on page refresh (intentional - requires fresh calibration)
- **Future Enhancement**: Could save to localStorage for persistence across sessions

## Testing Recommendations

1. **Initial Test**: Calibrate with door closed, then open door - should see sensors turn red
2. **Hand Test**: Wave hand through individual lasers - should see those sensors turn orange/red
3. **Variation Test**: Check that different sensors have different baseline ranges (proves per-sensor tracking)
4. **Reset Test**: Click Reset, verify all sensors turn gray until recalibrated

## Technical Notes

- Calibration runs for exactly 10 seconds (10000ms)
- Min/max values update every data fetch during calibration (~every 3 seconds)
- Uses existing 5-sample voltage averaging from original system
- Thresholds: 10mV (partial) and 25mV (blocked) are configurable in constructor
- Digital door sensors (27-30) use fixed thresholds, not calibration

## Next Steps (Optional Enhancements)

1. **Persist Calibration**: Save baselines to localStorage
2. **Auto-Calibration**: Trigger calibration on print start
3. **Calibration History**: Track calibration timestamps
4. **Per-Sensor Threshold**: Allow custom thresholds for specific sensors
5. **Trend Analysis**: Graph sensor voltage over time
6. **Alert Integration**: Trigger alerts when sensors go to BLOCKED status
