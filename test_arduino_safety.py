#!/usr/bin/env python3
"""Test Arduino A safety status reporting (door/top open/closed)"""
import serial
import time

# Protocol constants from arduino_a.ino
PACKET_START = 0xAA
PACKET_END = 0x55
CMD_GET_STATUS = 0x04  # Includes safety in byte 8
CMD_GET_SAFETY = 0x09  # Dedicated safety status
RESP_STATUS = 0x13
RESP_SAFETY = 0x14

port = '/dev/arduino_a'
print(f"Testing Arduino A safety status at {port}...")

try:
    ser = serial.Serial(port, 115200, timeout=2)
    time.sleep(2)  # Wait for Arduino reset
    print(f"✓ Connected to {port}\n")

    # Read and discard any startup messages
    time.sleep(0.5)
    if ser.in_waiting > 0:
        ser.read(ser.in_waiting)

    # Test 1: CMD_GET_STATUS (includes safety in status[8])
    print("=" * 60)
    print("Test 1: CMD_GET_STATUS (0x04)")
    print("=" * 60)

    packet = bytearray([PACKET_START, CMD_GET_STATUS, 0x00, 0x00])
    checksum = sum(packet) & 0xFF
    packet.append(checksum)
    packet.append(PACKET_END)

    ser.write(packet)
    ser.flush()
    print(f"Sent: {packet.hex()}")

    # Wait for response
    time.sleep(0.1)
    response = ser.read(100)

    if len(response) > 0:
        print(f"Received {len(response)} bytes: {response.hex()}")
        if response[0] == PACKET_START and response[1] == RESP_STATUS:
            print("✓ Valid STATUS response")
            data_len = response[2]
            print(f"  Data length: {data_len}")

            if data_len >= 9:
                scanning = response[4]
                threshold = (response[5] << 8) | response[6]
                reading_count = (response[7] << 24) | (response[8] << 16) | (response[9] << 8) | response[10]
                num_sensors = response[11]
                safety_state = response[12]  # NEW: Safety status

                print(f"  Scanning active: {scanning}")
                print(f"  Threshold: {threshold}")
                print(f"  Reading count: {reading_count}")
                print(f"  Num sensors: {num_sensors}")
                print(f"  Safety state: {safety_state}")
                print(f"    -> {safety_state} = {'CLOSED (Lasers ON)' if safety_state == 1 else 'OPEN (Lasers OFF)'}")
        else:
            print("✗ Invalid or unexpected response")
    else:
        print("✗ No response\n")

    # Test 2: CMD_GET_SAFETY (dedicated safety status)
    print("\n" + "=" * 60)
    print("Test 2: CMD_GET_SAFETY (0x09) - Dedicated Safety Command")
    print("=" * 60)

    packet = bytearray([PACKET_START, CMD_GET_SAFETY, 0x00, 0x00])
    checksum = sum(packet) & 0xFF
    packet.append(checksum)
    packet.append(PACKET_END)

    ser.write(packet)
    ser.flush()
    print(f"Sent: {packet.hex()}")

    # Wait for response
    time.sleep(0.1)
    response = ser.read(100)

    if len(response) > 0:
        print(f"Received {len(response)} bytes: {response.hex()}")
        if response[0] == PACKET_START and response[1] == RESP_SAFETY:
            print("✓ Valid SAFETY response")
            data_len = response[2]
            print(f"  Data length: {data_len}")

            if data_len == 9:
                safety_state = response[4]
                change_count = (response[5] << 24) | (response[6] << 16) | (response[7] << 8) | response[8]
                timestamp = (response[9] << 24) | (response[10] << 16) | (response[11] << 8) | response[12]

                print(f"  Safety state: {safety_state}")
                print(f"    -> {safety_state} = {'CLOSED (Lasers ON)' if safety_state == 1 else 'OPEN (Lasers OFF)'}")
                print(f"  State changes: {change_count}")
                print(f"  Arduino uptime: {timestamp} ms ({timestamp/1000:.1f} seconds)")
            else:
                print(f"  ✗ Expected 9 bytes, got {data_len}")
        else:
            print("✗ Invalid or unexpected response")
    else:
        print("✗ No response")

    # Test 3: Continuous monitoring for 10 seconds
    print("\n" + "=" * 60)
    print("Test 3: Continuous Safety Monitoring (10 seconds)")
    print("=" * 60)
    print("Querying safety status every 1 second...")
    print("Try opening/closing the door/top during this test!\n")

    for i in range(10):
        packet = bytearray([PACKET_START, CMD_GET_SAFETY, 0x00, 0x00])
        checksum = sum(packet) & 0xFF
        packet.append(checksum)
        packet.append(PACKET_END)

        ser.write(packet)
        ser.flush()

        time.sleep(0.1)
        response = ser.read(100)

        if len(response) > 0 and response[0] == PACKET_START and response[1] == RESP_SAFETY:
            safety_state = response[4]
            change_count = (response[5] << 24) | (response[6] << 16) | (response[7] << 8) | response[8]
            timestamp = (response[9] << 24) | (response[10] << 16) | (response[11] << 8) | response[12]

            status_text = "CLOSED (Lasers ON)" if safety_state == 1 else "OPEN (Lasers OFF)"
            print(f"  [{i+1:2d}] Safety: {status_text:20s} | Changes: {change_count:3d} | Uptime: {timestamp/1000:6.1f}s")
        else:
            print(f"  [{i+1:2d}] ✗ No valid response")

        time.sleep(0.9)  # Total 1 second interval

    ser.close()
    print("\n" + "=" * 60)
    print("✓ Test complete")
    print("=" * 60)

except Exception as e:
    print(f"✗ Error: {e}")
