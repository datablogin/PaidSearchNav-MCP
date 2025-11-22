"""Tests for base integration classes."""

from datetime import datetime, timezone

from paidsearchnav_mcp.integrations.base import (
    CRMConnector,
    CustomerJourney,
    Lead,
    LeadQuality,
    LeadStage,
    OfflineConversion,
    OfflineConversionTracker,
)


class TestLead:
    """Test Lead dataclass."""

    def test_lead_creation(self):
        """Test creating a Lead instance."""
        lead = Lead(
            id="lead123",
            email="test@example.com",
            phone="+1234567890",
            gclid="gclid_12345",
            created_at=datetime.now(timezone.utc),
            stage=LeadStage.QUALIFIED,
            quality=LeadQuality.HIGH,
            value=1000.0,
            source="google_ads",
            campaign_id="campaign123",
            ad_group_id="adgroup456",
            keyword="test keyword",
        )

        assert lead.id == "lead123"
        assert lead.email == "test@example.com"
        assert lead.stage == LeadStage.QUALIFIED
        assert lead.quality == LeadQuality.HIGH
        assert lead.value == 1000.0
        assert lead.custom_fields == {}

    def test_lead_custom_fields(self):
        """Test Lead with custom fields."""
        custom_fields = {"company": "Test Corp", "industry": "Technology"}
        lead = Lead(
            id="lead456",
            email=None,
            phone=None,
            gclid=None,
            created_at=datetime.now(timezone.utc),
            stage=LeadStage.NEW,
            custom_fields=custom_fields,
        )

        assert lead.custom_fields == custom_fields
        assert lead.custom_fields["company"] == "Test Corp"


class TestOfflineConversion:
    """Test OfflineConversion dataclass."""

    def test_offline_conversion_creation(self):
        """Test creating an OfflineConversion instance."""
        conversion_time = datetime.now(timezone.utc)
        conversion = OfflineConversion(
            conversion_id="conv123",
            gclid="gclid_12345",
            conversion_name="offline_purchase",
            conversion_time=conversion_time,
            conversion_value=500.0,
            currency_code="USD",
            lead_id="lead123",
            order_id="order456",
        )

        assert conversion.conversion_id == "conv123"
        assert conversion.gclid == "gclid_12345"
        assert conversion.conversion_value == 500.0
        assert conversion.custom_variables == {}

    def test_offline_conversion_custom_variables(self):
        """Test OfflineConversion with custom variables."""
        custom_vars = {"product_category": "electronics", "store_location": "NYC"}
        conversion = OfflineConversion(
            conversion_id="conv456",
            gclid="gclid_67890",
            conversion_name="store_visit",
            conversion_time=datetime.now(timezone.utc),
            conversion_value=0.0,
            custom_variables=custom_vars,
        )

        assert conversion.custom_variables == custom_vars
        assert conversion.conversion_value == 0.0


class TestCustomerJourney:
    """Test CustomerJourney dataclass."""

    def test_customer_journey_creation(self):
        """Test creating a CustomerJourney instance."""
        now = datetime.now(timezone.utc)
        journey = CustomerJourney(
            journey_id="journey123",
            gclid="gclid_12345",
            first_touch=now,
            last_touch=now,
            touchpoints=[
                {
                    "timestamp": now.isoformat(),
                    "type": "ad_click",
                    "channel": "paid_search",
                }
            ],
        )

        assert journey.journey_id == "journey123"
        assert journey.gclid == "gclid_12345"
        assert len(journey.touchpoints) == 1
        assert journey.conversions == []
        assert journey.total_value == 0.0

    def test_calculate_total_value(self):
        """Test calculating total value from conversions."""
        journey = CustomerJourney(
            journey_id="journey456",
            gclid="gclid_67890",
            first_touch=datetime.now(timezone.utc),
            last_touch=datetime.now(timezone.utc),
            touchpoints=[],
        )

        # Add conversions
        conversion1 = OfflineConversion(
            conversion_id="conv1",
            gclid="gclid_67890",
            conversion_name="purchase",
            conversion_time=datetime.now(timezone.utc),
            conversion_value=100.0,
        )
        conversion2 = OfflineConversion(
            conversion_id="conv2",
            gclid="gclid_67890",
            conversion_name="purchase",
            conversion_time=datetime.now(timezone.utc),
            conversion_value=200.0,
        )

        journey.conversions = [conversion1, conversion2]

        assert journey.calculate_total_value() == 300.0


