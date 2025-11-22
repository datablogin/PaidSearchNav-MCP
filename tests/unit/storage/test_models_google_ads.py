"""Unit tests for Google Ads account models."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from paidsearchnav.storage.models import (
    AnalysisRecord,
    Customer,
    CustomerGoogleAdsAccount,
    GoogleAdsAccount,
    User,
    UserType,
)


class TestGoogleAdsAccount:
    """Test GoogleAdsAccount model."""

    def test_create_google_ads_account(self, session):
        """Test creating a Google Ads account."""
        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Test Account",
            currency_code="USD",
            timezone="America/New_York",
        )
        session.add(account)
        session.commit()

        assert account.id is not None
        assert account.customer_id == "1234567890"
        assert account.account_name == "Test Account"
        assert account.currency_code == "USD"
        assert account.timezone == "America/New_York"
        assert account.is_active is True
        assert account.manager_customer_id is None

    def test_google_ads_account_with_manager(self, session):
        """Test creating a Google Ads account with MCC parent."""
        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Child Account",
            manager_customer_id="9876543210",
            currency_code="EUR",
            timezone="Europe/London",
        )
        session.add(account)
        session.commit()

        assert account.manager_customer_id == "9876543210"

    def test_customer_id_validation(self):
        """Test Google Ads customer ID validation."""
        account = GoogleAdsAccount(
            account_name="Test",
            currency_code="USD",
            timezone="UTC",
        )

        # Valid IDs
        account.customer_id = "1234567"  # 7 digits
        assert account.customer_id == "1234567"

        account.customer_id = "1234567890"  # 10 digits
        assert account.customer_id == "1234567890"

        account.customer_id = "123-456-7890"  # With hyphens
        assert account.customer_id == "1234567890"  # Stored without hyphens

        # Invalid IDs
        with pytest.raises(ValueError, match="Google Ads customer ID cannot be empty"):
            account.customer_id = ""

        with pytest.raises(ValueError, match="must contain only digits and hyphens"):
            account.customer_id = "abc123"

        with pytest.raises(ValueError, match="must be 7-10 digits"):
            account.customer_id = "123456"  # Too short

        with pytest.raises(ValueError, match="must be 7-10 digits"):
            account.customer_id = "12345678901"  # Too long

    def test_manager_customer_id_validation(self):
        """Test manager customer ID validation."""
        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Test",
            currency_code="USD",
            timezone="UTC",
        )

        # None is allowed
        account.manager_customer_id = None
        assert account.manager_customer_id is None

        # Valid manager ID
        account.manager_customer_id = "9876543210"
        assert account.manager_customer_id == "9876543210"

        # Invalid manager ID
        with pytest.raises(
            ValueError, match="Manager customer ID must contain only digits"
        ):
            account.manager_customer_id = "invalid"

    def test_currency_code_validation(self):
        """Test currency code validation."""
        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Test",
            timezone="UTC",
        )

        # Valid currency codes
        account.currency_code = "usd"
        assert account.currency_code == "USD"  # Converted to uppercase

        account.currency_code = "EUR"
        assert account.currency_code == "EUR"

        # Invalid currency codes
        with pytest.raises(
            ValueError, match="Currency code must be exactly 3 characters"
        ):
            account.currency_code = "US"

        with pytest.raises(
            ValueError, match="Currency code must be exactly 3 characters"
        ):
            account.currency_code = "USDD"

    def test_timezone_validation(self):
        """Test timezone validation against pytz."""
        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Test",
            currency_code="USD",
        )

        # Valid timezones
        account.timezone = "America/New_York"
        assert account.timezone == "America/New_York"

        account.timezone = "Europe/London"
        assert account.timezone == "Europe/London"

        account.timezone = "UTC"
        assert account.timezone == "UTC"

        # Invalid timezone
        with pytest.raises(ValueError, match="Invalid timezone"):
            account.timezone = "Invalid/Timezone"

        # Empty timezone
        with pytest.raises(ValueError, match="Timezone cannot be empty"):
            account.timezone = ""

    def test_unique_customer_id_constraint(self, session):
        """Test that customer_id must be unique."""
        account1 = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Account 1",
            currency_code="USD",
            timezone="UTC",
        )
        session.add(account1)
        session.commit()

        account2 = GoogleAdsAccount(
            customer_id="1234567890",  # Same customer ID
            account_name="Account 2",
            currency_code="USD",
            timezone="UTC",
        )
        session.add(account2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_to_dict(self):
        """Test converting to dictionary."""
        account = GoogleAdsAccount(
            id="test-id",
            customer_id="1234567890",
            account_name="Test Account",
            manager_customer_id="9876543210",
            currency_code="USD",
            timezone="America/New_York",
            is_active=True,
        )

        result = account.to_dict()
        assert result["id"] == "test-id"
        assert result["customer_id"] == "1234567890"
        assert result["account_name"] == "Test Account"
        assert result["manager_customer_id"] == "9876543210"
        assert result["currency_code"] == "USD"
        assert result["timezone"] == "America/New_York"
        assert result["is_active"] is True


class TestCustomerEnhancements:
    """Test Customer model enhancements."""

    def test_customer_s3_folder_path(self, session):
        """Test Customer model with S3 folder path."""
        user = User(
            email="test@example.com",
            name="Test User",
            user_type=UserType.INDIVIDUAL.value,
        )
        session.add(user)
        session.commit()

        customer = Customer(
            name="Test Customer",
            user_id=user.id,
            s3_folder_path="s3://bucket/customer-123",
        )
        session.add(customer)
        session.commit()

        assert customer.s3_folder_path == "s3://bucket/customer-123"

    def test_s3_folder_path_validation(self, session):
        """Test S3 folder path validation."""
        user = User(
            email="test@example.com",
            name="Test User",
            user_type=UserType.INDIVIDUAL.value,
        )
        session.add(user)
        session.commit()

        customer = Customer(
            name="Test Customer",
            user_id=user.id,
        )

        # Valid S3 paths
        customer.s3_folder_path = "s3://bucket/path"
        assert customer.s3_folder_path == "s3://bucket/path"

        customer.s3_folder_path = "s3://bucket/path/"
        assert customer.s3_folder_path == "s3://bucket/path"  # Trailing slash removed

        # Invalid S3 paths
        with pytest.raises(ValueError, match="S3 path must start with 's3://'"):
            customer.s3_folder_path = "http://bucket/path"

        with pytest.raises(
            ValueError, match="S3 path cannot contain '\\.\\.' for security reasons"
        ):
            customer.s3_folder_path = "s3://bucket/../path"

    def test_customer_google_ads_accounts_relationship(self, session):
        """Test Customer relationship with Google Ads accounts."""
        user = User(
            email="test@example.com",
            name="Test User",
            user_type=UserType.INDIVIDUAL.value,
        )
        session.add(user)
        session.commit()  # Commit user first

        customer = Customer(
            name="Test Customer",
            user_id=user.id,
        )
        session.add(customer)
        session.commit()

        # Create Google Ads accounts
        account1 = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Account 1",
            currency_code="USD",
            timezone="UTC",
        )
        account2 = GoogleAdsAccount(
            customer_id="0987654321",
            account_name="Account 2",
            currency_code="EUR",
            timezone="UTC",
        )
        session.add_all([account1, account2])
        session.commit()

        # Create junction records
        junction1 = CustomerGoogleAdsAccount(
            customer_id=customer.id,
            google_ads_account_id=account1.id,
            account_role="owner",
            s3_folder_path="s3://bucket/customer/account1",
        )
        junction2 = CustomerGoogleAdsAccount(
            customer_id=customer.id,
            google_ads_account_id=account2.id,
            account_role="manager",
            s3_folder_path="s3://bucket/customer/account2",
        )
        session.add_all([junction1, junction2])
        session.commit()

        # Refresh and check relationships
        session.refresh(customer)
        assert len(customer.google_ads_accounts) == 2


class TestCustomerGoogleAdsAccount:
    """Test CustomerGoogleAdsAccount junction table."""

    def test_create_junction_record(self, session):
        """Test creating a junction record."""
        # Create user and customer
        user = User(
            email="test@example.com",
            name="Test User",
            user_type=UserType.INDIVIDUAL.value,
        )
        session.add(user)
        session.commit()

        customer = Customer(
            name="Test Customer",
            user_id=user.id,
        )
        session.add(customer)
        session.commit()

        # Create Google Ads account
        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Test Account",
            currency_code="USD",
            timezone="UTC",
        )
        session.add(account)
        session.commit()

        # Create junction record
        junction = CustomerGoogleAdsAccount(
            customer_id=customer.id,
            google_ads_account_id=account.id,
            account_role="owner",
            s3_folder_path="s3://bucket/customer/account",
        )
        session.add(junction)
        session.commit()

        assert junction.customer_id == customer.id
        assert junction.google_ads_account_id == account.id
        assert junction.account_role == "owner"
        assert junction.s3_folder_path == "s3://bucket/customer/account"
        assert junction.created_at is not None

    def test_account_role_validation(self, session):
        """Test account role validation."""
        junction = CustomerGoogleAdsAccount(
            customer_id="cust-123",
            google_ads_account_id="acc-123",
            s3_folder_path="s3://bucket/path",
        )

        # Valid roles
        for role in ["owner", "manager", "viewer"]:
            junction.account_role = role
            assert junction.account_role == role

        # Invalid role
        with pytest.raises(ValueError, match="Invalid account role"):
            junction.account_role = "admin"

    def test_s3_folder_path_validation(self):
        """Test S3 folder path validation in junction table."""
        junction = CustomerGoogleAdsAccount(
            customer_id="cust-123",
            google_ads_account_id="acc-123",
            account_role="owner",
        )

        # Valid paths
        junction.s3_folder_path = "s3://bucket/path"
        assert junction.s3_folder_path == "s3://bucket/path"

        # Invalid paths
        with pytest.raises(ValueError, match="S3 folder path cannot be empty"):
            junction.s3_folder_path = ""

        with pytest.raises(ValueError, match="S3 path must start with 's3://'"):
            junction.s3_folder_path = "http://bucket/path"

    def test_composite_primary_key(self, session):
        """Test composite primary key constraint."""
        # Create prerequisites
        user = User(
            email="test@example.com",
            name="Test User",
            user_type=UserType.INDIVIDUAL.value,
        )
        session.add(user)
        session.commit()

        customer = Customer(
            name="Test Customer",
            user_id=user.id,
        )
        session.add(customer)
        session.commit()

        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Test Account",
            currency_code="USD",
            timezone="UTC",
        )
        session.add(account)
        session.commit()

        # Create first junction
        junction1 = CustomerGoogleAdsAccount(
            customer_id=customer.id,
            google_ads_account_id=account.id,
            account_role="owner",
            s3_folder_path="s3://bucket/path",
        )
        session.add(junction1)
        session.commit()

        # Try to create duplicate
        junction2 = CustomerGoogleAdsAccount(
            customer_id=customer.id,
            google_ads_account_id=account.id,
            account_role="viewer",
            s3_folder_path="s3://bucket/path2",
        )
        session.add(junction2)

        with pytest.raises(IntegrityError):
            session.commit()


class TestAnalysisRecordEnhancements:
    """Test AnalysisRecord model enhancements."""

    def test_analysis_record_with_google_ads_account(self, session):
        """Test AnalysisRecord with Google Ads account reference."""
        # Create Google Ads account
        account = GoogleAdsAccount(
            customer_id="1234567890",
            account_name="Test Account",
            currency_code="USD",
            timezone="UTC",
        )
        session.add(account)
        session.commit()

        # Create analysis record
        analysis = AnalysisRecord(
            customer_id="1234567890",
            google_ads_account_id=account.id,
            analysis_type="search_terms",
            analyzer_name="SearchTermsAnalyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            result_data={"recommendations": []},
        )
        session.add(analysis)
        session.commit()

        assert analysis.google_ads_account_id == account.id
        assert analysis.google_ads_account == account

    def test_analysis_record_s3_paths(self, session):
        """Test AnalysisRecord with S3 paths."""
        analysis = AnalysisRecord(
            customer_id="1234567890",
            analysis_type="search_terms",
            analyzer_name="SearchTermsAnalyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            s3_input_path="s3://bucket/input/data.csv",
            s3_output_path="s3://bucket/output/results.json",
            result_data={"recommendations": []},
        )
        session.add(analysis)
        session.commit()

        assert analysis.s3_input_path == "s3://bucket/input/data.csv"
        assert analysis.s3_output_path == "s3://bucket/output/results.json"

    def test_s3_path_validation(self):
        """Test S3 path validation for AnalysisRecord."""
        analysis = AnalysisRecord(
            customer_id="1234567890",
            analysis_type="test",
            analyzer_name="TestAnalyzer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            result_data={},
        )

        # Valid paths
        analysis.s3_input_path = "s3://bucket/file.csv"
        assert analysis.s3_input_path == "s3://bucket/file.csv"

        # Invalid paths
        with pytest.raises(
            ValueError, match="s3_input_path: S3 path must start with 's3://'"
        ):
            analysis.s3_input_path = "http://bucket/file.csv"

        with pytest.raises(
            ValueError,
            match="s3_output_path: S3 path cannot contain '\\.\\.' for security reasons",
        ):
            analysis.s3_output_path = "s3://bucket/../file.csv"

    def test_analysis_record_metadata(self, session):
        """Test AnalysisRecord with run metadata."""
        metadata = {
            "version": "1.0",
            "parameters": {"threshold": 0.5},
            "execution_time": 120.5,
        }

        analysis = AnalysisRecord(
            customer_id="1234567890",
            analysis_type="test",
            analyzer_name="TestAnalyzer",
            start_date=datetime.now(),
            end_date=datetime.now(),
            run_metadata=metadata,
            result_data={"recommendations": []},
        )
        session.add(analysis)
        session.commit()

        assert analysis.run_metadata == metadata
        assert analysis.run_metadata["version"] == "1.0"
        assert analysis.run_metadata["execution_time"] == 120.5

    def test_enhanced_to_dict(self):
        """Test enhanced to_dict method."""
        analysis = AnalysisRecord(
            id="test-id",
            customer_id="1234567890",
            google_ads_account_id="gads-123",
            analysis_type="search_terms",
            analyzer_name="SearchTermsAnalyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            s3_input_path="s3://bucket/input.csv",
            s3_output_path="s3://bucket/output.json",
            audit_id="audit-123",
            run_metadata={"version": "1.0"},
            result_data={"recommendations": []},
        )

        result = analysis.to_dict()
        assert result["id"] == "test-id"
        assert result["google_ads_account_id"] == "gads-123"
        assert result["s3_input_path"] == "s3://bucket/input.csv"
        assert result["s3_output_path"] == "s3://bucket/output.json"
        assert result["audit_id"] == "audit-123"
        assert result["run_metadata"] == {"version": "1.0"}
