# Statistical Calibration + Safety Status Implementation

## What This Adds
1. **Manual Statistical Calibration**: 30-second calibration using IQR threshold method
2. **Safety Status Display**: Shows door open/closed status from Arduino A
3. **UI Controls**: Calibration button and safety status card

---

## File 1: Create Simplified Calibration Module

**File:** `Navair_Project/navair_additive/navair_additive/sensors/laser_calibration_simple.py`

```python
"""Simple statistical calibration for laser sensors."""

import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Callable

import numpy as np

logger = logging.getLogger(__name__)


class StatisticalCalibration:
    """Statistical calibration using IQR method."""

    def __init__(self, calibration_file: str = "data/laser_calibration.json"):
        self.calibration_file = Path(calibration_file)
        self.calibration_file.parent.mkdir(parents=True, exist_ok=True)

        self.thresholds = {}  # {sensor_id: {'threshold': float, 'baseline_mean': float}}
        self.calibration_in_progress = False
        self.calibration_progress = 0
        self.last_calibration_time = None

        self.load_calibration()

    def calibrate(self, sensor_reader_func: Callable, duration_seconds: int = 30,
                  sample_rate_hz: int = 25, sensitivity: float = 1.5) -> Dict:
        """
        Run manual statistical calibration.

        IMPORTANT: Chamber must be EMPTY and door CLOSED!

        Args:
            sensor_reader_func: Function that returns Dict[int, float]
            duration_seconds: Calibration duration (default 30s)
            sample_rate_hz: Sample rate (default 25Hz)
            sensitivity: IQR multiplier (default 1.5, lower = more sensitive)
        """
        logger.info(f"Starting calibration: {duration_seconds}s at {sample_rate_hz}Hz")

        self.calibration_in_progress = True
        self.calibration_progress = 0

        total_samples = duration_seconds * sample_rate_hz
        sensor_readings = {i: [] for i in range(1, 37)}

        try:
            for sample in range(total_samples):
                readings = sensor_reader_func()
                for sensor_id, voltage in readings.items():
                    sensor_readings[sensor_id].append(voltage)

                self.calibration_progress = int((sample + 1) / total_samples * 100)
                time.sleep(1.0 / sample_rate_hz)

            # Calculate thresholds
            self.thresholds = {}
            for sensor_id, readings in sensor_readings.items():
                if len(readings) == 0:
                    continue

                arr = np.array(readings)
                mean = float(np.mean(arr))
                q1 = float(np.percentile(arr, 25))
                q3 = float(np.percentile(arr, 75))
                iqr = q3 - q1

                # IQR method threshold
                threshold = q1 - (sensitivity * iqr)
                threshold = max(threshold, 0.5)  # Minimum 0.5V

                self.thresholds[sensor_id] = {
                    'threshold': threshold,
                    'baseline_mean': mean,
                    'hysteresis': 0.2
                }

            self.last_calibration_time = datetime.now().isoformat()
            self.save_calibration()

            logger.info(f"Calibration complete: {len(self.thresholds)} sensors")

            return {
                'success': True,
                'samples_collected': total_samples,
                'sensors_calibrated': len(self.thresholds),
                'timestamp': self.last_calibration_time
            }

        finally:
            self.calibration_in_progress = False
            self.calibration_progress = 0

    def detect_blocking(self, current_readings: Dict[int, float],
                       previous_state: Dict[int, bool] = None) -> Dict[int, Dict]:
        """
        Detect blocking using calibrated thresholds.

        Returns:
            Dict of {sensor_id: {'blocked': bool, 'confidence': float, ...}}
        """
        if previous_state is None:
            previous_state = {}

        blocking_status = {}

        for sensor_id, voltage in current_readings.items():
            if sensor_id not in self.thresholds:
                # Not calibrated - use default
                blocked = voltage < 1.5
                confidence = 0.5
                threshold = 1.5
            else:
                threshold_data = self.thresholds[sensor_id]
                threshold = threshold_data['threshold']
                hysteresis = threshold_data.get('hysteresis', 0.2)
                baseline_mean = threshold_data['baseline_mean']

                # Get previous state
                was_blocked = previous_state.get(sensor_id, False)

                # Apply hysteresis
                if was_blocked:
                    blocked = voltage < (threshold + hysteresis)
                else:
                    blocked = voltage < threshold

                # Calculate confidence
                if blocked:
                    confidence = min((threshold - voltage) / threshold, 1.0)
                else:
                    confidence = min((voltage - threshold) / (baseline_mean - threshold), 1.0)
                confidence = max(0, confidence)

            blocking_status[sensor_id] = {
                'blocked': blocked,
                'confidence': confidence,
                'voltage': voltage,
                'threshold': threshold
            }

        return blocking_status

    def get_status(self) -> Dict:
        """Get calibration status."""
        return {
            'calibration_in_progress': self.calibration_in_progress,
            'calibration_progress': self.calibration_progress,
            'last_calibration_time': self.last_calibration_time,
            'sensors_calibrated': len(self.thresholds),
            'has_calibration': len(self.thresholds) > 0
        }

    def save_calibration(self):
        """Save to file."""
        data = {
            'last_calibration_time': self.last_calibration_time,
            'thresholds': self.thresholds
        }
        try:
            with open(self.calibration_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Calibration saved: {self.calibration_file}")
        except Exception as e:
            logger.error(f"Failed to save: {e}")

    def load_calibration(self):
        """Load from file."""
        if not self.calibration_file.exists():
            return

        try:
            with open(self.calibration_file, 'r') as f:
                data = json.load(f)
            self.last_calibration_time = data.get('last_calibration_time')
            self.thresholds = {
                int(k): v for k, v in data.get('thresholds', {}).items()
            }
            logger.info(f"Calibration loaded: {len(self.thresholds)} sensors")
        except Exception as e:
            logger.error(f"Failed to load: {e}")
```

