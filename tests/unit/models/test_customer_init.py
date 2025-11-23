"""Unit tests for customer initialization models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.models.customer_init import (
    BusinessType,
    CustomerInitRequest,
    CustomerRecord,
    GoogleAdsAccountLink,
    InitializationProgress,
    InitializationStatus,
    S3FolderStructure,
    ValidationResult,
    generate_customer_id,
    generate_customer_number,
)


class TestBusinessType:
    """Test BusinessType enum."""

    def test_all_values(self):
        """Test all business type values."""
        expected_values = {
            "retail",
            "ecommerce",
            "service",
            "saas",
            "healthcare",
            "automotive",
            "real_estate",
            "education",
            "nonprofit",
            "other",
        }

        actual_values = {bt.value for bt in BusinessType}
        assert actual_values == expected_values


class TestInitializationStatus:
    """Test InitializationStatus enum."""

    def test_all_values(self):
        """Test all initialization status values."""
        expected_values = {
            "pending",
            "in_progress",
            "completed",
            "failed",
            "rolled_back",
        }

        actual_values = {status.value for status in InitializationStatus}
        assert actual_values == expected_values


class TestCustomerInitRequest:
    """Test CustomerInitRequest model."""

    def test_valid_request(self):
        """Test creating a valid customer initialization request."""
        request = CustomerInitRequest(
            name="Acme Corp",
            email="contact@acme.com",
            business_type=BusinessType.RETAIL,
            google_ads_customer_ids=["1234567890"],
            contact_person="John Doe",
            phone="555-123-4567",
            company_website="https://acme.com",
            notes="Test customer",
        )

        assert request.name == "Acme Corp"
        assert request.email == "contact@acme.com"
        assert request.business_type == BusinessType.RETAIL
        assert request.google_ads_customer_ids == ["1234567890"]
        assert request.contact_person == "John Doe"
        assert request.phone == "555-123-4567"
        assert request.company_website == "https://acme.com"
        assert request.notes == "Test customer"

    def test_minimal_request(self):
        """Test request with only required fields."""
        request = CustomerInitRequest(
            name="Test Company",
            email="test@example.com",
            business_type=BusinessType.SERVICE,
            google_ads_customer_ids=["9876543210"],
        )

        assert request.name == "Test Company"
        assert request.contact_person is None
        assert request.phone is None
        assert request.company_website is None
        assert request.notes is None

    def test_name_validation(self):
        """Test name field validation."""
        # Empty name
        with pytest.raises(
            ValidationError, match="String should have at least 1 character"
        ):
            CustomerInitRequest(
                name="",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["1234567890"],
            )

        # Name too long
        long_name = "a" * 101
        with pytest.raises(
            ValidationError, match="String should have at most 100 characters"
        ):
            CustomerInitRequest(
                name=long_name,
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["1234567890"],
            )

    def test_email_validation(self):
        """Test email field validation."""
        with pytest.raises(ValidationError, match="Invalid email format"):
            CustomerInitRequest(
                name="Test Company",
                email="invalid-email",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["1234567890"],
            )

    def test_google_ads_customer_ids_validation(self):
        """Test Google Ads customer ID validation."""
        # Empty list
        with pytest.raises(ValidationError, match="at least 1"):
            CustomerInitRequest(
                name="Test Company",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=[],
            )

        # Invalid format - too short
        with pytest.raises(ValidationError, match="Must be 10 digits"):
            CustomerInitRequest(
                name="Test Company",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["123456"],
            )

        # Invalid format - too long
        with pytest.raises(ValidationError, match="Must be 10 digits"):
            CustomerInitRequest(
                name="Test Company",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["12345678901"],
            )

        # Invalid format - non-numeric
        with pytest.raises(ValidationError, match="Must be 10 digits"):
            CustomerInitRequest(
                name="Test Company",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["abcd567890"],
            )

        # Valid format with hyphens
        request = CustomerInitRequest(
            name="Test Company",
            email="test@example.com",
            business_type=BusinessType.RETAIL,
            google_ads_customer_ids=["123-456-7890"],
        )
        assert request.google_ads_customer_ids == ["123-456-7890"]

    def test_phone_validation(self):
        """Test phone number validation."""
        # Too short
        with pytest.raises(ValidationError, match="between 10 and 15 digits"):
            CustomerInitRequest(
                name="Test Company",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["1234567890"],
                phone="123456789",
            )

        # Too long
        with pytest.raises(ValidationError, match="between 10 and 15 digits"):
            CustomerInitRequest(
                name="Test Company",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["1234567890"],
                phone="1234567890123456",
            )

        # Valid phone numbers
        valid_phones = [
            "555-123-4567",
            "(555) 123-4567",
            "555.123.4567",
            "15551234567",
            "+1-555-123-4567",
        ]

        for phone in valid_phones:
            request = CustomerInitRequest(
                name="Test Company",
                email="test@example.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=["1234567890"],
                phone=phone,
            )
            assert request.phone == phone


class TestS3FolderStructure:
    """Test S3FolderStructure model."""

    def test_valid_structure(self):
        """Test creating a valid S3 folder structure."""
        structure = S3FolderStructure(
            base_path="ret/acme-corp_TEST123",
            customer_name_sanitized="acme-corp",
            customer_number="TEST123",
            inputs_path="ret/acme-corp_TEST123/inputs",
            outputs_path="ret/acme-corp_TEST123/outputs",
            reports_path="ret/acme-corp_TEST123/reports",
            actionable_files_path="ret/acme-corp_TEST123/actionable",
            created_folders=[
                "ret/acme-corp_TEST123/inputs",
                "ret/acme-corp_TEST123/outputs",
            ],
        )

        assert structure.base_path == "ret/acme-corp_TEST123"
        assert structure.customer_name_sanitized == "acme-corp"
        assert structure.customer_number == "TEST123"
        assert len(structure.created_folders) == 2


class TestGoogleAdsAccountLink:
    """Test GoogleAdsAccountLink model."""

    def test_valid_link(self):
        """Test creating a valid Google Ads account link."""
        link = GoogleAdsAccountLink(
            customer_id="1234567890",
            account_name="Test Account",
            currency_code="USD",
            time_zone="America/New_York",
            account_type="STANDARD",
            accessible=True,
            link_status="active",
        )

        assert link.customer_id == "1234567890"
        assert link.account_name == "Test Account"
        assert link.accessible is True
        assert link.link_status == "active"
        assert len(link.validation_errors) == 0

    def test_minimal_link(self):
        """Test link with minimal required fields."""
        link = GoogleAdsAccountLink(
            customer_id="1234567890", account_name="Test Account"
        )

        assert link.accessible is True
        assert link.link_status == "active"
        assert len(link.validation_errors) == 0

    def test_with_errors(self):
        """Test link with validation errors."""
        link = GoogleAdsAccountLink(
            customer_id="1234567890",
            account_name="Test Account",
            accessible=False,
            link_status="error",
            validation_errors=["Account not found", "Permission denied"],
        )

        assert link.accessible is False
        assert link.link_status == "error"
        assert len(link.validation_errors) == 2


class TestCustomerRecord:
    """Test CustomerRecord model."""

    def test_valid_record(self):
        """Test creating a valid customer record."""
        google_ads_links = [
            GoogleAdsAccountLink(customer_id="1234567890", account_name="Test Account")
        ]

        record = CustomerRecord(
            customer_id="cust_123",
            name="Acme Corp",
            name_sanitized="acme-corp",
            email="contact@acme.com",
            business_type=BusinessType.RETAIL,
            contact_person="John Doe",
            phone="555-123-4567",
            company_website="https://acme.com",
            notes="Test customer",
            s3_base_path="ret/acme-corp_TEST123",
            s3_bucket_name="test-bucket",
            initialization_status=InitializationStatus.COMPLETED,
            google_ads_accounts=google_ads_links,
        )

        assert record.customer_id == "cust_123"
        assert record.name == "Acme Corp"
        assert record.initialization_status == InitializationStatus.COMPLETED
        assert len(record.google_ads_accounts) == 1
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)

    def test_defaults(self):
        """Test default values."""
        record = CustomerRecord(
            customer_id="cust_123",
            name="Test Company",
            name_sanitized="test-company",
            email="test@example.com",
            business_type=BusinessType.SERVICE,
            s3_base_path="svc/test-company_ABC123",
        )

        assert record.initialization_status == InitializationStatus.PENDING
        assert len(record.google_ads_accounts) == 0
        assert record.s3_bucket_name is None
        assert record.contact_person is None


class TestInitializationProgress:
    """Test InitializationProgress model."""

    def test_valid_progress(self):
        """Test creating valid initialization progress."""
        progress = InitializationProgress(
            customer_id="cust_123",
            current_step="Creating S3 structure",
            total_steps=5,
            completed_steps=2,
            status=InitializationStatus.IN_PROGRESS,
            details={"s3_folders": "created", "google_ads": "pending"},
        )

        assert progress.customer_id == "cust_123"
        assert progress.current_step == "Creating S3 structure"
        assert progress.total_steps == 5
        assert progress.completed_steps == 2
        assert progress.status == InitializationStatus.IN_PROGRESS
        assert isinstance(progress.last_update, datetime)
        assert len(progress.details) == 2


class TestValidationResult:
    """Test ValidationResult model."""

    def test_successful_validation(self):
        """Test successful validation result."""
        result = ValidationResult(
            valid=True,
            customer_exists=True,
            s3_structure_valid=True,
            google_ads_links_valid=True,
            database_consistent=True,
        )

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert isinstance(result.validation_timestamp, datetime)

    def test_failed_validation(self):
        """Test failed validation result."""
        result = ValidationResult(
            valid=False,
            customer_exists=False,
            s3_structure_valid=True,
            google_ads_links_valid=False,
            database_consistent=False,
            errors=["Customer not found", "Invalid Google Ads links"],
            warnings=["S3 structure exists but may be incomplete"],
        )

        assert result.valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


class TestUtilityFunctions:
    """Test utility functions."""

    def test_generate_customer_number(self):
        """Test customer number generation."""
        number = generate_customer_number()
        assert len(number) == 12
        assert number.isupper()
        assert number.isalnum()

    def test_generate_customer_id(self):
        """Test customer ID generation."""
        customer_id = generate_customer_id()
        assert customer_id.startswith("cust_")
        assert len(customer_id) > 10  # UUID adds significant length

    def test_unique_generation(self):
        """Test that generated IDs are unique."""
        numbers = [generate_customer_number() for _ in range(50)]
        assert len(set(numbers)) == 50

        ids = [generate_customer_id() for _ in range(50)]
        assert len(set(ids)) == 50
