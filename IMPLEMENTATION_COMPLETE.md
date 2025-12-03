# Statistical Calibration + Safety Status Implementation

## Status: Backend Complete, Safety API Working, Calibration API + UI Pending

### ✓ Completed

1. **Statistical Calibration Module** (`laser_calibration_simple.py`)
   - IQR-based threshold calculation
   - Hysteresis detection to prevent flicker
   - Confidence scoring
   - Persistent storage to `data/laser_calibration.json`
   - Status: **TESTED & WORKING**

2. **Laser Array Handler Integration** (`laser_array_handler.py`)
   - Import: line 25
   - Initialization: lines 236-245
   - Safety status tracking
   - Methods added:
     - `get_safety_status()` - lines 1732-1767
     - `get_all_readings_sync()` - lines 1769-1805
   - Status: **TESTED & WORKING**
   - **Bug Fixed (2025-11-24)**: Fixed AttributeError where code referenced non-existent `_connected_a` and `_connected_b` attributes. Changed to use actual attributes `_serial_a` and `_serial_b` at lines 1734, 1774, 1788. See BUG_FIX_REPORT.md for details.

3. **Safety API Endpoint** (`api_server.py`)
   - Endpoint: `/api/safety/current` (line 629)
   - Status: **IMPLEMENTED & WORKING**
   - Returns door status (open/closed), last update time, and change count
   - Dashboard polls this endpoint every 2 seconds
   - Endpoint test: ✓ PASSING (200 OK)

### Pending

#### 4. Calibration API Endpoints (Add to `api_server.py` in `_setup_routes()` method)

Add after line 1684 (after calibration_history endpoint):

```python
# ========== LASER CALIBRATION & SAFETY ENDPOINTS ==========

@self.app.get("/api/laser/safety")
async def get_laser_safety():
    """Get Arduino A safety status (door open/closed)."""
    try:
        laser_sensor = self.sensors.get('laser_array_y')
        if laser_sensor and hasattr(laser_sensor, 'get_safety_status'):
            return await laser_sensor.get_safety_status()
        return {
            'error': 'Laser sensor not available',
            'door_closed': False,
            'last_update': None
        }
    except Exception as e:
        logger.error(f"Safety status error: {e}")
        return {
            'error': str(e),
            'door_closed': False,
            'last_update': None
        }

@self.app.get("/api/laser/calibration/status")
async def get_calibration_status():
    """Get calibration status."""
    try:
        laser_sensor = self.sensors.get('laser_array_y')
        if laser_sensor and hasattr(laser_sensor, 'calibration'):
            status = laser_sensor.calibration.get_status()
            return {
                **status,
                'timestamp': datetime.utcnow().isoformat()
            }
        return {
            'error': 'Calibration not available',
            'has_calibration': False
        }
    except Exception as e:
        logger.error(f"Calibration status error: {e}")
        return {
            'error': str(e),
            'has_calibration': False
        }

@self.app.post("/api/laser/calibration/start")
async def start_calibration():
    """Start 30-second statistical calibration."""
    try:
        laser_sensor = self.sensors.get('laser_array_y')
        if not laser_sensor or not hasattr(laser_sensor, 'calibration'):
            return {
                'success': False,
                'error': 'Calibration not available'
            }

        # Check if calibration already in progress
        status = laser_sensor.calibration.get_status()
        if status.get('calibration_in_progress'):
            return {
                'success': False,
                'error': 'Calibration already in progress',
                'progress': status.get('calibration_progress', 0)
            }

        # Run calibration in thread to avoid blocking
        import asyncio
        result = await asyncio.to_thread(
            laser_sensor.calibration.calibrate,
            laser_sensor.get_all_readings_sync
        )

        return result

    except Exception as e:
        logger.error(f"Calibration start error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@self.app.get("/api/laser/calibration/progress")
async def get_calibration_progress():
    """Get calibration progress (for polling during calibration)."""
    try:
        laser_sensor = self.sensors.get('laser_array_y')
        if laser_sensor and hasattr(laser_sensor, 'calibration'):
            return laser_sensor.calibration.get_status()
        return {'error': 'Calibration not available'}
    except Exception as e:
        logger.error(f"Calibration progress error: {e}")
        return {'error': str(e)}
```

