"""Unit tests for file validation utilities."""

import pytest

from paidsearchnav_mcp.services.file_validation import FileValidator


@pytest.fixture
def file_validator():
    """Create file validator instance."""
    return FileValidator()


@pytest.fixture
def valid_keywords_csv():
    """Valid keywords CSV content."""
    return """Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type
123,456,789,ENABLED,test keyword,EXACT
124,456,790,ENABLED,another keyword,PHRASE
125,457,791,PAUSED,third keyword,BROAD"""


@pytest.fixture
def valid_search_terms_csv():
    """Valid search terms CSV content."""
    return """Search term,Campaign ID,Ad group ID,Impressions,Clicks,Cost
near me dentist,456,789,1000,50,25.50
emergency dental care,456,790,500,30,18.75
dentist open sunday,457,791,250,10,8.25"""


@pytest.fixture
def valid_campaigns_csv():
    """Valid campaigns CSV content."""
    return """Campaign ID,Campaign name,Status,Budget,Campaign type
456,Local Dental Services,ENABLED,100.00,SEARCH
457,Emergency Dental,ENABLED,50.00,SEARCH"""


@pytest.fixture
def valid_ad_groups_csv():
    """Valid ad groups CSV content."""
    return """Ad group ID,Campaign ID,Ad group name,Status
789,456,General Dental,ENABLED
790,456,Emergency Services,ENABLED
791,457,Weekend Hours,PAUSED"""


