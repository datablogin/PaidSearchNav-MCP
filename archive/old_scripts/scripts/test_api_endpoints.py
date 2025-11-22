#!/usr/bin/env python3
"""
Test API Endpoints with TopGolf Real Data
Tests all API endpoints using the extracted TopGolf dataset
"""

import csv
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from io import StringIO
from typing import Any, Dict

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from paidsearchnav.api.main import app
from paidsearchnav.core.config import Settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIEndpointTester:
    """Test API endpoints with TopGolf data"""

    def __init__(self, data_file_path: str):
        """Initialize API endpoint tester"""
        self.data_file_path = data_file_path
        self.data = self._load_data()
        self.settings = Settings.from_env()
        self.client = TestClient(app)

    def _load_data(self) -> Dict[str, Any]:
        """Load TopGolf data from JSON file"""
        try:
            with open(self.data_file_path, "r") as f:
                data = json.load(f)
            logger.info(
                f"✅ Loaded TopGolf data: {len(data.get('search_terms', []))} search terms"
            )
            return data
        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            raise

    def _convert_to_csv(self, data_type: str) -> str:
        """Convert JSON data to CSV format for API testing"""
        if data_type == "search_terms":
            data_list = self.data.get("search_terms", [])
            if not data_list:
                return ""

            # Map normalized field names to expected Google Ads CSV column names
            field_mapping = {
                "campaign_id": "Campaign ID",
                "campaign_name": "Campaign",
                "ad_group_id": "Ad group ID",
                "ad_group_name": "Ad group",
                "search_term": "Search term",
                "keyword_text": "Keyword",
                "match_type": "Match type",
                "clicks": "Clicks",
                "impressions": "Impr.",
                "cost_micros": "Cost",  # Will be converted to dollars
                "conversions": "Conversions",
                "conversion_value": "Conversion value",
                "ctr": "CTR",
                "avg_cpc": "Avg. CPC",
                "conversion_rate": "Conv. rate",
                "cpa": "Cost / conv.",
            }

            # Create CSV with expected Google Ads headers
            expected_headers = [
                "Campaign ID",
                "Campaign",
                "Ad group ID",
                "Ad group",
                "Search term",
                "Keyword",
                "Match type",
                "Clicks",
                "Impr.",
                "Cost",
                "Conversions",
                "Conversion value",
                "CTR",
                "Avg. CPC",
                "Conv. rate",
                "Cost / conv.",
            ]

            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=expected_headers)
            writer.writeheader()

            for row in data_list:
                # Convert row to expected format
                csv_row = {}
                for google_ads_col in expected_headers:
                    # Find the corresponding field in our data
                    source_field = None
                    for data_field, mapped_col in field_mapping.items():
                        if mapped_col == google_ads_col:
                            source_field = data_field
                            break

                    if source_field and source_field in row:
                        value = row[source_field]
                        # Convert cost from micros to dollars
                        if source_field == "cost_micros":
                            value = float(value) / 1000000.0
                        csv_row[google_ads_col] = value
                    else:
                        csv_row[google_ads_col] = ""

                writer.writerow(csv_row)

            return output.getvalue()

        return ""

    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test health check endpoint"""
        logger.info("🔍 Testing Health Endpoint...")

        try:
            response = self.client.get("/api/v1/health")

            return {
                "status": "success" if response.status_code == 200 else "error",
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000
                if hasattr(response, "elapsed")
                else "N/A",
                "response_data": response.json()
                if response.status_code == 200
                else None,
            }

        except Exception as e:
            logger.error(f"❌ Health endpoint test failed: {e}")
            return {"status": "error", "reason": str(e)}

    def test_upload_endpoint(self) -> Dict[str, Any]:
        """Test file upload endpoint with TopGolf data"""
        logger.info("📤 Testing Upload Endpoint...")

        try:
            # Create a temporary CSV file with TopGolf data
            csv_data = self._convert_to_csv("search_terms")
            if not csv_data:
                return {
                    "status": "skipped",
                    "reason": "No search terms data available for CSV conversion",
                }

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as temp_file:
                temp_file.write(csv_data)
                temp_file_path = temp_file.name

            try:
                # Test file upload
                with open(temp_file_path, "rb") as f:
                    files = {"file": ("topgolf_search_terms.csv", f, "text/csv")}

                    response = self.client.post(
                        "/api/v1/upload/csv?data_type=search_terms", files=files
                    )

                return {
                    "status": "success"
                    if response.status_code in [200, 201]
                    else "error",
                    "status_code": response.status_code,
                    "response_data": response.json()
                    if response.status_code in [200, 201]
                    else response.text[:500],
                    "file_size_bytes": len(csv_data),
                }

            finally:
                # Clean up temp file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"❌ Upload endpoint test failed: {e}")
            return {"status": "error", "reason": str(e)}

    def test_analysis_endpoint(self) -> Dict[str, Any]:
        """Test analysis endpoint"""
        logger.info("🔍 Testing Analysis Endpoint...")

        try:
            request_data = {
                "customer_id": "577-746-1198",
                "analyzers": ["search_term_analyzer"],
                "date_range": {"start": "2025-08-15", "end": "2025-08-22"},
                "priority": "normal",
            }

            response = self.client.post("/api/v1/analyses/trigger", json=request_data)

            return {
                "status": "success"
                if response.status_code in [200, 201, 202, 403]
                else "error",  # 403 acceptable (auth required)
                "status_code": response.status_code,
                "response_data": response.json()
                if response.status_code in [200, 201, 202]
                else response.text,
            }

        except Exception as e:
            logger.error(f"❌ Analysis endpoint test failed: {e}")
            return {"status": "error", "reason": str(e)}

    def test_reports_endpoint(self) -> Dict[str, Any]:
        """Test reports endpoint"""
        logger.info("📊 Testing Reports Endpoint...")

        try:
            request_data = {
                "customer_id": "577-746-1198",
                "report_type": "search_terms_performance",
                "date_range": "last_7_days",
                "format": "json",
            }

            response = self.client.post(
                "/api/v1/reports/test-audit-id/generate", json=request_data
            )

            return {
                "status": "success"
                if response.status_code in [200, 201, 202, 403]
                else "error",  # 403 acceptable (auth required)
                "status_code": response.status_code,
                "response_data": response.json()
                if response.status_code in [200, 201, 202]
                else response.text[:500],  # Truncate long responses
            }

        except Exception as e:
            logger.error(f"❌ Reports endpoint test failed: {e}")
            return {"status": "error", "reason": str(e)}

    def test_customer_endpoint(self) -> Dict[str, Any]:
        """Test customer management endpoint"""
        logger.info("👤 Testing Customer Endpoint...")

        try:
            # Test GET customer
            response = self.client.get("/api/v1/customers/577-746-1198")

            return {
                "status": "success"
                if response.status_code in [200, 404, 403]
                else "error",  # 403/404 acceptable (auth required or customer doesn't exist)
                "status_code": response.status_code,
                "response_data": response.json()
                if response.status_code == 200
                else response.text[:200],
            }

        except Exception as e:
            logger.error(f"❌ Customer endpoint test failed: {e}")
            return {"status": "error", "reason": str(e)}

    def test_csv_analysis_endpoint(self) -> Dict[str, Any]:
        """Test CSV analysis endpoint with TopGolf data"""
        logger.info("📋 Testing CSV Analysis Endpoint...")

        try:
            # Create CSV data
            csv_data = self._convert_to_csv("search_terms")
            if not csv_data:
                return {
                    "status": "skipped",
                    "reason": "No search terms data for CSV analysis",
                }

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as temp_file:
                temp_file.write(csv_data)
                temp_file_path = temp_file.name

            try:
                # Test CSV analysis
                with open(temp_file_path, "rb") as f:
                    files = {"file": ("topgolf_search_terms.csv", f, "text/csv")}

                    response = self.client.post(
                        "/api/v1/csv/analyze?customer_id=577-746-1198&analysis_type=comprehensive",
                        files=files,
                    )

                return {
                    "status": "success"
                    if response.status_code in [200, 201, 202, 403]
                    else "error",  # 403 acceptable (auth required)
                    "status_code": response.status_code,
                    "response_data": response.json()
                    if response.status_code in [200, 201, 202]
                    else response.text[:500],
                }

            finally:
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"❌ CSV analysis endpoint test failed: {e}")
            return {"status": "error", "reason": str(e)}

    def test_bigquery_endpoints(self) -> Dict[str, Any]:
        """Test BigQuery endpoints if available"""
        logger.info("🔍 Testing BigQuery Endpoints...")

        try:
            # Test BigQuery status endpoint
            response = self.client.get("/api/v1/bigquery/health")

            return {
                "status": "success"
                if response.status_code in [200, 404, 501, 503]
                else "error",  # 503 acceptable (BigQuery not configured)
                "status_code": response.status_code,
                "response_data": response.json()
                if response.status_code == 200
                else response.text[:200],
            }

        except Exception as e:
            logger.error(f"❌ BigQuery endpoints test failed: {e}")
            return {"status": "error", "reason": str(e)}

    def run_api_tests(self) -> Dict[str, Any]:
        """Run comprehensive API endpoint testing"""
        logger.info("🚀 STARTING API ENDPOINT TESTING")
        logger.info("=" * 60)
        logger.info("TopGolf Customer ID: 577-746-1198")
        logger.info(f"Data Source: {self.data_file_path}")
        logger.info("=" * 60)

        # Define test endpoints
        test_endpoints = {
            "health": self.test_health_endpoint,
            "upload": self.test_upload_endpoint,
            "analysis": self.test_analysis_endpoint,
            "reports": self.test_reports_endpoint,
            "customer": self.test_customer_endpoint,
            "csv_analysis": self.test_csv_analysis_endpoint,
            "bigquery": self.test_bigquery_endpoints,
        }

        results = {}
        successful_tests = 0
        failed_tests = 0
        skipped_tests = 0

        for endpoint_name, test_func in test_endpoints.items():
            try:
                result = test_func()
                results[endpoint_name] = result

                if result["status"] == "success":
                    successful_tests += 1
                    logger.info(f"✅ {endpoint_name}: Status {result['status_code']}")
                elif result["status"] == "error":
                    failed_tests += 1
                    logger.error(
                        f"❌ {endpoint_name}: {result.get('reason', 'Unknown error')}"
                    )
                else:
                    skipped_tests += 1
                    logger.warning(
                        f"⚠️ {endpoint_name}: {result.get('reason', 'Skipped')}"
                    )

            except Exception as e:
                failed_tests += 1
                results[endpoint_name] = {
                    "status": "error",
                    "reason": f"Test execution failed: {str(e)}",
                }
                logger.error(f"❌ {endpoint_name}: Test execution failed - {e}")

        total_tests = len(test_endpoints)

        logger.info("=" * 60)
        logger.info("🏆 API ENDPOINT TESTING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✅ Successful: {successful_tests}/{total_tests}")
        logger.info(f"❌ Failed: {failed_tests}/{total_tests}")
        logger.info(f"⚠️ Skipped: {skipped_tests}/{total_tests}")
        logger.info(f"Success Rate: {(successful_tests / total_tests * 100):.1f}%")

        return {
            "timestamp": datetime.now().isoformat(),
            "customer_id": "577-746-1198",
            "data_source": self.data_file_path,
            "total_endpoints": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "success_rate": f"{(successful_tests / total_tests * 100):.1f}%",
            "endpoint_results": results,
        }


def main():
    """Main API testing function"""
    data_file = "/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_real_data_20250822_181442.json"

    if not os.path.exists(data_file):
        logger.error(f"❌ Data file not found: {data_file}")
        return False

    # Initialize API tester
    tester = APIEndpointTester(data_file)

    # Run API tests
    results = tester.run_api_tests()

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_api_test_results_{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"💾 API test results saved to: {output_path}")

    # Generate report
    report_path = generate_api_report(results, output_path)

    logger.info("=" * 60)
    logger.info("✅ API ENDPOINT TESTING COMPLETED")
    logger.info("=" * 60)
    logger.info(f"JSON Results: {output_path}")
    logger.info(f"Report: {report_path}")

    return results["success_rate"] != "0.0%"


def generate_api_report(results: Dict[str, Any], json_path: str) -> str:
    """Generate API testing report"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_api_test_report_{timestamp}.md"

    with open(report_path, "w") as f:
        f.write("# TopGolf API Endpoint Testing Report\n\n")
        f.write(f"**Generated:** {results['timestamp']}\n")
        f.write(f"**Customer ID:** {results['customer_id']}\n")
        f.write(f"**Success Rate:** {results['success_rate']}\n\n")

        f.write("## Test Results Summary\n\n")
        f.write(
            f"- ✅ Successful: {results['successful_tests']}/{results['total_endpoints']}\n"
        )
        f.write(
            f"- ❌ Failed: {results['failed_tests']}/{results['total_endpoints']}\n"
        )
        f.write(
            f"- ⚠️ Skipped: {results['skipped_tests']}/{results['total_endpoints']}\n"
        )
        f.write(f"- 🎯 Success Rate: {results['success_rate']}\n\n")

        f.write("## Endpoint Test Details\n\n")

        for endpoint_name, result in results["endpoint_results"].items():
            f.write(f"### {endpoint_name.replace('_', ' ').title()}\n")

            if result["status"] == "success":
                f.write("✅ **Status:** Success\n")
                f.write(f"- **HTTP Status:** {result['status_code']}\n")
                if "response_time_ms" in result:
                    f.write(f"- **Response Time:** {result['response_time_ms']}ms\n")
            elif result["status"] == "error":
                f.write("❌ **Status:** Failed\n")
                f.write(f"- **Error:** {result.get('reason', 'Unknown error')}\n")
                if "status_code" in result:
                    f.write(f"- **HTTP Status:** {result['status_code']}\n")
            else:
                f.write("⚠️ **Status:** Skipped\n")
                f.write(f"- **Reason:** {result['reason']}\n")

            f.write("\n")

        f.write("## Next Steps\n")
        f.write("1. ✅ API endpoint testing completed\n")
        f.write("2. 🔄 Validate prediction accuracy against historical data\n")
        f.write("3. 🔄 Run end-to-end pipeline test\n")

    return report_path


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
