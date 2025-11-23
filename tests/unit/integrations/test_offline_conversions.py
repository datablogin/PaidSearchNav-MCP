"""Tests for offline conversion tracking."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.integrations.base import OfflineConversion
from paidsearchnav_mcp.integrations.offline_conversions import (
    EnhancedConversionsTracker,
    GCLIDTracker,
)


class TestEnhancedConversionsTracker:
    """Test EnhancedConversionsTracker functionality."""

    @pytest.fixture
    def mock_google_ads_client(self):
        """Create mock Google Ads client."""
        mock_client = Mock()
        mock_client.customer_id = "1234567890"
        mock_client.client = Mock()
        return mock_client

    @pytest.fixture
    def tracker(self, mock_google_ads_client):
        """Create EnhancedConversionsTracker instance."""
        with patch.object(EnhancedConversionsTracker, "_init_services") as mock_init:
            tracker = EnhancedConversionsTracker(mock_google_ads_client)
            tracker.conversion_upload_service = Mock()
            tracker.conversion_action_service = Mock()
        return tracker

    def test_tracker_initialization(self, mock_google_ads_client):
        """Test tracker initialization."""
        with patch.object(EnhancedConversionsTracker, "_init_services") as mock_init:
            tracker = EnhancedConversionsTracker(mock_google_ads_client)
            assert tracker.client == mock_google_ads_client
            mock_init.assert_called_once()

    def test_validate_conversion_valid(self, tracker):
        """Test validation of valid conversion."""
        conversion = OfflineConversion(
            conversion_id="conv123",
            gclid="gclid_12345678901234567890",  # Valid length
            conversion_name="offline_purchase",
            conversion_time=datetime.now(timezone.utc) - timedelta(hours=1),
            conversion_value=100.0,
            currency_code="USD",
        )

        errors = tracker.validate_conversion(conversion)
        assert errors == []

    def test_validate_conversion_missing_gclid(self, tracker):
        """Test validation with missing GCLID."""
        conversion = OfflineConversion(
            conversion_id="conv123",
            gclid="",
            conversion_name="offline_purchase",
            conversion_time=datetime.now(timezone.utc),
            conversion_value=100.0,
            currency_code="USD",
        )

        errors = tracker.validate_conversion(conversion)
        assert "GCLID is required for offline conversion tracking" in errors

    def test_validate_conversion_invalid_gclid(self, tracker):
        """Test validation with invalid GCLID."""
        conversion = OfflineConversion(
            conversion_id="conv123",
            gclid="short_gclid",  # Too short
            conversion_name="offline_purchase",
            conversion_time=datetime.now(timezone.utc),
            conversion_value=100.0,
            currency_code="USD",
        )

        errors = tracker.validate_conversion(conversion)
        assert "Invalid GCLID format" in errors

    def test_validate_conversion_future_time(self, tracker):
        """Test validation with future conversion time."""
        conversion = OfflineConversion(
            conversion_id="conv123",
            gclid="gclid_12345678901234567890",
            conversion_name="offline_purchase",
            conversion_time=datetime.now(timezone.utc) + timedelta(days=1),
            conversion_value=100.0,
            currency_code="USD",
        )

        errors = tracker.validate_conversion(conversion)
        assert "Conversion time cannot be in the future" in errors

    def test_validate_conversion_negative_value(self, tracker):
        """Test validation with negative conversion value."""
        conversion = OfflineConversion(
            conversion_id="conv123",
            gclid="gclid_12345678901234567890",
            conversion_name="offline_purchase",
            conversion_time=datetime.now(timezone.utc),
            conversion_value=-50.0,
            currency_code="USD",
        )

        errors = tracker.validate_conversion(conversion)
        assert "Conversion value cannot be negative" in errors

    def test_upload_conversions_empty_list(self, tracker):
        """Test uploading empty conversion list."""
        result = tracker.upload_conversions([])
        assert result["successful"] == 0
        assert result["failed"] == 0
        assert result["errors"] == []

    def test_upload_conversions_success(self, tracker):
        """Test successful conversion upload."""
        conversions = [
            OfflineConversion(
                conversion_id="conv1",
                gclid="gclid_12345678901234567890",
                conversion_name="offline_purchase",
                conversion_time=datetime.now(timezone.utc) - timedelta(hours=1),
                conversion_value=100.0,
                currency_code="USD",
            ),
            OfflineConversion(
                conversion_id="conv2",
                gclid="gclid_09876543210987654321",
                conversion_name="offline_purchase",
                conversion_time=datetime.now(timezone.utc) - timedelta(hours=2),
                conversion_value=200.0,
                currency_code="USD",
            ),
        ]

        # Mock the upload service response
        mock_response = Mock()
        mock_response.partial_failure_error = None
        tracker.conversion_upload_service.upload_click_conversions.return_value = (
            mock_response
        )

        result = tracker.upload_conversions(conversions)

        assert result["successful"] == 2
        assert result["failed"] == 0
        assert result["errors"] == []
        tracker.conversion_upload_service.upload_click_conversions.assert_called_once()

    def test_upload_conversions_with_invalid(self, tracker):
        """Test upload with some invalid conversions."""
        conversions = [
            OfflineConversion(
                conversion_id="conv1",
                gclid="gclid_12345678901234567890",
                conversion_name="offline_purchase",
                conversion_time=datetime.now(timezone.utc) - timedelta(hours=1),
                conversion_value=100.0,
                currency_code="USD",
            ),
            OfflineConversion(
                conversion_id="conv2",
                gclid="",  # Invalid - missing GCLID
                conversion_name="offline_purchase",
                conversion_time=datetime.now(timezone.utc),
                conversion_value=200.0,
                currency_code="USD",
            ),
        ]

        # Mock the upload service response
        mock_response = Mock()
        mock_response.partial_failure_error = None
        tracker.conversion_upload_service.upload_click_conversions.return_value = (
            mock_response
        )

        result = tracker.upload_conversions(conversions)

        assert result["successful"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) > 0

    def test_get_conversion_actions(self, tracker):
        """Test getting conversion actions."""
        # Mock Google Ads service
        mock_ga_service = Mock()
        tracker.client.client.get_service.return_value = mock_ga_service

        # Mock query response
        mock_batch = Mock()
        mock_row = Mock()
        mock_row.conversion_action.id = 123
        mock_row.conversion_action.name = "Purchase"
        mock_row.conversion_action.type.name = "WEBPAGE"
        mock_row.conversion_action.category.name = "PURCHASE"
        mock_row.conversion_action.value_settings.default_value = 0.0
        mock_row.conversion_action.value_settings.default_currency_code = "USD"

        mock_batch.results = [mock_row]
        mock_response = [mock_batch]
        mock_ga_service.search_stream.return_value = mock_response

        actions = tracker.get_conversion_actions()

        assert len(actions) == 1
        assert actions[0]["id"] == 123
        assert actions[0]["name"] == "Purchase"
        assert actions[0]["type"] == "WEBPAGE"
        assert actions[0]["category"] == "PURCHASE"

    def test_build_upload_request(self, tracker):
        """Test building upload request."""
        conversions = [
            OfflineConversion(
                conversion_id="conv1",
                gclid="gclid_12345678901234567890",
                conversion_name="offline_purchase",
                conversion_time=datetime.now(timezone.utc),
                conversion_value=100.0,
                currency_code="USD",
                order_id="order123",
                custom_variables={"custom_variable_1": "value1"},
            )
        ]

        # Mock client methods
        tracker.client.client.get_type = Mock(side_effect=lambda x: Mock())

        request = tracker._build_upload_request(conversions)

        assert request["customer_id"] == "1234567890"
        assert request["partial_failure"] is True
        assert len(request["conversions"]) == 1


class TestGCLIDTracker:
    """Test GCLIDTracker functionality."""

    @pytest.fixture
    def tracker(self):
        """Create GCLIDTracker instance."""
        mock_storage = Mock()
        return GCLIDTracker(storage_backend=mock_storage)

    def test_store_gclid_success(self, tracker):
        """Test successful GCLID storage."""
        tracker.storage.store_gclid.return_value = True

        result = tracker.store_gclid(
            gclid="gclid_12345",
            timestamp=datetime.now(timezone.utc),
            landing_page="https://example.com/landing",
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1",
        )

        assert result is True
        tracker.storage.store_gclid.assert_called_once()

        # Check that IP was hashed
        call_args = tracker.storage.store_gclid.call_args[0][0]
        assert call_args["hashed_ip"] is not None
        assert call_args["hashed_ip"] != "192.168.1.1"  # Should be hashed

    def test_store_gclid_no_storage(self):
        """Test GCLID storage without storage backend."""
        tracker = GCLIDTracker(storage_backend=None)

        result = tracker.store_gclid(
            gclid="gclid_12345",
            timestamp=datetime.now(timezone.utc),
        )

        assert result is True  # Should succeed but just log

    def test_store_gclid_failure(self, tracker):
        """Test GCLID storage failure."""
        tracker.storage.store_gclid.side_effect = Exception("Storage error")

        result = tracker.store_gclid(
            gclid="gclid_12345",
            timestamp=datetime.now(timezone.utc),
        )

        assert result is False

    def test_get_gclid_data(self, tracker):
        """Test retrieving GCLID data."""
        expected_data = {
            "gclid": "gclid_12345",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "landing_page": "https://example.com",
        }
        tracker.storage.get_gclid.return_value = expected_data

        result = tracker.get_gclid_data("gclid_12345")

        assert result == expected_data
        tracker.storage.get_gclid.assert_called_with("gclid_12345")

    def test_get_gclid_data_no_storage(self):
        """Test retrieving GCLID data without storage."""
        tracker = GCLIDTracker(storage_backend=None)
        result = tracker.get_gclid_data("gclid_12345")
        assert result is None

    def test_associate_gclid_with_lead_success(self, tracker):
        """Test associating GCLID with lead."""
        tracker.storage.associate_lead.return_value = True

        result = tracker.associate_gclid_with_lead(
            gclid="gclid_12345",
            lead_id="lead_67890",
            lead_data={"email": "test@example.com", "value": 1000},
        )

        assert result is True
        tracker.storage.associate_lead.assert_called_once()

    def test_associate_gclid_with_lead_failure(self, tracker):
        """Test failed GCLID-lead association."""
        tracker.storage.associate_lead.side_effect = Exception("Association error")

        result = tracker.associate_gclid_with_lead(
            gclid="gclid_12345",
            lead_id="lead_67890",
            lead_data={},
        )

        assert result is False

    def test_cleanup_old_gclids(self, tracker):
        """Test cleaning up old GCLIDs."""
        tracker.storage.cleanup_gclids.return_value = 100

        result = tracker.cleanup_old_gclids(days_to_keep=30)

        assert result == 100
        tracker.storage.cleanup_gclids.assert_called_once()

        # Check that cutoff date was calculated correctly
        call_args = tracker.storage.cleanup_gclids.call_args[0][0]
        expected_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        assert (
            abs((call_args - expected_cutoff).total_seconds()) < 60
        )  # Within 1 minute

    def test_cleanup_old_gclids_no_storage(self):
        """Test cleanup without storage backend."""
        tracker = GCLIDTracker(storage_backend=None)
        result = tracker.cleanup_old_gclids()
        assert result == 0