class TestFileValidator:
    """Test suite for FileValidator."""

    def test_validate_file_size_valid(self, file_validator):
        """Test file size validation with valid size."""
        content = b"x" * 1000
        is_valid, error = file_validator.validate_file_size(content, "test.csv")
        assert is_valid is True
        assert error is None

    def test_validate_file_size_too_small(self, file_validator):
        """Test file size validation with too small file."""
        content = b"x"
        is_valid, error = file_validator.validate_file_size(content, "test.csv")
        assert is_valid is False
        assert "too small" in error

    def test_validate_file_size_too_large(self, file_validator):
        """Test file size validation with too large file."""
        validator = FileValidator(max_file_size=100)
        content = b"x" * 200
        is_valid, error = validator.validate_file_size(content, "test.csv")
        assert is_valid is False
        assert "exceeds maximum size" in error

    def test_validate_file_size_string_content(self, file_validator):
        """Test file size validation with string content."""
        content = "x" * 1000
        is_valid, error = file_validator.validate_file_size(content, "test.csv")
        assert is_valid is True
        assert error is None

    def test_validate_content_type_valid_csv(self, file_validator):
        """Test content type validation for CSV files."""
        is_valid, error = file_validator.validate_content_type("data.csv", "text/csv")
        assert is_valid is True
        assert error is None

    def test_validate_content_type_valid_markdown(self, file_validator):
        """Test content type validation for Markdown files."""
        is_valid, error = file_validator.validate_content_type(
            "report.md", "text/markdown"
        )
        assert is_valid is True
        assert error is None

    def test_validate_content_type_invalid_extension(self, file_validator):
        """Test content type validation with invalid extension."""
        is_valid, error = file_validator.validate_content_type(
            "data.exe", "application/x-executable"
        )
        assert is_valid is False
        assert "not allowed" in error

    def test_validate_content_type_mismatch(self, file_validator):
        """Test content type validation with mismatched type."""
        is_valid, error = file_validator.validate_content_type(
            "data.csv", "application/pdf"
        )
        assert is_valid is False
        assert "not allowed for .csv files" in error

    def test_validate_csv_structure_valid(self, file_validator):
        """Test CSV structure validation with valid data."""
        csv_content = """Name,Age,City
John,30,New York
Jane,25,Los Angeles"""

        result = file_validator.validate_csv_structure(
            csv_content, "test.csv", ["Name", "Age", "City"]
        )

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.file_info["row_count"] == 2
        assert result.file_info["column_count"] == 3

    def test_validate_csv_structure_missing_columns(self, file_validator):
        """Test CSV structure validation with missing columns."""
        csv_content = """Name,City
John,New York
Jane,Los Angeles"""

        result = file_validator.validate_csv_structure(
            csv_content, "test.csv", ["Name", "Age", "City"]
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Missing required columns: Age" in result.errors[0]

    def test_validate_csv_structure_extra_columns(self, file_validator):
        """Test CSV structure validation with extra columns."""
        csv_content = """Name,Age,City,Country
John,30,New York,USA
Jane,25,Los Angeles,USA"""

        result = file_validator.validate_csv_structure(
            csv_content, "test.csv", ["Name", "Age", "City"]
        )

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "Extra columns found: Country" in result.warnings[0]

    def test_validate_csv_structure_empty_file(self, file_validator):
        """Test CSV structure validation with empty file."""
        result = file_validator.validate_csv_structure("", "test.csv", ["Name", "Age"])

        assert result.is_valid is False
        assert "CSV file has no headers" in result.errors[0]

    def test_validate_csv_structure_no_data_rows(self, file_validator):
        """Test CSV structure validation with headers only."""
        csv_content = "Name,Age,City"

        result = file_validator.validate_csv_structure(
            csv_content, "test.csv", ["Name", "Age", "City"]
        )

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert "CSV file has no data rows" in result.warnings[0]

    def test_validate_csv_structure_bytes_content(self, file_validator):
        """Test CSV structure validation with bytes content."""
        csv_content = b"""Name,Age,City
John,30,New York"""

        result = file_validator.validate_csv_structure(
            csv_content, "test.csv", ["Name", "Age", "City"]
        )

        assert result.is_valid is True
        assert result.file_info["row_count"] == 1

    def test_validate_keywords_csv_valid(self, file_validator, valid_keywords_csv):
        """Test keywords CSV validation with valid data."""
        result = file_validator.validate_keywords_csv(valid_keywords_csv)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.file_info["row_count"] == 3

    def test_validate_keywords_csv_invalid(self, file_validator):
        """Test keywords CSV validation with invalid data."""
        invalid_csv = """Wrong,Headers,Here
data1,data2,data3"""

        result = file_validator.validate_keywords_csv(invalid_csv)

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_keywords_csv_large_file_warning(self, file_validator):
        """Test keywords CSV validation with large file warning."""
        header = "Keyword ID,Campaign ID,Ad group ID,Status,Keyword,Match type\n"
        rows = "\n".join(
            [f"{i},456,789,ENABLED,keyword{i},EXACT" for i in range(100001)]
        )
        large_csv = header + rows

        result = file_validator.validate_keywords_csv(large_csv)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "Large file warning" in result.warnings[0]

    def test_validate_search_terms_csv_valid(
        self, file_validator, valid_search_terms_csv
    ):
        """Test search terms CSV validation with valid data."""
        result = file_validator.validate_search_terms_csv(valid_search_terms_csv)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_search_terms_csv_invalid_numeric(self, file_validator):
        """Test search terms CSV validation with invalid numeric values."""
        invalid_csv = """Search term,Campaign ID,Ad group ID,Impressions,Clicks,Cost
near me dentist,456,789,invalid,50,25.50
emergency dental,456,790,500,not_a_number,18.75"""

        result = file_validator.validate_search_terms_csv(invalid_csv)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Invalid numeric value" in str(result.errors)

    def test_validate_search_terms_csv_negative_values(self, file_validator):
        """Test search terms CSV validation with negative values."""
        invalid_csv = """Search term,Campaign ID,Ad group ID,Impressions,Clicks,Cost
near me dentist,456,789,-100,50,25.50
emergency dental,456,790,500,30,-18.75"""

        result = file_validator.validate_search_terms_csv(invalid_csv)

        assert result.is_valid is False
        assert "cannot be negative" in str(result.errors)

    def test_validate_campaigns_csv_valid(self, file_validator, valid_campaigns_csv):
        """Test campaigns CSV validation with valid data."""
        result = file_validator.validate_campaigns_csv(valid_campaigns_csv)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_ad_groups_csv_valid(self, file_validator, valid_ad_groups_csv):
        """Test ad groups CSV validation with valid data."""
        result = file_validator.validate_ad_groups_csv(valid_ad_groups_csv)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_calculate_checksum_sha256(self, file_validator):
        """Test SHA256 checksum calculation."""
        content = b"test content"
        checksum = file_validator.calculate_checksum(content, "sha256")

        assert len(checksum) == 64
        assert (
            checksum
            == "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
        )

    def test_calculate_checksum_md5(self, file_validator):
        """Test MD5 checksum calculation."""
        content = b"test content"
        checksum = file_validator.calculate_checksum(content, "md5")

        assert len(checksum) == 32
        # MD5 hash is deterministic, just verify it's the correct format
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_calculate_checksum_string_content(self, file_validator):
        """Test checksum calculation with string content."""
        content = "test content"
        checksum = file_validator.calculate_checksum(content, "sha256")

        assert len(checksum) == 64

    def test_calculate_checksum_invalid_algorithm(self, file_validator):
        """Test checksum calculation with invalid algorithm."""
        with pytest.raises(ValueError) as exc_info:
            file_validator.calculate_checksum(b"content", "invalid")

        assert "Unsupported hash algorithm" in str(exc_info.value)

    def test_validate_input_file_keywords(self, file_validator, valid_keywords_csv):
        """Test input file validation for keywords type."""
        result = file_validator.validate_input_file(
            valid_keywords_csv, "keywords.csv", "keywords"
        )

        assert result.is_valid is True

    def test_validate_input_file_search_terms(
        self, file_validator, valid_search_terms_csv
    ):
        """Test input file validation for search terms type."""
        result = file_validator.validate_input_file(
            valid_search_terms_csv, "search_terms.csv", "search_terms"
        )

        assert result.is_valid is True

    def test_validate_input_file_campaigns(self, file_validator, valid_campaigns_csv):
        """Test input file validation for campaigns type."""
        result = file_validator.validate_input_file(
            valid_campaigns_csv, "campaigns.csv", "campaigns"
        )

        assert result.is_valid is True

    def test_validate_input_file_ad_groups(self, file_validator, valid_ad_groups_csv):
        """Test input file validation for ad groups type."""
        result = file_validator.validate_input_file(
            valid_ad_groups_csv, "ad_groups.csv", "ad_groups"
        )

        assert result.is_valid is True

    def test_validate_input_file_unknown_type(self, file_validator):
        """Test input file validation with unknown type."""
        # Use a longer content to pass size validation
        result = file_validator.validate_input_file(
            b"content" * 10, "file.csv", "unknown_type"
        )

        assert result.is_valid is False
        assert "Unknown file type" in result.errors[0]

    def test_validate_input_file_size_failure(self, file_validator):
        """Test input file validation with size failure."""
        result = file_validator.validate_input_file(b"x", "file.csv", "keywords")

        assert result.is_valid is False
        assert "too small" in result.errors[0]

    def test_detect_content_type(self, file_validator):
        """Test content type detection."""
        assert file_validator.detect_content_type("file.csv") == "text/csv"
        assert file_validator.detect_content_type("report.md") == "text/markdown"
        assert file_validator.detect_content_type("doc.txt") == "text/plain"
        # The actual mimetype for .xyz files might vary by system
        content_type = file_validator.detect_content_type("unknown.xyz")
        assert content_type in ["application/octet-stream", "chemical/x-xyz"]
