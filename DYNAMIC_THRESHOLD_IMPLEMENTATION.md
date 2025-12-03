# Dynamic Per-Sensor Threshold Implementation

## Summary
Updated the voltage display dashboard (port 5001) to use **per-sensor dynamic thresholds** where each sensor is evaluated against its own peak voltage, not a global threshold.

## Calibration Data Collected

### Door OPEN (Lasers Blocked) - Baseline
- **Analog Sensors (32 sensors):**
  - Voltage Range: 50 - 350 mV
  - Average: 95 mV
  - Most sensors: 50-120 mV

- **Digital Door Sensors (4 sensors: 27-30):**
  - All reading: 0.000V (LOW = door open)

### Door CLOSED (Lasers Active/Unblocked)
- **Analog Sensors (32 sensors):**
  - Voltage Range: 240 - 550 mV
  - Average: 322 mV
  - Most sensors: 290-370 mV

- **Digital Door Sensors:**
  - Sensors 28, 29, 30: 5.000V (HIGH = door closed)
  - Sensor 27: 0.000V (may be different type)

## Implementation Details

### Per-Sensor Threshold Logic

Each analog laser sensor (1-26, 31-36) now:
1. **Tracks its own peak voltage** in the `sensorMaxVoltages` object
2. **Compares current reading to its own peak** (not to other sensors)
3. **Calculates voltage drop** = peak - current

### Status Classification

For **Analog Laser Sensors**:
- **CLEAR**: Voltage drop < 15mV from sensor's own peak
- **PARTIAL**: Voltage drop 15-30mV from sensor's own peak
- **BLOCKED**: Voltage drop > 30mV from sensor's own peak

For **Digital Door Sensors** (27-30):
- **DOOR CLOSED**: Voltage > 4.0V
- **PARTIAL**: Voltage 1.0-4.0V
- **DOOR OPEN**: Voltage < 1.0V

## Key Benefits

1. **Adaptive to Each Sensor**: Accounts for natural variations between sensors
2. **No False Positives**: Sensor 1 (peaks at 550mV) won't trigger the same threshold as Sensor 35 (peaks at 270mV)
3. **Real-time Learning**: Each sensor's peak updates automatically as higher voltages are detected
4. **Relative Detection**: Detects blockage based on change from baseline, not absolute values

## Display Features

Each sensor card now shows:
- **Current**: Current voltage in mV
- **Peak**: Highest voltage seen for THIS sensor
- **Drop**: How many mV this sensor dropped from its own peak

Example:
```
Sensor 1: 0.520V
Current: 520mV | Peak: 550mV | Drop: 30mV
Status: BLOCKED (dropped exactly 30mV)
```

```
Sensor 35: 0.270V
Current: 270mV | Peak: 270mV | Drop: 0mV
Status: CLEAR (at its own peak)
```

## Summary Statistics

Dashboard header shows count of sensors in each category:
- **Clear (<15mV drop)**: Sensors within 15mV of their own peaks
- **Partial (15-30mV drop)**: Sensors showing some voltage reduction
- **Blocked (>30mV drop)**: Sensors dropped >30mV from their own peak

## Files Modified

- `/home/navair/Desktop/navair-add-monitor/Navair_Project/navair_additive/web_dashboard/voltages.html`
  - Lines 233-282: Added per-sensor tracking and status functions
  - Lines 318-361: Track individual sensor peaks and calculate counts
  - Lines 375-397: Display peak, current, and drop values
  - Lines 212-221: Updated summary labels

## Testing

### To test the dynamic thresholds:

1. **Start with door OPEN** (all lasers blocked):
   - All sensors will show low baseline voltages
   - These become each sensor's initial "peak"

2. **Close door** (lasers unblocked):
   - Each sensor's peak voltage updates to its unblocked level
   - All sensors should show "CLEAR" status (0mV drop)

3. **Block individual sensors** (wave hand through laser):
   - Only the blocked sensor's voltage drops
   - That sensor shows "BLOCKED" when it drops >30mV from ITS OWN peak
   - Other sensors remain "CLEAR"

4. **Check sensor-specific behavior**:
   - Sensor 1 (peak ~550mV): Blocked at <520mV
   - Sensor 35 (peak ~270mV): Blocked at <240mV
   - Each sensor has its own threshold!

## Notes

- **Peak values persist** across page refreshes (stored in JavaScript variable)
- **Refresh page** to reset all peaks if you want to recalibrate
- **Digital door sensors** (27-30) use fixed 0-5V thresholds (not dynamic)
- **Sensor 34** reads 0.000V in both states - may require investigation

## Threshold Constant

The 30mV drop threshold is defined as:
```javascript
const DROP_THRESHOLD_MV = 30;
const DROP_THRESHOLD_V = 0.030;
```

To adjust sensitivity, modify these values:
- **Increase** (e.g., 50mV) = less sensitive, fewer false alarms
- **Decrease** (e.g., 20mV) = more sensitive, detects smaller blockages
