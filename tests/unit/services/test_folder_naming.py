"""Unit tests for folder naming utilities."""

import pytest

from paidsearchnav.core.models.customer_init import BusinessType
from paidsearchnav.services.folder_naming import (
    FolderNamingError,
    PathValidationError,
    create_folder_structure,
    extract_customer_info_from_path,
    generate_business_type_prefix,
    generate_customer_number,
    get_customer_base_path,
    is_valid_customer_path,
    sanitize_customer_name,
    validate_folder_names,
    validate_s3_path,
)


class TestSanitizeCustomerName:
    """Test customer name sanitization."""

    def test_basic_sanitization(self):
        """Test basic name sanitization."""
        assert sanitize_customer_name("Acme Corp") == "acme-corp"
        assert sanitize_customer_name("Test Company Inc.") == "test-company-inc"
        assert sanitize_customer_name("My   Business") == "my-business"

    def test_special_characters(self):
        """Test handling of special characters."""
        assert sanitize_customer_name("Acme & Co.") == "acme-co"
        assert sanitize_customer_name("Test@Company!") == "test-company"
        assert sanitize_customer_name("Company#1$2%3") == "company-1-2-3"

    def test_edge_cases(self):
        """Test edge cases."""
        # Empty or whitespace-only names
        with pytest.raises(FolderNamingError, match="Customer name cannot be empty"):
            sanitize_customer_name("")

        with pytest.raises(FolderNamingError, match="Customer name cannot be empty"):
            sanitize_customer_name("   ")

        # Names with only special characters
        with pytest.raises(FolderNamingError, match="contains no valid characters"):
            sanitize_customer_name("!@#$%")

    def test_reserved_names(self):
        """Test handling of reserved names."""
        assert sanitize_customer_name("admin") == "customer-admin"
        assert sanitize_customer_name("API") == "customer-api"
        assert sanitize_customer_name("ROOT") == "customer-root"

    def test_length_limits(self):
        """Test length limitations."""
        long_name = "a" * 70
        result = sanitize_customer_name(long_name)
        assert len(result) <= 63
        assert not result.endswith("-")

    def test_starts_with_number(self):
        """Test names that start with numbers."""
        assert sanitize_customer_name("123 Company") == "customer-123-company"
        assert sanitize_customer_name("5th Avenue Shop") == "customer-5th-avenue-shop"


class TestGenerateCustomerNumber:
    """Test customer number generation."""

    def test_format(self):
        """Test customer number format."""
        number = generate_customer_number()
        assert len(number) == 12
        assert number.isupper()
        assert number.isalnum()

    def test_uniqueness(self):
        """Test that generated numbers are unique."""
        numbers = [generate_customer_number() for _ in range(100)]
        assert len(set(numbers)) == 100


class TestGenerateBusinessTypePrefix:
    """Test business type prefix generation."""

    def test_all_business_types(self):
        """Test prefix generation for all business types."""
        expected = {
            BusinessType.RETAIL: "ret",
            BusinessType.ECOMMERCE: "ecom",
            BusinessType.SERVICE: "svc",
            BusinessType.SAAS: "saas",
            BusinessType.HEALTHCARE: "hlth",
            BusinessType.AUTOMOTIVE: "auto",
            BusinessType.REAL_ESTATE: "re",
            BusinessType.EDUCATION: "edu",
            BusinessType.NONPROFIT: "npo",
            BusinessType.OTHER: "misc",
        }

        for business_type, expected_prefix in expected.items():
            assert generate_business_type_prefix(business_type) == expected_prefix


class TestCreateFolderStructure:
    """Test folder structure creation."""

    def test_basic_structure(self):
        """Test basic folder structure creation."""
        structure = create_folder_structure(
            "Acme Corp", BusinessType.RETAIL, "TEST12345678"
        )

        assert structure["customer_name_sanitized"] == "acme-corp"
        assert structure["customer_number"] == "TEST12345678"
        assert structure["base_path"] == "ret/acme-corp_TEST12345678"
        assert structure["inputs_path"] == "ret/acme-corp_TEST12345678/inputs"
        assert structure["outputs_path"] == "ret/acme-corp_TEST12345678/outputs"
        assert structure["reports_path"] == "ret/acme-corp_TEST12345678/reports"
        assert (
            structure["actionable_files_path"]
            == "ret/acme-corp_TEST12345678/actionable"
        )

    def test_generated_customer_number(self):
        """Test with generated customer number."""
        structure = create_folder_structure("Test Company", BusinessType.ECOMMERCE)

        assert structure["customer_name_sanitized"] == "test-company"
        assert len(structure["customer_number"]) == 12
        assert structure["base_path"].startswith("ecom/test-company_")

    def test_invalid_inputs(self):
        """Test with invalid inputs."""
        with pytest.raises(FolderNamingError):
            create_folder_structure("", BusinessType.RETAIL)


