#!/usr/bin/env python3
"""
Arduino Packet Analyzer - Compare communication from Arduino A and B
Analyzes packet size, timing, structure, and data integrity
"""

import serial
import time
import struct
from collections import defaultdict

# Packet constants
PACKET_START = 0xAA
PACKET_END = 0x55
CMD_GET_DATA = 0x07
RESP_DATA = 0x12

class ArduinoPacketAnalyzer:
    def __init__(self, port, name):
        self.port = port
        self.name = name
        self.ser = None
        self.stats = {
            'total_packets': 0,
            'successful_packets': 0,
            'failed_packets': 0,
            'checksum_errors': 0,
            'packet_sizes': [],
            'response_times': [],
            'sensor_counts': []
        }

    def connect(self):
        """Open serial connection"""
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            print(f"[{self.name}] Connected to {self.port}")
            return True
        except Exception as e:
            print(f"[{self.name}] Failed to connect: {e}")
            return False

    def send_get_data_command(self):
        """Send CMD_GET_DATA command to Arduino"""
        if not self.ser:
            return False

        # Build command packet
        packet = bytearray()
        packet.append(PACKET_START)  # Start marker
        packet.append(CMD_GET_DATA)  # Command
        packet.append(0)             # Data length
        packet.append(0)             # Reserved

        # Calculate checksum
        checksum = sum(packet) & 0xFF
        packet.append(checksum)
        packet.append(PACKET_END)

        # Send command
        self.ser.write(packet)
        self.ser.flush()
        return True

    def read_response_packet(self, timeout=1.0):
        """Read and parse response packet"""
        start_time = time.time()

        # Wait for packet start
        while time.time() - start_time < timeout:
            if self.ser.in_waiting > 0:
                byte = self.ser.read(1)
                if byte[0] == PACKET_START:
                    break
        else:
            return None  # Timeout

        # Read packet header
        try:
            response_code = self.ser.read(1)[0]
            data_len = self.ser.read(1)[0]
            reserved = self.ser.read(1)[0]

            # Read data
            data = self.ser.read(data_len) if data_len > 0 else b''

            # Read checksum and end marker
            checksum = self.ser.read(1)[0]
            end_marker = self.ser.read(1)[0]

            # Calculate elapsed time
            response_time = (time.time() - start_time) * 1000  # ms

            # Verify packet
            if end_marker != PACKET_END:
                return {'error': 'Invalid end marker', 'response_time': response_time}

            # Verify checksum
            calc_checksum = (PACKET_START + response_code + data_len + reserved + sum(data)) & 0xFF
            if calc_checksum != checksum:
                return {
                    'error': 'Checksum mismatch',
                    'expected': calc_checksum,
                    'received': checksum,
                    'response_time': response_time
                }

            # Parse sensor data
            sensors = []
            if response_code == RESP_DATA and len(data) % 3 == 0:
                for i in range(0, len(data), 3):
                    sensor_num = data[i]
                    adc_value = (data[i+1] << 8) | data[i+2]
                    voltage = (adc_value * 5.0) / 1023.0
                    sensors.append({
                        'sensor': sensor_num,
                        'adc': adc_value,
                        'voltage': voltage
                    })

            total_packet_size = 1 + 1 + 1 + 1 + data_len + 1 + 1  # Full packet with overhead

            return {
                'success': True,
                'response_code': response_code,
                'data_len': data_len,
                'total_packet_size': total_packet_size,
                'sensors': sensors,
                'response_time': response_time,
                'checksum_ok': True
            }

        except Exception as e:
            return {'error': str(e)}

    def analyze_packet(self):
        """Send command and analyze response"""
        self.stats['total_packets'] += 1

        if not self.send_get_data_command():
            self.stats['failed_packets'] += 1
            return None

        response = self.read_response_packet()

        if response is None:
            self.stats['failed_packets'] += 1
            return {'error': 'Timeout - no response'}

        if 'error' in response:
            self.stats['failed_packets'] += 1
            if 'Checksum' in response['error']:
                self.stats['checksum_errors'] += 1
            return response

        # Update statistics
        self.stats['successful_packets'] += 1
        self.stats['packet_sizes'].append(response['total_packet_size'])
        self.stats['response_times'].append(response['response_time'])
        self.stats['sensor_counts'].append(len(response['sensors']))

        return response

    def print_stats(self):
        """Print statistics summary"""
        if self.stats['total_packets'] == 0:
            print(f"\n[{self.name}] No packets sent yet")
            return

        print(f"\n{'='*60}")
        print(f"[{self.name}] Packet Statistics")
        print(f"{'='*60}")
        print(f"Total Packets:      {self.stats['total_packets']}")
        print(f"Successful:         {self.stats['successful_packets']}")
        print(f"Failed:             {self.stats['failed_packets']}")
        print(f"Checksum Errors:    {self.stats['checksum_errors']}")
        print(f"Success Rate:       {self.stats['successful_packets']/self.stats['total_packets']*100:.1f}%")

        if self.stats['packet_sizes']:
            avg_size = sum(self.stats['packet_sizes']) / len(self.stats['packet_sizes'])
            print(f"\nPacket Size:        {avg_size:.1f} bytes (avg)")
            print(f"  Min/Max:          {min(self.stats['packet_sizes'])}/{max(self.stats['packet_sizes'])} bytes")

        if self.stats['response_times']:
            avg_time = sum(self.stats['response_times']) / len(self.stats['response_times'])
            print(f"\nResponse Time:      {avg_time:.2f} ms (avg)")
            print(f"  Min/Max:          {min(self.stats['response_times']):.2f}/{max(self.stats['response_times']):.2f} ms")

        if self.stats['sensor_counts']:
            avg_sensors = sum(self.stats['sensor_counts']) / len(self.stats['sensor_counts'])
            print(f"\nSensors per Packet: {avg_sensors:.1f} (avg)")
            print(f"  Min/Max:          {min(self.stats['sensor_counts'])}/{max(self.stats['sensor_counts'])}")

    def close(self):
        """Close serial connection"""
        if self.ser:
            self.ser.close()
            print(f"[{self.name}] Disconnected")


