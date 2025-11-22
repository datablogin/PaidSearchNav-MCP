"""Unit tests for customer initialization service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from paidsearchnav.core.models.customer_init import (
    BusinessType,
    CustomerInitRequest,
    InitializationStatus,
)
from paidsearchnav.services.customer_initialization import (
    CustomerInitializationError,
    CustomerInitializationService,
    GoogleAdsInitializationError,
    S3InitializationError,
)


class TestCustomerInitializationService:
    """Test CustomerInitializationService class."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        mock_client = MagicMock()
        mock_client.put_object.return_value = {}
        mock_client.get_paginator.return_value.paginate.return_value = []
        mock_client.delete_objects.return_value = {}
        return mock_client

    @pytest.fixture
    def mock_google_ads_client(self):
        """Create a mock Google Ads client."""
        return AsyncMock()

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.flush = AsyncMock()
        return mock_session

    @pytest.fixture
    def service(self, mock_s3_client, mock_google_ads_client):
        """Create a customer initialization service instance."""
        return CustomerInitializationService(
            s3_client=mock_s3_client,
            google_ads_client=mock_google_ads_client,
            bucket_name="test-bucket",
        )

    @pytest.fixture
    def sample_request(self):
        """Create a sample customer initialization request."""
        return CustomerInitRequest(
            name="Acme Corp",
            email="contact@acme.com",
            business_type=BusinessType.RETAIL,
            google_ads_customer_ids=["1234567890"],
            contact_person="John Doe",
            phone="555-123-4567",
        )

    async def test_successful_initialization(
        self, service, sample_request, mock_session
    ):
        """Test successful customer initialization."""
        # Mock the repository
        with patch(
            "paidsearchnav.services.customer_initialization.CustomerRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            # Mock the customer object returned from the database
            mock_customer = MagicMock()
            mock_customer.google_ads_customer_id = "1234567890"  # Valid 10-digit ID
            mock_repo.get_by_id.return_value = mock_customer
            mock_repo_class.return_value = mock_repo

            response = await service.initialize_customer(
                request=sample_request, user_id="user_123", session=mock_session
            )

        assert response.success is True
        assert response.initialization_status == InitializationStatus.COMPLETED
        assert response.customer_record is not None
        assert response.s3_structure is not None
        assert len(response.google_ads_links) > 0
        assert len(response.errors) == 0
        assert response.duration_seconds > 0

    async def test_s3_creation_failure(self, service, sample_request, mock_session):
        """Test S3 folder creation failure."""
        # Make S3 client raise an error
        service.s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
            "PutObject",
        )

        response = await service.initialize_customer(
            request=sample_request, user_id="user_123", session=mock_session
        )

        assert response.success is False
        assert response.initialization_status == InitializationStatus.FAILED
        assert len(response.errors) > 0
        assert "Failed to create S3 structure" in response.errors[0]

    async def test_google_ads_validation_no_client(
        self, mock_s3_client, sample_request, mock_session
    ):
        """Test Google Ads validation with no client."""
        service = CustomerInitializationService(
            s3_client=mock_s3_client, google_ads_client=None, bucket_name="test-bucket"
        )

        with patch("paidsearchnav.services.customer_initialization.CustomerRepository"):
            response = await service.initialize_customer(
                request=sample_request, user_id="user_123", session=mock_session
            )

        assert response.success is True
        assert len(response.warnings) > 0
        assert "Google Ads client not available" in response.warnings[0]

    async def test_database_creation_failure(
        self, service, sample_request, mock_session
    ):
        """Test database record creation failure."""
        # Make session commit raise an error
        mock_session.commit.side_effect = Exception("Database error")

        response = await service.initialize_customer(
            request=sample_request, user_id="user_123", session=mock_session
        )

        assert response.success is False
        assert response.initialization_status == InitializationStatus.FAILED
        assert len(response.errors) > 0
        assert mock_session.rollback.called

    @patch("paidsearchnav.services.customer_initialization.create_folder_structure")
    async def test_create_s3_structure_success(
        self, mock_create_structure, service, sample_request
    ):
        """Test successful S3 structure creation."""
        mock_create_structure.return_value = {
            "base_path": "ret/acme-corp_TEST123",
            "customer_name_sanitized": "acme-corp",
            "customer_number": "TEST123",
            "inputs_path": "ret/acme-corp_TEST123/inputs",
            "outputs_path": "ret/acme-corp_TEST123/outputs",
            "reports_path": "ret/acme-corp_TEST123/reports",
            "actionable_files_path": "ret/acme-corp_TEST123/actionable",
        }

        s3_structure = await service._create_s3_structure(sample_request, "cust_123")

        assert s3_structure.base_path == "ret/acme-corp_TEST123"
        assert s3_structure.customer_name_sanitized == "acme-corp"
        assert len(s3_structure.created_folders) == 4
        assert service.s3_client.put_object.call_count == 4

    async def test_create_s3_structure_failure(self, service, sample_request):
        """Test S3 structure creation failure."""
        service.s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "PutObject"
        )

        with pytest.raises(
            S3InitializationError, match="Failed to create S3 structure"
        ):
            await service._create_s3_structure(sample_request, "cust_123")

    async def test_validate_google_ads_accounts_success(self, service):
        """Test successful Google Ads account validation."""
        # Mock the Google Ads account info method
        service._get_google_ads_account_info = AsyncMock(
            return_value={
                "name": "Test Account",
                "currency_code": "USD",
                "time_zone": "America/New_York",
                "account_type": "STANDARD",
            }
        )

        links = await service._validate_google_ads_accounts(
            ["1234567890", "098-765-4321"]
        )

        assert len(links) == 2
        assert all(link.accessible for link in links)
        assert all(link.link_status == "active" for link in links)
        assert links[0].customer_id == "1234567890"
        assert links[1].customer_id == "0987654321"  # Hyphens removed

    async def test_validate_google_ads_accounts_no_client(self, mock_s3_client):
        """Test Google Ads validation without client."""
        service = CustomerInitializationService(
            s3_client=mock_s3_client, google_ads_client=None
        )

        with pytest.raises(
            GoogleAdsInitializationError, match="Google Ads client not available"
        ):
            await service._validate_google_ads_accounts(["1234567890"])

    async def test_validate_google_ads_accounts_api_error(self, service):
        """Test Google Ads validation with API errors."""
        # Mock the Google Ads account info method to raise an error
        service._get_google_ads_account_info = AsyncMock(
            side_effect=Exception("API error")
        )

        links = await service._validate_google_ads_accounts(["1234567890"])

        assert len(links) == 1
        assert links[0].accessible is False
        assert links[0].link_status == "error"
        assert len(links[0].validation_errors) == 1
        assert "API error" in links[0].validation_errors[0]

    async def test_get_google_ads_account_info(self, service):
        """Test getting Google Ads account information."""
        info = await service._get_google_ads_account_info("1234567890")

        assert "name" in info
        assert "currency_code" in info
        assert "time_zone" in info
        assert "account_type" in info
        assert info["name"] == "Account 1234567890"

    async def test_create_customer_record(self, service, sample_request, mock_session):
        """Test customer record creation."""
        from paidsearchnav.core.models.customer_init import (
            GoogleAdsAccountLink,
            S3FolderStructure,
        )

        s3_structure = S3FolderStructure(
            base_path="ret/acme-corp_TEST123",
            customer_name_sanitized="acme-corp",
            customer_number="TEST123",
            inputs_path="ret/acme-corp_TEST123/inputs",
            outputs_path="ret/acme-corp_TEST123/outputs",
            reports_path="ret/acme-corp_TEST123/reports",
            actionable_files_path="ret/acme-corp_TEST123/actionable",
        )

        google_ads_links = [
            GoogleAdsAccountLink(customer_id="1234567890", account_name="Test Account")
        ]

        record = await service._create_customer_record(
            request=sample_request,
            customer_id="cust_123",
            user_id="user_123",
            s3_structure=s3_structure,
            google_ads_links=google_ads_links,
            session=mock_session,
        )

        assert record.customer_id == "cust_123"
        assert record.name == "Acme Corp"
        assert record.s3_base_path == "ret/acme-corp_TEST123"
        assert len(record.google_ads_accounts) == 1
        assert mock_session.add.called
        assert mock_session.commit.called

    async def test_create_customer_record_database_error(
        self, service, sample_request, mock_session
    ):
        """Test customer record creation with database error."""
        from paidsearchnav.core.models.customer_init import S3FolderStructure

        s3_structure = S3FolderStructure(
            base_path="ret/acme-corp_TEST123",
            customer_name_sanitized="acme-corp",
            customer_number="TEST123",
            inputs_path="ret/acme-corp_TEST123/inputs",
            outputs_path="ret/acme-corp_TEST123/outputs",
            reports_path="ret/acme-corp_TEST123/reports",
            actionable_files_path="ret/acme-corp_TEST123/actionable",
        )

        mock_session.commit.side_effect = Exception("Database error")

        with pytest.raises(
            CustomerInitializationError, match="Failed to create customer record"
        ):
            await service._create_customer_record(
                request=sample_request,
                customer_id="cust_123",
                user_id="user_123",
                s3_structure=s3_structure,
                google_ads_links=[],
                session=mock_session,
            )

        assert mock_session.rollback.called

    async def test_verify_customer_setup_success(self, service, mock_session):
        """Test successful customer setup verification."""
        with patch(
            "paidsearchnav.services.customer_initialization.CustomerRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_customer = MagicMock()
            mock_customer.google_ads_customer_id = "1234567890"
            mock_repo.get_by_id.return_value = mock_customer
            mock_repo_class.return_value = mock_repo

            result = await service._verify_customer_setup("cust_123", mock_session)

        assert result.valid is True
        assert result.customer_exists is True
        assert result.s3_structure_valid is True
        assert result.google_ads_links_valid is True
        assert result.database_consistent is True
        assert len(result.errors) == 0

    async def test_verify_customer_setup_customer_not_found(
        self, service, mock_session
    ):
        """Test customer setup verification when customer not found."""
        with patch(
            "paidsearchnav.services.customer_initialization.CustomerRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = None
            mock_repo_class.return_value = mock_repo

            result = await service._verify_customer_setup("cust_123", mock_session)

        assert result.valid is False
        assert result.customer_exists is False
        assert len(result.errors) == 1
        assert "Customer database record not found" in result.errors[0]

    async def test_verify_customer_setup_invalid_google_ads(
        self, service, mock_session
    ):
        """Test customer setup verification with invalid Google Ads ID."""
        with patch(
            "paidsearchnav.services.customer_initialization.CustomerRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_customer = MagicMock()
            mock_customer.google_ads_customer_id = "123"  # Too short
            mock_repo.get_by_id.return_value = mock_customer
            mock_repo_class.return_value = mock_repo

            result = await service._verify_customer_setup("cust_123", mock_session)

        assert result.valid is False
        assert result.google_ads_links_valid is False
        assert any(
            "Invalid Google Ads customer ID format" in error for error in result.errors
        )

    async def test_rollback_initialization(self, service, mock_session):
        """Test initialization rollback."""
        from paidsearchnav.core.models.customer_init import S3FolderStructure

        s3_structure = S3FolderStructure(
            base_path="ret/acme-corp_TEST123",
            customer_name_sanitized="acme-corp",
            customer_number="TEST123",
            inputs_path="ret/acme-corp_TEST123/inputs",
            outputs_path="ret/acme-corp_TEST123/outputs",
            reports_path="ret/acme-corp_TEST123/reports",
            actionable_files_path="ret/acme-corp_TEST123/actionable",
        )

        # Mock the paginator for S3 cleanup
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "test/file.txt"}]}
        ]
        service.s3_client.get_paginator.return_value = mock_paginator

        await service._rollback_initialization("cust_123", s3_structure, mock_session)

        assert mock_session.rollback.called
        assert service.s3_client.delete_objects.called

    async def test_cleanup_s3_structure(self, service):
        """Test S3 structure cleanup."""
        from paidsearchnav.core.models.customer_init import S3FolderStructure

        s3_structure = S3FolderStructure(
            base_path="ret/acme-corp_TEST123",
            customer_name_sanitized="acme-corp",
            customer_number="TEST123",
            inputs_path="ret/acme-corp_TEST123/inputs",
            outputs_path="ret/acme-corp_TEST123/outputs",
            reports_path="ret/acme-corp_TEST123/reports",
            actionable_files_path="ret/acme-corp_TEST123/actionable",
        )

        # Mock paginator response
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "ret/acme-corp_TEST123/inputs/.folder_marker"},
                    {"Key": "ret/acme-corp_TEST123/outputs/.folder_marker"},
                ]
            }
        ]
        service.s3_client.get_paginator.return_value = mock_paginator

        await service._cleanup_s3_structure(s3_structure)

        assert service.s3_client.get_paginator.called
        assert service.s3_client.delete_objects.called

        # Verify delete_objects was called with correct parameters
        delete_call = service.s3_client.delete_objects.call_args
        assert delete_call[1]["Bucket"] == "test-bucket"
        assert len(delete_call[1]["Delete"]["Objects"]) == 2

    async def test_cleanup_s3_structure_error(self, service):
        """Test S3 structure cleanup with error."""
        from paidsearchnav.core.models.customer_init import S3FolderStructure

        s3_structure = S3FolderStructure(
            base_path="ret/acme-corp_TEST123",
            customer_name_sanitized="acme-corp",
            customer_number="TEST123",
            inputs_path="ret/acme-corp_TEST123/inputs",
            outputs_path="ret/acme-corp_TEST123/outputs",
            reports_path="ret/acme-corp_TEST123/reports",
            actionable_files_path="ret/acme-corp_TEST123/actionable",
        )

        # Make the paginator raise an error
        service.s3_client.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
            "ListObjectsV2",
        )

        with pytest.raises(
            S3InitializationError, match="Failed to cleanup S3 structure"
        ):
            await service._cleanup_s3_structure(s3_structure)

    def test_get_initialization_progress(self, service):
        """Test getting initialization progress."""
        # This is a placeholder method currently
        progress = service.get_initialization_progress("cust_123")
        assert progress is None

    async def test_validate_customer_initialization(self, service, mock_session):
        """Test validating customer initialization."""
        with patch(
            "paidsearchnav.services.customer_initialization.CustomerRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_customer = MagicMock()
            mock_customer.google_ads_customer_id = "1234567890"
            mock_repo.get_by_id.return_value = mock_customer
            mock_repo_class.return_value = mock_repo

            result = await service.validate_customer_initialization(
                "cust_123", mock_session
            )

        assert result.valid is True
        assert result.customer_exists is True