#### 4. UI Components (Add to `web_dashboard/index.html`)

Add safety status card in the dashboard grid (after line ~200):

```html
<!-- Safety Status Card -->
<div class="card">
    <h3>Safety Status</h3>
    <div class="status-item">
        <span>Door Status:</span>
        <span id="door-status" class="status-value">Unknown</span>
    </div>
    <div class="status-item">
        <span>Last Update:</span>
        <span id="safety-last-update" class="status-value">-</span>
    </div>
    <div class="status-item">
        <span>State Changes:</span>
        <span id="safety-changes" class="status-value">-</span>
    </div>
</div>

<!-- Laser Calibration Card -->
<div class="card">
    <h3>Laser Calibration</h3>
    <div class="status-item">
        <span>Status:</span>
        <span id="cal-status" class="status-value">Not Calibrated</span>
    </div>
    <div class="status-item">
        <span>Last Calibration:</span>
        <span id="cal-last-time" class="status-value">Never</span>
    </div>
    <div class="status-item">
        <span>Sensors Calibrated:</span>
        <span id="cal-sensor-count" class="status-value">0</span>
    </div>
    <button id="calibrate-btn" class="btn-primary">Start Calibration</button>
    <div id="cal-progress-container" style="display:none;">
        <progress id="cal-progress" value="0" max="100"></progress>
        <span id="cal-progress-text">0%</span>
    </div>
    <div id="cal-instructions" style="display:none; color: #ff6b6b; margin-top: 10px;">
        ⚠ Ensure chamber is EMPTY and door is CLOSED before calibrating!
    </div>
</div>
```

#### 5. UI JavaScript (Add to `web_dashboard/dashboard.js`)

Add after existing fetch functions:

