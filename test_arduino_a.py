#!/usr/bin/env python3
"""Quick test to check if Arduino A is responding"""
import serial
import time

port = '/dev/arduino_a'
print(f"Testing Arduino A at {port}...")

try:
    ser = serial.Serial(port, 115200, timeout=2)
    time.sleep(2)  # Wait for Arduino reset
    print(f"✓ Connected to {port}")

    # Read any startup messages
    print("\nReading startup messages (3 seconds)...")
    time.sleep(1)
    if ser.in_waiting > 0:
        startup_msg = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        print(f"Startup message: {startup_msg}")

    # Send CMD_GET_DATA (0x07)
    print("\nSending GET_DATA command...")
    packet = bytearray([0xAA, 0x07, 0x00, 0x00])
    checksum = sum(packet) & 0xFF
    packet.append(checksum)
    packet.append(0x55)

    ser.write(packet)
    ser.flush()
    print(f"Sent: {packet.hex()}")

    # Wait for response
    print("\nWaiting for response (2 seconds)...")
    start = time.time()
    response = b''
    while time.time() - start < 2:
        if ser.in_waiting > 0:
            response += ser.read(ser.in_waiting)
            if len(response) > 100:  # Enough data
                break

    if len(response) > 0:
        print(f"✓ Received {len(response)} bytes: {response[:60].hex()}...")
        # Try to parse
        if response[0] == 0xAA:
            print("  - Packet start marker OK")
            if len(response) > 2:
                resp_code = response[1]
                data_len = response[2]
                print(f"  - Response code: 0x{resp_code:02x}")
                print(f"  - Data length: {data_len}")
                if data_len == 48:
                    print("  - ✓ Expected 48 bytes for 16 sensors")
                else:
                    print(f"  - ✗ Expected 48 bytes, got {data_len}")
    else:
        print("✗ NO RESPONSE from Arduino A")

    ser.close()
    print("\n✓ Test complete")

except Exception as e:
    print(f"✗ Error: {e}")