---

## File 2: Add to laser_array_handler.py

Add this import at the top (around line 24):
```python
from .laser_calibration_simple import StatisticalCalibration
```

Add to `__init__` method (around line 200):
```python
# Calibration system
self.calibration = StatisticalCalibration()

# Safety status
self.safety_status = {
    'door_closed': True,
    'change_count': 0,
    'uptime_ms': 0,
    'last_update': None
}
self._previous_blocking_state = {}
```

Add these two methods at the end of the class (around line 1600):

```python
async def get_safety_status(self) -> Dict:
    """Query Arduino A for safety status."""
    if not self._serial_a or not self._connected_a:
        return {'error': 'Arduino A not connected', **self.safety_status}

    try:
        packet = LaserArrayProtocol.create_packet(LaserArrayProtocol.CMD_GET_SAFETY)
        self._serial_a.write(packet)
        await asyncio.sleep(0.1)

        response_data = self._serial_a.read(100)
        if not response_data:
            return self.safety_status

        result = LaserArrayProtocol.parse_packet(response_data)
        if not result:
            return self.safety_status

        resp_code, payload = result
        if resp_code == LaserArrayProtocol.RESP_SAFETY and len(payload) == 9:
            safety_state = payload[0]
            change_count = struct.unpack('<I', payload[1:5])[0]
            uptime_ms = struct.unpack('<I', payload[5:9])[0]

            self.safety_status = {
                'door_closed': bool(safety_state),
                'change_count': change_count,
                'uptime_ms': uptime_ms,
                'last_update': datetime.now().isoformat()
            }

        return self.safety_status

    except Exception as e:
        logger.error(f"Error querying safety: {e}")
        return self.safety_status

def get_all_readings_sync(self) -> Dict[int, float]:
    """Get current readings synchronously (for calibration)."""
    readings = {}

    try:
        if self._connected_a:
            packet = LaserArrayProtocol.create_packet(LaserArrayProtocol.CMD_GET_DATA)
            self._serial_a.write(packet)
            time.sleep(0.05)
            data = self._serial_a.read(200)
            result = LaserArrayProtocol.parse_packet(data)
            if result:
                _, payload = result
                for i in range(0, len(payload), 3):
                    sensor_id = payload[i]
                    adc_value = (payload[i+1] << 8) | payload[i+2]
                    voltage = (adc_value * 5.0) / 1023.0
                    readings[sensor_id] = voltage

        if self._connected_b:
            packet = LaserArrayProtocol.create_packet(LaserArrayProtocol.CMD_GET_DATA)
            self._serial_b.write(packet)
            time.sleep(0.05)
            data = self._serial_b.read(200)
            result = LaserArrayProtocol.parse_packet(data)
            if result:
                _, payload = result
                for i in range(0, len(payload), 3):
                    sensor_id = payload[i]
                    adc_value = (payload[i+1] << 8) | payload[i+2]
                    voltage = (adc_value * 5.0) / 1023.0
                    readings[sensor_id] = voltage

    except Exception as e:
        logger.error(f"Error getting readings: {e}")

    return readings
```

In the `_read_sensors` method, after collecting sensor_voltages, add:

```python
# Apply calibration blocking detection
blocking_status = self.calibration.detect_blocking(
    sensor_voltages,
    self._previous_blocking_state
)
self._previous_blocking_state = {
    sid: status['blocked'] for sid, status in blocking_status.items()
}
```

---

## Implementation Complete!

Apply the changes above, then I'll help create the API endpoints and UI in the next steps.

Would you like me to continue with:
1. API endpoints
2. UI components
3. Or test what we have so far?
