"""Integration tests for customer initialization service."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from paidsearchnav_mcp.models.customer_init import (
    BusinessType,
    CustomerInitRequest,
    InitializationStatus,
)
from paidsearchnav_mcp.services.customer_initialization import CustomerInitializationService
from paidsearchnav_mcp.storage.models import Base, User


class TestCustomerInitializationIntegration:
    """Integration tests for the complete customer initialization flow."""

    @pytest.fixture
    async def test_database(self):
        """Create a test database."""
        # Create a temporary SQLite database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            # Create async engine
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)

            # Create tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Create session factory
            AsyncSessionLocal = sessionmaker(
                bind=engine, class_=AsyncSession, expire_on_commit=False
            )

            yield engine, AsyncSessionLocal

        finally:
            # Clean up
            await engine.dispose()
            Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client that simulates successful operations."""
        client = MagicMock()

        # Mock put_object to succeed
        client.put_object.return_value = {}

        # Mock paginator for cleanup
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "test/folder1/.folder_marker"},
                    {"Key": "test/folder2/.folder_marker"},
                ]
            }
        ]
        client.get_paginator.return_value = mock_paginator

        # Mock delete_objects
        client.delete_objects.return_value = {}

        return client

    @pytest.fixture
    def mock_google_ads_client(self):
        """Create a mock Google Ads client."""
        return AsyncMock()

    @pytest.fixture
    async def test_user(self, test_database):
        """Create a test user in the database."""
        engine, AsyncSessionLocal = test_database

        async with AsyncSessionLocal() as session:
            user = User(
                id="test_user_123",
                email="test@example.com",
                name="Test User",
                user_type="individual",
            )
            session.add(user)
            await session.commit()

            yield user

    @pytest.fixture
    def customer_init_service(self, mock_s3_client, mock_google_ads_client):
        """Create a customer initialization service."""
        return CustomerInitializationService(
            s3_client=mock_s3_client,
            google_ads_client=mock_google_ads_client,
            bucket_name="test-bucket",
        )

    @pytest.fixture
    def sample_request(self):
        """Create a sample customer initialization request."""
        return CustomerInitRequest(
            name="Integration Test Corp",
            email="contact@integrationtest.com",
            business_type=BusinessType.RETAIL,
            google_ads_customer_ids=["1234567890", "098-765-4321"],
            contact_person="John Integration",
            phone="555-999-8888",
            company_website="https://integrationtest.com",
            notes="This is an integration test customer",
        )

    async def test_complete_customer_initialization_flow(
        self, customer_init_service, sample_request, test_user, test_database
    ):
        """Test the complete customer initialization flow from request to database."""
        engine, AsyncSessionLocal = test_database

        # Mock Google Ads account info
        customer_init_service._get_google_ads_account_info = AsyncMock(
            return_value={
                "name": "Test Google Ads Account",
                "currency_code": "USD",
                "time_zone": "America/New_York",
                "account_type": "STANDARD",
            }
        )

        async with AsyncSessionLocal() as session:
            response = await customer_init_service.initialize_customer(
                request=sample_request, user_id=test_user.id, session=session
            )

        # Verify response
        assert response.success is True
        assert response.initialization_status == InitializationStatus.COMPLETED
        assert response.customer_record is not None
        assert response.s3_structure is not None
        assert len(response.google_ads_links) == 2
        assert len(response.errors) == 0
        assert response.duration_seconds > 0

        # Verify customer record details
        customer_record = response.customer_record
        assert customer_record.name == "Integration Test Corp"
        assert customer_record.email == "contact@integrationtest.com"
        assert customer_record.business_type == BusinessType.RETAIL
        assert customer_record.contact_person == "John Integration"
        assert customer_record.phone == "555-999-8888"

        # Verify S3 structure
        s3_structure = response.s3_structure
        assert s3_structure.customer_name_sanitized == "integration-test-corp"
        assert s3_structure.base_path.startswith("ret/integration-test-corp_")
        assert s3_structure.inputs_path.endswith("/inputs")
        assert s3_structure.outputs_path.endswith("/outputs")
        assert s3_structure.reports_path.endswith("/reports")
        assert s3_structure.actionable_files_path.endswith("/actionable")
        assert len(s3_structure.created_folders) == 4

        # Verify Google Ads links
        google_ads_links = response.google_ads_links
        assert len(google_ads_links) == 2
        assert google_ads_links[0].customer_id == "1234567890"
        assert google_ads_links[1].customer_id == "0987654321"  # Hyphens removed
        assert all(link.accessible for link in google_ads_links)
        assert all(link.link_status == "active" for link in google_ads_links)

        # Verify database record was created
        async with AsyncSessionLocal() as session:
            from paidsearchnav.storage.repository import CustomerRepository

            repo = CustomerRepository(session)
            db_customer = await repo.get_by_id(customer_record.customer_id)

            assert db_customer is not None
            assert db_customer.name == "Integration Test Corp"
            assert db_customer.email == "contact@integrationtest.com"
            assert db_customer.user_id == test_user.id
            assert db_customer.is_active is True

        # Verify S3 operations were called
        assert customer_init_service.s3_client.put_object.call_count == 4

    async def test_initialization_with_s3_failure_and_rollback(
        self, customer_init_service, sample_request, test_user, test_database
    ):
        """Test initialization failure and rollback when S3 operations fail."""
        engine, AsyncSessionLocal = test_database

        # Make S3 operations fail after creating some folders
        call_count = 0

        def side_effect_put_object(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 2:  # Fail after 2 successful calls
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                    "PutObject",
                )
            return {}

        customer_init_service.s3_client.put_object.side_effect = side_effect_put_object

        async with AsyncSessionLocal() as session:
            response = await customer_init_service.initialize_customer(
                request=sample_request, user_id=test_user.id, session=session
            )

        # Verify failure response
        assert response.success is False
        assert response.initialization_status == InitializationStatus.FAILED
        assert len(response.errors) > 0
        assert any("S3" in error for error in response.errors)

        # Verify rollback was attempted
        assert customer_init_service.s3_client.get_paginator.called

        # Verify no customer record was persisted
        async with AsyncSessionLocal() as session:
            from paidsearchnav.storage.repository import CustomerRepository

            repo = CustomerRepository(session)
            customers = await repo.list_by_user(test_user.id)
            assert len(customers) == 0

    async def test_initialization_without_google_ads_client(
        self, mock_s3_client, sample_request, test_user, test_database
    ):
        """Test initialization without Google Ads client."""
        engine, AsyncSessionLocal = test_database

        # Create service without Google Ads client
        service = CustomerInitializationService(
            s3_client=mock_s3_client, google_ads_client=None, bucket_name="test-bucket"
        )

        async with AsyncSessionLocal() as session:
            response = await service.initialize_customer(
                request=sample_request, user_id=test_user.id, session=session
            )

        # Should succeed but with warnings
        assert response.success is True
        assert response.initialization_status == InitializationStatus.COMPLETED
        assert len(response.google_ads_links) == 0
        assert len(response.warnings) > 0
        assert "Google Ads client not available" in response.warnings[0]

    async def test_database_constraint_violation(
        self, customer_init_service, sample_request, test_user, test_database
    ):
        """Test handling of database constraint violations."""
        engine, AsyncSessionLocal = test_database

        # Mock Google Ads validation
        customer_init_service._get_google_ads_account_info = AsyncMock(
            return_value={
                "name": "Test Account",
                "currency_code": "USD",
                "time_zone": "America/New_York",
                "account_type": "STANDARD",
            }
        )

        # First initialization should succeed
        async with AsyncSessionLocal() as session:
            response1 = await customer_init_service.initialize_customer(
                request=sample_request, user_id=test_user.id, session=session
            )

        assert response1.success is True

        # Second initialization with same Google Ads customer ID should handle duplicate
        # Note: This test depends on the unique constraint on google_ads_customer_id
        # The actual behavior may vary based on implementation
        async with AsyncSessionLocal() as session:
            response2 = await customer_init_service.initialize_customer(
                request=sample_request, user_id=test_user.id, session=session
            )

        # The service should either succeed (if it handles duplicates) or fail gracefully
        if not response2.success:
            assert len(response2.errors) > 0

    async def test_validation_after_successful_initialization(
        self, customer_init_service, sample_request, test_user, test_database
    ):
        """Test validation of customer after successful initialization."""
        engine, AsyncSessionLocal = test_database

        # Mock Google Ads validation
        customer_init_service._get_google_ads_account_info = AsyncMock(
            return_value={
                "name": "Test Account",
                "currency_code": "USD",
                "time_zone": "America/New_York",
                "account_type": "STANDARD",
            }
        )

        # Initialize customer
        async with AsyncSessionLocal() as session:
            response = await customer_init_service.initialize_customer(
                request=sample_request, user_id=test_user.id, session=session
            )

        assert response.success is True
        customer_id = response.customer_record.customer_id

        # Validate the initialized customer
        async with AsyncSessionLocal() as session:
            validation_result = (
                await customer_init_service.validate_customer_initialization(
                    customer_id=customer_id, session=session
                )
            )

        assert validation_result.valid is True
        assert validation_result.customer_exists is True
        assert validation_result.s3_structure_valid is True
        assert validation_result.google_ads_links_valid is True
        assert validation_result.database_consistent is True
        assert len(validation_result.errors) == 0

    async def test_concurrent_initializations(
        self, customer_init_service, test_user, test_database
    ):
        """Test concurrent customer initializations."""
        engine, AsyncSessionLocal = test_database

        # Mock Google Ads validation
        customer_init_service._get_google_ads_account_info = AsyncMock(
            return_value={
                "name": "Test Account",
                "currency_code": "USD",
                "time_zone": "America/New_York",
                "account_type": "STANDARD",
            }
        )

        # Create multiple requests
        requests = []
        for i in range(3):
            request = CustomerInitRequest(
                name=f"Concurrent Test Corp {i}",
                email=f"contact{i}@concurrenttest.com",
                business_type=BusinessType.RETAIL,
                google_ads_customer_ids=[f"123456789{i}"],
            )
            requests.append(request)

        # Run concurrent initializations
        import asyncio

        async def initialize_customer(request):
            async with AsyncSessionLocal() as session:
                return await customer_init_service.initialize_customer(
                    request=request, user_id=test_user.id, session=session
                )

        responses = await asyncio.gather(
            *[initialize_customer(req) for req in requests], return_exceptions=True
        )

        # All should succeed
        successful_responses = [r for r in responses if not isinstance(r, Exception)]
        assert len(successful_responses) == 3

        for response in successful_responses:
            assert response.success is True
            assert response.initialization_status == InitializationStatus.COMPLETED

        # Verify all customers were created
        async with AsyncSessionLocal() as session:
            from paidsearchnav.storage.repository import CustomerRepository

            repo = CustomerRepository(session)
            customers = await repo.list_by_user(test_user.id)
            assert len(customers) == 3

    async def test_large_folder_structure_creation(
        self, customer_init_service, test_user, test_database
    ):
        """Test creation of customer with complex folder structure requirements."""
        engine, AsyncSessionLocal = test_database

        # Create a request with a complex name that tests sanitization
        complex_request = CustomerInitRequest(
            name="Test Company, LLC & Associates (Professional Services) - New York Division",
            email="contact@complex-company.com",
            business_type=BusinessType.SERVICE,
            google_ads_customer_ids=["1234567890"],
        )

        # Mock Google Ads validation
        customer_init_service._get_google_ads_account_info = AsyncMock(
            return_value={
                "name": "Complex Test Account",
                "currency_code": "USD",
                "time_zone": "America/New_York",
                "account_type": "STANDARD",
            }
        )

        async with AsyncSessionLocal() as session:
            response = await customer_init_service.initialize_customer(
                request=complex_request, user_id=test_user.id, session=session
            )

        assert response.success is True

        # Verify the name was properly sanitized
        s3_structure = response.s3_structure
        sanitized_name = s3_structure.customer_name_sanitized

        # Should be sanitized but still meaningful
        assert len(sanitized_name) <= 63  # S3 segment length limit
        assert "-" in sanitized_name  # Should contain hyphens from spaces/punctuation
        assert sanitized_name.islower()  # Should be lowercase
        assert (
            sanitized_name.replace("-", "").replace("_", "").isalnum()
        )  # Should be alphanumeric plus separators