class MockCRMConnector(CRMConnector):
    """Mock CRM connector for testing."""

    def authenticate(self) -> bool:
        return True

    def get_leads(
        self,
        start_date=None,
        end_date=None,
        stage=None,
    ):
        return []

    def update_lead(self, lead_id: str, updates):
        return True

    def sync_lead_stages(self, leads):
        return {lead.id: True for lead in leads}

    def get_custom_fields(self):
        return {"custom_field_1": {"type": "string"}}


class TestCRMConnector:
    """Test CRMConnector abstract base class."""

    def test_crm_connector_initialization(self):
        """Test CRM connector initialization."""
        config = {"api_key": "test_key", "endpoint": "https://api.example.com"}
        connector = MockCRMConnector(config)

        assert connector.config == config
        assert hasattr(connector, "logger")

    def test_test_connection(self):
        """Test connection testing."""
        connector = MockCRMConnector({})
        assert connector.test_connection() is True

    def test_abstract_methods_implemented(self):
        """Test that all abstract methods are implemented."""
        connector = MockCRMConnector({})

        # All these should work without raising NotImplementedError
        assert connector.authenticate() is True
        assert connector.get_leads() == []
        assert connector.update_lead("lead1", {}) is True
        assert connector.sync_lead_stages([]) == {}
        assert connector.get_custom_fields() == {"custom_field_1": {"type": "string"}}


class MockOfflineConversionTracker(OfflineConversionTracker):
    """Mock offline conversion tracker for testing."""

    def upload_conversions(self, conversions):
        return {
            "successful": len(conversions),
            "failed": 0,
            "errors": [],
        }

    def validate_conversion(self, conversion):
        errors = []
        if not conversion.gclid:
            errors.append("GCLID is required")
        return errors

    def get_conversion_actions(self):
        return [
            {
                "id": "123",
                "name": "Purchase",
                "type": "WEBPAGE",
                "category": "PURCHASE",
            }
        ]


class TestOfflineConversionTracker:
    """Test OfflineConversionTracker abstract base class."""

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        from unittest.mock import Mock

        mock_client = Mock()
        tracker = MockOfflineConversionTracker(mock_client)

        assert tracker.client == mock_client
        assert hasattr(tracker, "logger")

    def test_batch_upload(self):
        """Test batch upload functionality."""
        from unittest.mock import Mock

        mock_client = Mock()
        tracker = MockOfflineConversionTracker(mock_client)

        conversions = []
        for i in range(250):  # More than default batch size
            conversions.append(
                OfflineConversion(
                    conversion_id=f"conv{i}",
                    gclid=f"gclid_{i}",
                    conversion_name="test",
                    conversion_time=datetime.now(timezone.utc),
                    conversion_value=100.0,
                )
            )

        result = tracker.batch_upload(conversions, batch_size=100)

        assert result["successful"] == 250
        assert result["failed"] == 0
        assert len(result["batches"]) == 3  # 250 / 100 = 3 batches

    def test_batch_upload_with_errors(self):
        """Test batch upload with errors."""
        from unittest.mock import Mock

        mock_client = Mock()
        tracker = MockOfflineConversionTracker(mock_client)

        # Override upload method to simulate failure
        def failing_upload(conversions):
            raise Exception("API error")

        tracker.upload_conversions = failing_upload

        conversions = [
            OfflineConversion(
                conversion_id="conv1",
                gclid="gclid_1",
                conversion_name="test",
                conversion_time=datetime.now(timezone.utc),
                conversion_value=100.0,
            )
        ]

        result = tracker.batch_upload(conversions)

        assert result["successful"] == 0
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert "API error" in result["errors"][0]