```javascript
// ========== LASER SAFETY & CALIBRATION ==========

async function updateSafetyStatus() {
    try {
        const response = await fetch('/api/laser/safety');
        const data = await response.json();

        const doorStatus = document.getElementById('door-status');
        if (data.door_closed) {
            doorStatus.textContent = '✓ CLOSED (Safe)';
            doorStatus.style.color = '#4CAF50';
        } else {
            doorStatus.textContent = '✗ OPEN (Unsafe)';
            doorStatus.style.color = '#ff6b6b';
        }

        document.getElementById('safety-last-update').textContent =
            data.last_update ? new Date(data.last_update).toLocaleTimeString() : 'Never';
        document.getElementById('safety-changes').textContent =
            data.change_count || 0;

    } catch (error) {
        console.error('Safety status error:', error);
        document.getElementById('door-status').textContent = 'Error';
    }
}

async function updateCalibrationStatus() {
    try {
        const response = await fetch('/api/laser/calibration/status');
        const data = await response.json();

        const statusElem = document.getElementById('cal-status');
        if (data.calibration_in_progress) {
            statusElem.textContent = `Calibrating... ${data.calibration_progress}%`;
            statusElem.style.color = '#2196F3';
        } else if (data.has_calibration) {
            statusElem.textContent = '✓ Calibrated';
            statusElem.style.color = '#4CAF50';
        } else {
            statusElem.textContent = 'Not Calibrated';
            statusElem.style.color = '#ff6b6b';
        }

        document.getElementById('cal-last-time').textContent =
            data.last_calibration_time ?
                new Date(data.last_calibration_time).toLocaleString() :
                'Never';
        document.getElementById('cal-sensor-count').textContent =
            data.sensors_calibrated || 0;

    } catch (error) {
        console.error('Calibration status error:', error);
    }
}

async function startCalibration() {
    const btn = document.getElementById('calibrate-btn');
    const progressContainer = document.getElementById('cal-progress-container');
    const instructions = document.getElementById('cal-instructions');

    // Show warning
    instructions.style.display = 'block';

    // Confirm with user
    if (!confirm('Is the chamber EMPTY and door CLOSED?\n\nCalibration will take 30 seconds.')) {
        instructions.style.display = 'none';
        return;
    }

    try {
        btn.disabled = true;
        btn.textContent = 'Calibrating...';
        progressContainer.style.display = 'block';

        // Start calibration
        const response = await fetch('/api/laser/calibration/start', {
            method: 'POST'
        });
        const data = await response.json();

        if (!data.success) {
            alert(`Calibration failed: ${data.error}`);
            return;
        }

        // Poll for progress
        const progressInterval = setInterval(async () => {
            const progressResp = await fetch('/api/laser/calibration/progress');
            const progressData = await progressResp.json();

            const progress = progressData.calibration_progress || 0;
            document.getElementById('cal-progress').value = progress;
            document.getElementById('cal-progress-text').textContent = `${progress}%`;

            if (!progressData.calibration_in_progress) {
                clearInterval(progressInterval);
                btn.disabled = false;
                btn.textContent = 'Start Calibration';
                progressContainer.style.display = 'none';
                instructions.style.display = 'none';

                alert('Calibration complete!\n\n' +
                      `Samples: ${data.samples_collected}\n` +
                      `Sensors: ${data.sensors_calibrated}`);

                updateCalibrationStatus();
            }
        }, 1000); // Poll every second

    } catch (error) {
        console.error('Calibration error:', error);
        alert(`Calibration error: ${error.message}`);
        btn.disabled = false;
        btn.textContent = 'Start Calibration';
        progressContainer.style.display = 'none';
        instructions.style.display = 'none';
    }
}

// Add to existing initialization
document.addEventListener('DOMContentLoaded', function() {
    // ... existing code ...

    // Setup calibration button
    document.getElementById('calibrate-btn').addEventListener('click', startCalibration);

    // Update every 2 seconds
    setInterval(updateSafetyStatus, 2000);
    setInterval(updateCalibrationStatus, 2000);

    // Initial load
    updateSafetyStatus();
    updateCalibrationStatus();
});
```

### Testing Checklist

- [x] Calibration module imports successfully
- [x] LaserArrayHandler integration works
- [x] Safety API endpoint accessible and working (`/api/safety/current`)
- [x] Safety endpoint bug fixed (AttributeError resolved)
- [x] Safety status updates automatically (dashboard polls every 2s)
- [ ] Calibration API endpoints implemented
- [ ] UI displays safety status (needs calibration/safety UI cards)
- [ ] UI calibration button works
- [ ] 30-second calibration completes
- [ ] Calibration progress updates in real-time

### Architecture Summary

```
Arduino A (Reed Switch)
    ↓ CMD_GET_SAFETY (0x09)
LaserArrayHandler.get_safety_status()
    ↓
API: GET /api/laser/safety
    ↓
UI: Safety Status Card (auto-refresh 2s)

User clicks "Start Calibration"
    ↓
API: POST /api/laser/calibration/start
    ↓
LaserArrayHandler.calibration.calibrate()
    → 30s @ 25Hz = 750 samples
    → Calculate IQR thresholds
    → Save to data/laser_calibration.json
    ↓
UI: Poll GET /api/laser/calibration/progress
    → Update progress bar
    → Show completion message
```

### File Locations

- **Backend:**
  - `navair_additive/sensors/laser_calibration_simple.py` ✓
  - `navair_additive/sensors/laser_array_handler.py` ✓
  - `navair_additive/communication/api_server.py` (pending)

- **Frontend:**
  - `web_dashboard/index.html` (pending)
  - `web_dashboard/dashboard.js` (pending)

- **Data:**
  - `data/laser_calibration.json` (auto-created on first calibration)
