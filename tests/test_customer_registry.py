"""Tests for customer registry functionality."""

import pytest
from unittest.mock import Mock, patch

from paidsearchnav_mcp.clients.bigquery.customer_registry import (
    CustomerRegistry,
    CustomerConfig,
)


@pytest.fixture
def mock_bigquery_client():
    """Mock BigQuery client for testing."""
    with patch("paidsearchnav_mcp.clients.bigquery.customer_registry.bigquery") as mock:
        yield mock


@pytest.fixture
def registry(mock_bigquery_client):
    """Create a test registry instance."""
    return CustomerRegistry(
        registry_project="test-project",
        registry_dataset="test_dataset",
        registry_table="customer_registry",
    )


def test_get_customer_config_success(registry, mock_bigquery_client):
    """Test successful customer config retrieval."""
    # Mock query results
    mock_row = {
        "customer_id": "5777461198",
        "project_id": "topgolf-460202",
        "dataset": "paidsearchnav_production",
        "account_name": "Topgolf",
        "status": "active",
    }

    mock_result = Mock()
    mock_result.result.return_value = [mock_row]
    mock_bigquery_client.Client.return_value.query.return_value = mock_result

    # Get config
    config = registry.get_customer_config("5777461198")

    # Verify
    assert config is not None
    assert config.customer_id == "5777461198"
    assert config.project_id == "topgolf-460202"
    assert config.dataset == "paidsearchnav_production"
    assert config.account_name == "Topgolf"
    assert config.status == "active"


def test_get_customer_config_not_found(registry, mock_bigquery_client):
    """Test customer not found in registry."""
    # Mock empty results
    mock_result = Mock()
    mock_result.result.return_value = []
    mock_bigquery_client.Client.return_value.query.return_value = mock_result

    # Get config
    config = registry.get_customer_config("9999999999")

    # Verify
    assert config is None


def test_get_customer_config_cached(registry, mock_bigquery_client):
    """Test that customer config is cached after first retrieval."""
    # Mock query results
    mock_row = {
        "customer_id": "5777461198",
        "project_id": "topgolf-460202",
        "dataset": "paidsearchnav_production",
        "account_name": "Topgolf",
        "status": "active",
    }

    mock_result = Mock()
    mock_result.result.return_value = [mock_row]
    mock_query = mock_bigquery_client.Client.return_value.query
    mock_query.return_value = mock_result

    # First call - should query
    config1 = registry.get_customer_config("5777461198")
    assert mock_query.call_count == 1

    # Second call - should use cache
    config2 = registry.get_customer_config("5777461198")
    assert mock_query.call_count == 1  # No additional query

    # Verify same config
    assert config1.customer_id == config2.customer_id
    assert config1.project_id == config2.project_id


def test_get_project_for_customer(registry, mock_bigquery_client):
    """Test getting project ID for customer."""
    # Mock query results
    mock_row = {
        "customer_id": "9097587272",
        "project_id": "puttery-golf-001",
        "dataset": "paidsearchnav_production",
        "account_name": "Puttery",
        "status": "active",
    }

    mock_result = Mock()
    mock_result.result.return_value = [mock_row]
    mock_bigquery_client.Client.return_value.query.return_value = mock_result

    # Get project
    project = registry.get_project_for_customer("9097587272")

    # Verify
    assert project == "puttery-golf-001"


def test_get_dataset_for_customer(registry, mock_bigquery_client):
    """Test getting dataset for customer."""
    # Mock query results
    mock_row = {
        "customer_id": "9097587272",
        "project_id": "puttery-golf-001",
        "dataset": "paidsearchnav_production",
        "account_name": "Puttery",
        "status": "active",
    }

    mock_result = Mock()
    mock_result.result.return_value = [mock_row]
    mock_bigquery_client.Client.return_value.query.return_value = mock_result

    # Get dataset
    dataset = registry.get_dataset_for_customer("9097587272")

    # Verify
    assert dataset == "paidsearchnav_production"


def test_clear_cache(registry, mock_bigquery_client):
    """Test cache clearing."""
    # Mock query results
    mock_row = {
        "customer_id": "5777461198",
        "project_id": "topgolf-460202",
        "dataset": "paidsearchnav_production",
        "account_name": "Topgolf",
        "status": "active",
    }

    mock_result = Mock()
    mock_result.result.return_value = [mock_row]
    mock_query = mock_bigquery_client.Client.return_value.query
    mock_query.return_value = mock_result

    # First call - should query
    registry.get_customer_config("5777461198")
    assert mock_query.call_count == 1

    # Clear cache
    registry.clear_cache()

    # Next call should query again
    registry.get_customer_config("5777461198")
    assert mock_query.call_count == 2


def test_list_customers(registry, mock_bigquery_client):
    """Test listing all active customers."""
    # Mock query results
    mock_rows = [
        {
            "customer_id": "5777461198",
            "project_id": "topgolf-460202",
            "dataset": "paidsearchnav_production",
            "account_name": "Topgolf",
            "status": "active",
        },
        {
            "customer_id": "9097587272",
            "project_id": "puttery-golf-001",
            "dataset": "paidsearchnav_production",
            "account_name": "Puttery",
            "status": "active",
        },
    ]

    mock_result = Mock()
    mock_result.result.return_value = mock_rows
    mock_bigquery_client.Client.return_value.query.return_value = mock_result

    # List customers
    customers = registry.list_customers()

    # Verify
    assert len(customers) == 2
    assert customers[0].customer_id == "5777461198"
    assert customers[1].customer_id == "9097587272"
