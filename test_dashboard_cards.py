#!/usr/bin/env python3
"""
Dashboard Card Data Connectivity Test
Verifies which dashboard cards/sections are receiving data
"""

import asyncio
import aiohttp
import json
from typing import Dict, List

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class DashboardCardTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.card_results = {}

    async def test_card(self, session: aiohttp.ClientSession, card_name: str,
                       endpoint: str, data_check_func=None) -> Dict:
        """Test if a dashboard card is receiving data."""
        url = f"{self.base_url}{endpoint}"
        result = {
            'card': card_name,
            'endpoint': endpoint,
            'status': 'UNKNOWN',
            'has_data': False,
            'data_summary': None
        }

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()

                    if data_check_func:
                        has_data, summary = data_check_func(data)
                        result['has_data'] = has_data
                        result['data_summary'] = summary
                    else:
                        result['has_data'] = bool(data)
                        result['data_summary'] = "Data present"

                    result['status'] = 'OK' if result['has_data'] else 'EMPTY'
                else:
                    result['status'] = f'HTTP {response.status}'
        except Exception as e:
            result['status'] = 'ERROR'
            result['data_summary'] = str(e)[:50]

        return result

    def print_card_result(self, result: Dict):
        """Print dashboard card test result."""
        card = result['card']
        status = result['status']

        if status == 'OK' and result['has_data']:
            icon = f"{GREEN}✓{RESET}"
            status_color = GREEN
        elif status == 'EMPTY':
            icon = f"{YELLOW}○{RESET}"
            status_color = YELLOW
        else:
            icon = f"{RED}✗{RESET}"
            status_color = RED

        print(f"{icon} {BOLD}{card}{RESET}")
        print(f"   Endpoint: {BLUE}{result['endpoint']}{RESET}")
        print(f"   Status: {status_color}{status}{RESET}")

        if result['data_summary']:
            print(f"   Data: {result['data_summary']}")
        print()

    async def run_dashboard_tests(self):
        """Test all dashboard cards."""
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}Dashboard Card Data Connectivity Test{RESET}")
        print(f"{BOLD}{'='*80}{RESET}\n")

        async with aiohttp.ClientSession() as session:
            # System Status Cards
            print(f"{BOLD}=== SYSTEM STATUS CARDS ==={RESET}\n")

            result = await self.test_card(
                session, "System Health Card", "/api/system/health",
                lambda d: (bool(d.get('overall_health')), f"Health: {d.get('overall_health', 'N/A')}")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "System Performance Card", "/api/system/performance",
                lambda d: (d.get('cpu_usage') is not None, f"CPU: {d.get('cpu_usage', 0):.1f}% | Memory: {d.get('memory_usage', 0):.1f}%")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "System Alerts Card", "/api/system/alerts?limit=20",
                lambda d: (True, f"{d.get('count', 0)} alerts" if d.get('count', 0) > 0 else "No alerts")
            )
            self.print_card_result(result)

            # Sensor Cards
            print(f"{BOLD}=== SENSOR CARDS ==={RESET}\n")

            result = await self.test_card(
                session, "Laser Array Visualization (36 boxes)", "/api/sensor_data/laser_array",
                lambda d: (
                    len(d.get('lasers', [])) == 36,
                    f"36 lasers - {sum(1 for l in d.get('lasers', []) if l.get('active', False))} active"
                )
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Current Sensors Card", "/api/sensors/current",
                lambda d: (bool(d.get('timestamp')), f"Timestamp: {d.get('timestamp', 'N/A')[:19]}" if d.get('timestamp') else "No data")
            )
            self.print_card_result(result)

            # Printer Cards
            print(f"{BOLD}=== PRINTER STATUS CARDS ==={RESET}\n")

            result = await self.test_card(
                session, "Print Status Card", "/api/print/status",
                lambda d: (bool(d.get('status')), f"Status: {d.get('status', 'N/A')}")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Printer Temperatures Card", "/api/print/temperatures",
                lambda d: (
                    d.get('nozzle_temp') is not None or d.get('bed_temp') is not None,
                    f"Nozzle: {d.get('nozzle_temp', 'N/A')}°C | Bed: {d.get('bed_temp', 'N/A')}°C"
                )
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Materials Card", "/api/print/materials",
                lambda d: (bool(d.get('materials')), f"{len(d.get('materials', []))} materials" if isinstance(d.get('materials'), list) else "No materials")
            )
            self.print_card_result(result)

            # Quality Cards
            print(f"{BOLD}=== QUALITY CARDS ==={RESET}\n")

            result = await self.test_card(
                session, "Current Quality Card", "/api/quality/current",
                lambda d: (
                    d.get('quality_score') is not None,
                    f"Score: {d.get('quality_score', 'N/A')} | Confidence: {d.get('confidence', 'N/A')}"
                )
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "FMEA Analysis Card", "/api/quality/fmea",
                lambda d: (
                    d.get('rpn_average') is not None,
                    f"Critical: {d.get('critical_failures', 0)} | RPN Avg: {d.get('rpn_average', 0):.1f}"
                )
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Material Efficiency Card", "/api/quality/material_efficiency",
                lambda d: (bool(d.get('material_efficiency')), f"Efficiency: {d.get('material_efficiency', 'N/A')}")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Quality Metrics Summary Card", "/api/quality/metrics",
                lambda d: (
                    d.get('overall_quality') is not None,
                    f"Overall: {d.get('overall_quality', 'N/A')} | Success: {d.get('successful_prints', 0)}"
                )
            )
            self.print_card_result(result)

            # Analytics Cards
            print(f"{BOLD}=== ANALYTICS CARDS ==={RESET}\n")

            result = await self.test_card(
                session, "Sensor Correlation Card", "/api/analytics/correlation",
                lambda d: (bool(d.get('correlations')), f"{len(d.get('correlations', []))} correlations" if isinstance(d.get('correlations'), list) else "No data")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Anomaly Detection Card", "/api/analytics/anomalies",
                lambda d: (bool(d.get('anomalies')), f"{len(d.get('anomalies', []))} anomalies detected" if isinstance(d.get('anomalies'), list) else "No anomalies")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "ML Insights Card", "/api/analytics/ml_insights",
                lambda d: (bool(d.get('feature_importance')), "ML data available" if d.get('feature_importance') else "No ML data")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Process Capability Card", "/api/analytics/process_capability",
                lambda d: (bool(d.get('cpk')), f"Cpk: {d.get('cpk', 'N/A')}")
            )
            self.print_card_result(result)

            # Defect Detection Cards
            print(f"{BOLD}=== DEFECT DETECTION CARDS ==={RESET}\n")

            result = await self.test_card(
                session, "Defect Monitoring Status Card", "/api/defects/monitoring-status",
                lambda d: (bool(d), f"Monitoring: {'Enabled' if d.get('monitoring_active') else 'Disabled'}" if d else "No status")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Defect Summary Card", "/api/defects/summary",
                lambda d: (bool(d), f"Total: {d.get('total', 0)} | Active: {d.get('active', 0)}" if d else "No summary")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Active Defects Card", "/api/defects/active",
                lambda d: (True, f"{len(d.get('defects', []))} active defects" if isinstance(d.get('defects'), list) else "No defects")
            )
            self.print_card_result(result)

            # Maintenance & Safety Cards
            print(f"{BOLD}=== MAINTENANCE & SAFETY CARDS ==={RESET}\n")

            result = await self.test_card(
                session, "Maintenance Schedule Card", "/api/maintenance/schedule",
                lambda d: (bool(d.get('sensors')), f"{len(d.get('sensors', []))} sensors" if isinstance(d.get('sensors'), list) else "No schedule")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Safety Status Card", "/api/safety/current",
                lambda d: (bool(d.get('status')), f"Status: {d.get('status', 'N/A')}")
            )
            self.print_card_result(result)

            result = await self.test_card(
                session, "Active Jobs Card", "/api/jobs/active",
                lambda d: (True, f"{d.get('count', 0)} active jobs")
            )
            self.print_card_result(result)

        self.print_summary()

    def print_summary(self):
        """Print dashboard test summary."""
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}DASHBOARD CARD SUMMARY{RESET}")
        print(f"{BOLD}{'='*80}{RESET}\n")

        print(f"{GREEN}✓{RESET} = Card has data (working)")
        print(f"{YELLOW}○{RESET} = Card connected but empty (no current data)")
        print(f"{RED}✗{RESET} = Card not working (error)")
        print()


async def main():
    tester = DashboardCardTester()
    await tester.run_dashboard_tests()


if __name__ == "__main__":
    asyncio.run(main())
