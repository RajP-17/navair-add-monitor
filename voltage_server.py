#!/usr/bin/env python3
"""
Standalone voltage monitoring server for NAVAIR laser sensors
Serves raw voltage data via API and web UI
"""
from flask import Flask, jsonify, send_file
import serial
import time
import threading
from pathlib import Path

app = Flask(__name__)

# Global sensor data cache
sensor_data_a = {}
sensor_data_b = {}
data_lock = threading.Lock()

# Protocol constants
PACKET_START = 0xAA
PACKET_END = 0x55
CMD_GET_DATA = 0x07
RESP_DATA = 0x12

def send_command(ser, cmd):
    packet = bytearray([PACKET_START, cmd, 0, 0])
    checksum = sum(packet) & 0xFF
    packet.append(checksum)
    packet.append(PACKET_END)
    ser.write(packet)
    time.sleep(0.05)

def read_response(ser):
    while True:
        b = ser.read(1)
        if not b:
            return None
        if b[0] == PACKET_START:
            break

    resp_code = ser.read(1)[0]
    data_len = ser.read(1)[0]
    reserved = ser.read(1)[0]
    data = ser.read(data_len) if data_len > 0 else b''
    checksum = ser.read(1)[0]
    end_marker = ser.read(1)[0]

    if end_marker != PACKET_END:
        return None
    return resp_code, data

def parse_sensors(data):
    sensors = {}
    for i in range(0, len(data), 3):
        num = data[i]
        raw = (data[i+1] << 8) | data[i+2]
        voltage = (raw / 1023.0) * 5.0
        percent = (raw / 1023.0) * 100.0
        sensors[num] = {
            "raw": raw,
            "voltage": round(voltage, 2),
            "percent": round(percent, 1)
        }
    return sensors

def read_arduino_loop(port, data_dict):
    """Background thread to continuously read from Arduino"""
    while True:
        try:
            with serial.Serial(port, 115200, timeout=1) as ser:
                time.sleep(0.5)
                ser.reset_input_buffer()

                while True:
                    send_command(ser, CMD_GET_DATA)
                    result = read_response(ser)

                    if result:
                        resp_code, data = result
                        if resp_code == RESP_DATA and len(data) > 0:
                            sensors = parse_sensors(data)
                            with data_lock:
                                data_dict.clear()
                                data_dict.update(sensors)

                    time.sleep(0.5)

        except Exception as e:
            print(f"Error reading {port}: {e}")
            time.sleep(2)

@app.route('/')
def index():
    """Serve the voltage monitoring page"""
    html_path = Path('/home/navair/Desktop/navair-add-monitor/Navair_Project/navair_additive/web_dashboard/voltages.html')
    return send_file(html_path)

@app.route('/api/arduino/a/raw')
def get_arduino_a_raw():
    """Get raw voltage data from Arduino A (sensors 1-20)"""
    with data_lock:
        return jsonify({"sensors": dict(sensor_data_a)})

@app.route('/api/arduino/b/raw')
def get_arduino_b_raw():
    """Get raw voltage data from Arduino B (sensors 21-36)"""
    with data_lock:
        return jsonify({"sensors": dict(sensor_data_b)})

@app.route('/api/sensors/all')
def get_all_sensors():
    """Get all 36 sensors combined"""
    with data_lock:
        all_sensors = {**sensor_data_a, **sensor_data_b}
        return jsonify({"sensors": all_sensors})

if __name__ == '__main__':
    print("Starting NAVAIR Voltage Monitor Server...")
    print("="*60)

    # Start background threads to read from Arduinos
    thread_a = threading.Thread(target=read_arduino_loop, args=('/dev/ttyACM0', sensor_data_a), daemon=True)
    thread_b = threading.Thread(target=read_arduino_loop, args=('/dev/ttyACM1', sensor_data_b), daemon=True)

    thread_a.start()
    thread_b.start()

    print("Arduino readers started")
    print("Web UI available at: http://192.168.1.2:5001")
    print("API endpoints:")
    print("  /api/arduino/a/raw - Arduino A sensors")
    print("  /api/arduino/b/raw - Arduino B sensors")
    print("  /api/sensors/all   - All 36 sensors")
    print("="*60)

    # Run Flask server
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