class TestValidateS3Path:
    """Test S3 path validation."""

    def test_valid_paths(self):
        """Test valid S3 paths."""
        valid_paths = [
            "ret/acme-corp_TEST12345678/inputs",
            "ecom/test-company_ABC456789/outputs",
            "svc/my-service_XYZ7890123/reports",
            "misc/customer-123_DEF000ABC/actionable",
        ]

        for path in valid_paths:
            assert validate_s3_path(path) is True

    def test_invalid_paths(self):
        """Test invalid S3 paths."""
        invalid_cases = [
            ("", "Path cannot be empty"),
            ("//double/slash", "consecutive slashes"),
            ("/starts/with/slash", "start/end with slash"),
            ("ends/with/slash/", "start/end with slash"),
            ("a" * 1025, "Path too long"),  # Exceeds MAX_PATH_LENGTH
            (
                "segment/" + "a" * 64,
                "Path segment too long",
            ),  # Segment exceeds MAX_SEGMENT_LENGTH
            ("invalid/characters!", "invalid characters"),
            ("path/.starts.with.period", "start/end with period"),
            ("path/ends.with.period.", "start/end with period"),
            ("path/-starts-with-hyphen", "start/end with hyphen"),
            ("path/ends-with-hyphen-", "start/end with hyphen"),
        ]

        for path, expected_error in invalid_cases:
            with pytest.raises(PathValidationError, match=expected_error):
                validate_s3_path(path)


class TestValidateFolderNames:
    """Test folder name list validation."""

    def test_all_valid(self):
        """Test with all valid folder names."""
        folders = [
            "ret/acme_TEST12345678/inputs",
            "ecom/test_ABC456789/outputs",
            "svc/service_XYZ7890123/reports",
        ]

        errors = validate_folder_names(folders)
        assert errors == []

    def test_some_invalid(self):
        """Test with some invalid folder names."""
        folders = [
            "ret/acme_TEST12345678/inputs",  # valid
            "invalid/path/!",  # invalid
            "ecom/test_ABC456789/outputs",  # valid
            "/starts/with/slash",  # invalid
        ]

        errors = validate_folder_names(folders)
        assert len(errors) == 2
        assert "Folder 2" in errors[0]
        assert "Folder 4" in errors[1]


class TestGetCustomerBasePath:
    """Test customer base path generation."""

    def test_basic_path(self):
        """Test basic base path generation."""
        path = get_customer_base_path("Acme Corp", BusinessType.RETAIL)

        assert path.startswith("ret/acme-corp_")
        assert len(path.split("_")[1]) == 12

    def test_different_business_types(self):
        """Test with different business types."""
        path_retail = get_customer_base_path("Test", BusinessType.RETAIL)
        path_ecom = get_customer_base_path("Test", BusinessType.ECOMMERCE)

        assert path_retail.startswith("ret/")
        assert path_ecom.startswith("ecom/")


class TestExtractCustomerInfoFromPath:
    """Test customer info extraction from paths."""

    def test_valid_extraction(self):
        """Test extracting info from valid paths."""
        path = "ret/acme-corp_TEST12345678/inputs"
        info = extract_customer_info_from_path(path)

        assert info["business_type_prefix"] == "ret"
        assert info["customer_name"] == "acme-corp"
        assert info["customer_number"] == "TEST12345678"

    def test_base_path_only(self):
        """Test with just the base path."""
        path = "ecom/test-company_ABC12345678"
        info = extract_customer_info_from_path(path)

        assert info["business_type_prefix"] == "ecom"
        assert info["customer_name"] == "test-company"
        assert info["customer_number"] == "ABC12345678"

    def test_invalid_paths(self):
        """Test with invalid paths."""
        invalid_paths = [
            "",
            "single-segment",
            "no_underscore/folder",
            "too/few/underscores",
            "empty//_segment",
        ]

        for path in invalid_paths:
            with pytest.raises(PathValidationError):
                extract_customer_info_from_path(path)


class TestIsValidCustomerPath:
    """Test customer path validity checking."""

    def test_valid_paths(self):
        """Test with valid customer paths."""
        valid_paths = [
            "ret/acme-corp_TEST12345678",
            "ecom/test-company_ABC456789/inputs",
            "svc/my-service_XYZ7890123/outputs/reports",
        ]

        for path in valid_paths:
            assert is_valid_customer_path(path) is True

    def test_invalid_paths(self):
        """Test with invalid customer paths."""
        invalid_paths = [
            "",
            "invalid-format",
            "ret/no-underscore-here",  # No underscore
            "ret/short_12",  # Customer number too short
            "invalid/characters!/test_123",
            "/starts/with/slash_123",
        ]

        for path in invalid_paths:
            assert is_valid_customer_path(path) is False