def compare_analyzers(analyzer_a, analyzer_b, num_samples=10):
    """Compare packet analysis from both Arduinos"""
    print("\n" + "="*80)
    print("ARDUINO PACKET COMPARISON ANALYZER")
    print("="*80)
    print(f"\nAnalyzing {num_samples} packets from each Arduino...")
    print(f"Arduino A: {analyzer_a.port}")
    print(f"Arduino B: {analyzer_b.port}\n")

    for i in range(num_samples):
        print(f"\n--- Sample {i+1}/{num_samples} ---")

        # Analyze Arduino A
        print(f"\n[Arduino A] Sending GET_DATA command...")
        result_a = analyzer_a.analyze_packet()

        if result_a:
            if 'error' in result_a:
                print(f"  ERROR: {result_a['error']}")
            else:
                print(f"  ✓ Packet Size: {result_a['total_packet_size']} bytes")
                print(f"  ✓ Data Payload: {result_a['data_len']} bytes")
                print(f"  ✓ Sensors: {len(result_a['sensors'])}")
                print(f"  ✓ Response Time: {result_a['response_time']:.2f} ms")

        # Analyze Arduino B
        print(f"\n[Arduino B] Sending GET_DATA command...")
        result_b = analyzer_b.analyze_packet()

        if result_b:
            if 'error' in result_b:
                print(f"  ERROR: {result_b['error']}")
            else:
                print(f"  ✓ Packet Size: {result_b['total_packet_size']} bytes")
                print(f"  ✓ Data Payload: {result_b['data_len']} bytes")
                print(f"  ✓ Sensors: {len(result_b['sensors'])}")
                print(f"  ✓ Response Time: {result_b['response_time']:.2f} ms")

        # Compare
        if result_a and result_b and 'error' not in result_a and 'error' not in result_b:
            size_diff = result_b['total_packet_size'] - result_a['total_packet_size']
            time_diff = result_b['response_time'] - result_a['response_time']
            sensor_diff = len(result_b['sensors']) - len(result_a['sensors'])

            print(f"\n  COMPARISON:")
            print(f"    Size Difference:    {size_diff:+d} bytes (B - A)")
            print(f"    Time Difference:    {time_diff:+.2f} ms (B - A)")
            print(f"    Sensor Difference:  {sensor_diff:+d} sensors (B - A)")

        time.sleep(0.5)  # Delay between samples

    # Print final statistics
    analyzer_a.print_stats()
    analyzer_b.print_stats()

    # Print comparison summary
    print(f"\n{'='*80}")
    print("COMPARISON SUMMARY")
    print(f"{'='*80}")

    if analyzer_a.stats['packet_sizes'] and analyzer_b.stats['packet_sizes']:
        avg_size_a = sum(analyzer_a.stats['packet_sizes']) / len(analyzer_a.stats['packet_sizes'])
        avg_size_b = sum(analyzer_b.stats['packet_sizes']) / len(analyzer_b.stats['packet_sizes'])
        print(f"\nAverage Packet Size:")
        print(f"  Arduino A: {avg_size_a:.1f} bytes")
        print(f"  Arduino B: {avg_size_b:.1f} bytes")
        print(f"  Difference: {avg_size_b - avg_size_a:+.1f} bytes ({(avg_size_b - avg_size_a)/avg_size_a*100:+.1f}%)")

    if analyzer_a.stats['response_times'] and analyzer_b.stats['response_times']:
        avg_time_a = sum(analyzer_a.stats['response_times']) / len(analyzer_a.stats['response_times'])
        avg_time_b = sum(analyzer_b.stats['response_times']) / len(analyzer_b.stats['response_times'])
        print(f"\nAverage Response Time:")
        print(f"  Arduino A: {avg_time_a:.2f} ms")
        print(f"  Arduino B: {avg_time_b:.2f} ms")
        print(f"  Difference: {avg_time_b - avg_time_a:+.2f} ms ({(avg_time_b - avg_time_a)/avg_time_a*100:+.1f}%)")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    # Initialize analyzers
    analyzer_a = ArduinoPacketAnalyzer('/dev/arduino_a', 'Arduino A')
    analyzer_b = ArduinoPacketAnalyzer('/dev/arduino_b', 'Arduino B')

    try:
        # Connect to both Arduinos
        if not analyzer_a.connect():
            print("Failed to connect to Arduino A")
            exit(1)

        if not analyzer_b.connect():
            print("Failed to connect to Arduino B")
            analyzer_a.close()
            exit(1)

        # Run comparison analysis
        compare_analyzers(analyzer_a, analyzer_b, num_samples=10)

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")

    finally:
        # Clean up
        analyzer_a.close()
        analyzer_b.close()
        print("\nAnalysis complete!")
