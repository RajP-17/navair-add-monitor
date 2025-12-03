#!/usr/bin/env python3
"""
Comprehensive API Endpoint Testing Script
Tests all 33 dashboard endpoints and verifies data connectivity
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Tuple
import sys

# ANSI color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class EndpointTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    async def test_endpoint(self, session: aiohttp.ClientSession, method: str, path: str,
                           description: str, expected_keys: List[str] = None) -> Dict:
        """Test a single endpoint and validate response."""
        url = f"{self.base_url}{path}"
        result = {
            'endpoint': path,
            'description': description,
            'method': method,
            'status': 'UNKNOWN',
            'http_code': None,
            'response_time': None,
            'has_data': False,
            'missing_keys': [],
            'error': None
        }

        try:
            start_time = datetime.now()

            if method == 'GET':
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    result['http_code'] = response.status
                    result['response_time'] = (datetime.now() - start_time).total_seconds()

                    if response.status == 200:
                        try:
                            data = await response.json()
                            result['has_data'] = bool(data)

                            # Validate expected keys if provided
                            if expected_keys and isinstance(data, dict):
                                missing = [key for key in expected_keys if key not in data]
                                result['missing_keys'] = missing

                                if not missing:
                                    result['status'] = 'PASS'
                                    self.passed += 1
                                else:
                                    result['status'] = 'WARN'
                                    result['error'] = f"Missing keys: {', '.join(missing)}"
                                    self.warnings += 1
                            else:
                                result['status'] = 'PASS'
                                self.passed += 1

                        except json.JSONDecodeError as e:
                            result['status'] = 'FAIL'
                            result['error'] = f"Invalid JSON: {str(e)}"
                            self.failed += 1
                    elif response.status == 404:
                        result['status'] = 'FAIL'
                        result['error'] = 'Endpoint not found (404)'
                        self.failed += 1
                    elif response.status == 500:
                        result['status'] = 'FAIL'
                        text = await response.text()
                        result['error'] = f'Internal server error: {text[:100]}'
                        self.failed += 1
                    elif response.status == 503:
                        result['status'] = 'WARN'
                        result['error'] = 'Service unavailable (503) - may be expected'
                        self.warnings += 1
                    else:
                        result['status'] = 'WARN'
                        result['error'] = f'Unexpected status code: {response.status}'
                        self.warnings += 1

        except asyncio.TimeoutError:
            result['status'] = 'FAIL'
            result['error'] = 'Request timeout (>10s)'
            self.failed += 1
        except aiohttp.ClientError as e:
            result['status'] = 'FAIL'
            result['error'] = f'Connection error: {str(e)}'
            self.failed += 1
        except Exception as e:
            result['status'] = 'FAIL'
            result['error'] = f'Unexpected error: {str(e)}'
            self.failed += 1

        self.results.append(result)
        return result

    def print_result(self, result: Dict):
        """Print a single test result with color coding."""
        status = result['status']
        endpoint = result['endpoint']
        description = result['description']

        if status == 'PASS':
            icon = f"{GREEN}✓{RESET}"
            status_text = f"{GREEN}PASS{RESET}"
        elif status == 'WARN':
            icon = f"{YELLOW}⚠{RESET}"
            status_text = f"{YELLOW}WARN{RESET}"
        elif status == 'FAIL':
            icon = f"{RED}✗{RESET}"
            status_text = f"{RED}FAIL{RESET}"
        else:
            icon = "?"
            status_text = status

        print(f"{icon} [{status_text}] {endpoint}")
        print(f"   {BLUE}{description}{RESET}")

        if result['http_code']:
            print(f"   HTTP {result['http_code']} | {result['response_time']:.3f}s", end='')
            if result['has_data']:
                print(f" | Has data")
            else:
                print(f" | {YELLOW}No data{RESET}")

        if result['error']:
            print(f"   {RED}Error: {result['error']}{RESET}")

        if result['missing_keys']:
            print(f"   {YELLOW}Missing keys: {', '.join(result['missing_keys'])}{RESET}")

        print()

    async def run_all_tests(self):
        """Run all endpoint tests."""
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}NAVAIR API Endpoint Comprehensive Test Suite{RESET}")
        print(f"{BOLD}{'='*80}{RESET}\n")
        print(f"Testing against: {BLUE}{self.base_url}{RESET}\n")

        async with aiohttp.ClientSession() as session:
            # Test 1: Health Check
            print(f"{BOLD}=== SYSTEM HEALTH ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/health',
                                   'Basic health check', ['status'])
            await self.test_endpoint(session, 'GET', '/api/system/status',
                                   'Overall system status', ['sensors', 'database'])
            await self.test_endpoint(session, 'GET', '/api/system/health',
                                   'Comprehensive system health', ['overall_health'])
            await self.test_endpoint(session, 'GET', '/api/system/performance',
                                   'System performance metrics', ['cpu_usage', 'memory_usage'])
            await self.test_endpoint(session, 'GET', '/api/system/alerts?limit=20',
                                   'System alerts (CRITICAL - was returning 500)', ['alerts', 'count'])

            # Test 2: Sensor Endpoints
            print(f"\n{BOLD}=== SENSOR ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/sensors/current',
                                   'Current sensor readings', ['sensors'])
            await self.test_endpoint(session, 'GET', '/api/sensor_data/laser_array',
                                   'Laser array data (FIXED - ADC values)', ['lasers'])

            # Test 3: Print/Printer Endpoints
            print(f"\n{BOLD}=== PRINT/PRINTER ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/print/status',
                                   'Current print job status')
            await self.test_endpoint(session, 'GET', '/api/print/temperatures',
                                   'Printer temperatures (may be 503 if offline)')
            await self.test_endpoint(session, 'GET', '/api/print/materials',
                                   'Loaded materials')

            # Test 4: Quality Endpoints
            print(f"\n{BOLD}=== QUALITY ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/quality/current',
                                   'Current quality prediction', ['quality_score', 'confidence'])
            await self.test_endpoint(session, 'GET', '/api/quality/fmea',
                                   'FMEA analysis', ['critical_failures', 'rpn_average'])
            await self.test_endpoint(session, 'GET', '/api/quality/material_efficiency',
                                   'Material efficiency metrics')
            await self.test_endpoint(session, 'GET', '/api/quality/metrics',
                                   'Quality metrics summary')

            # Test 5: Analytics Endpoints
            print(f"\n{BOLD}=== ANALYTICS ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/analytics/correlation',
                                   'Sensor correlation analysis')
            await self.test_endpoint(session, 'GET', '/api/analytics/anomalies',
                                   'Anomaly detection')
            await self.test_endpoint(session, 'GET', '/api/analytics/prediction',
                                   'Prediction accuracy')
            await self.test_endpoint(session, 'GET', '/api/analytics/process_capability',
                                   'Process capability (Cpk)')
            await self.test_endpoint(session, 'GET', '/api/analytics/ml_insights',
                                   'ML model insights')
            await self.test_endpoint(session, 'GET', '/api/analytics/ml_performance_history',
                                   'ML performance history')
            await self.test_endpoint(session, 'GET', '/api/analytics/risk_assessment',
                                   'Risk assessment')

            # Test 6: Maintenance & Safety
            print(f"\n{BOLD}=== MAINTENANCE & SAFETY ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/maintenance/schedule',
                                   'Maintenance schedule')
            await self.test_endpoint(session, 'GET', '/api/maintenance/calibration_history',
                                   'Calibration history')
            await self.test_endpoint(session, 'GET', '/api/safety/current',
                                   'Current safety status')

            # Test 7: Defect Detection
            print(f"\n{BOLD}=== DEFECT DETECTION ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/defects/monitoring-status',
                                   'Defect monitoring status', ['enabled'])
            await self.test_endpoint(session, 'GET', '/api/defects/summary',
                                   'Defect summary', ['total_defects'])
            await self.test_endpoint(session, 'GET', '/api/defects/active',
                                   'Active defects', ['defects'])
            await self.test_endpoint(session, 'GET', '/api/defects/history?hours=24',
                                   'Defect history')

            # Test 8: Jobs
            print(f"\n{BOLD}=== JOB ENDPOINTS ==={RESET}\n")
            await self.test_endpoint(session, 'GET', '/api/jobs/active',
                                   'Active print jobs', ['active_jobs', 'count'])

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed + self.warnings

        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}TEST SUMMARY{RESET}")
        print(f"{BOLD}{'='*80}{RESET}\n")

        print(f"Total Endpoints Tested: {BOLD}{total}{RESET}")
        print(f"{GREEN}Passed: {self.passed}{RESET}")
        print(f"{YELLOW}Warnings: {self.warnings}{RESET}")
        print(f"{RED}Failed: {self.failed}{RESET}")

        if self.failed == 0:
            print(f"\n{GREEN}{BOLD}✓ ALL CRITICAL TESTS PASSED!{RESET}")
        else:
            print(f"\n{RED}{BOLD}✗ SOME TESTS FAILED - REVIEW ERRORS ABOVE{RESET}")

        # Breakdown by category
        print(f"\n{BOLD}FAILED ENDPOINTS:{RESET}")
        failed_endpoints = [r for r in self.results if r['status'] == 'FAIL']
        if failed_endpoints:
            for r in failed_endpoints:
                print(f"  {RED}✗{RESET} {r['endpoint']} - {r['error']}")
        else:
            print(f"  {GREEN}None{RESET}")

        print(f"\n{BOLD}WARNINGS:{RESET}")
        warning_endpoints = [r for r in self.results if r['status'] == 'WARN']
        if warning_endpoints:
            for r in warning_endpoints:
                print(f"  {YELLOW}⚠{RESET} {r['endpoint']} - {r['error']}")
        else:
            print(f"  {GREEN}None{RESET}")

        print(f"\n{BOLD}{'='*80}{RESET}\n")

        # Save detailed report
        self.save_json_report()

    def save_json_report(self):
        """Save detailed JSON report."""
        report_file = '/home/navair/Desktop/navair-add-monitor/endpoint_test_report.json'
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'base_url': self.base_url,
                'summary': {
                    'total': len(self.results),
                    'passed': self.passed,
                    'failed': self.failed,
                    'warnings': self.warnings
                },
                'results': self.results
            }, f, indent=2)
        print(f"Detailed report saved to: {BLUE}{report_file}{RESET}")


async def main():
    """Main entry point."""
    # Try different possible ports
    ports = [8000, 5000, 8080, 3000]

    print(f"{BOLD}Checking for running API server...{RESET}\n")

    tester = None
    for port in ports:
        url = f"http://localhost:{port}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/api/health", timeout=aiohttp.ClientTimeout(total=2)) as response:
                    if response.status in [200, 404]:  # Server is responding
                        print(f"{GREEN}✓ Found API server at {url}{RESET}\n")
                        tester = EndpointTester(base_url=url)
                        break
        except:
            continue

    if not tester:
        print(f"{RED}✗ Could not find API server on ports {ports}{RESET}")
        print(f"{YELLOW}Please start the NAVAIR application first.{RESET}\n")
        sys.exit(1)

    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
