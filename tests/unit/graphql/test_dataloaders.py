"""Tests for GraphQL DataLoaders."""

from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.graphql.dataloaders import (
    DataLoaderRegistry,
    create_audit_loader,
    create_audit_results_loader,
    create_customer_audits_loader,
    create_customer_loader,
)


class TestDataLoaders:
    """Test DataLoader implementations."""

    @pytest.mark.asyncio
    async def test_customer_loader(self):
        """Test customer DataLoader batching."""
        mock_customers = [
            Mock(id="1", name="Customer 1"),
            Mock(id="2", name="Customer 2"),
            Mock(id="3", name="Customer 3"),
        ]

        with patch(
            "paidsearchnav.graphql.dataloaders.customer_service.get_by_ids",
            return_value=mock_customers,
        ) as mock_get:
            loader = create_customer_loader()

            # Load multiple customers
            results = await loader.load_many(["1", "3", "2", "999"])

            # Check results are in correct order
            assert results[0].id == "1"
            assert results[1].id == "3"
            assert results[2].id == "2"
            assert results[3] is None  # Non-existent customer

            # Verify batching - should be called once with all IDs
            mock_get.assert_called_once_with(["1", "3", "2", "999"])

    @pytest.mark.asyncio
    async def test_audit_loader(self):
        """Test audit DataLoader batching."""
        mock_audits = [
            Mock(id="a1", customer_id="c1"),
            Mock(id="a2", customer_id="c2"),
        ]

        with patch(
            "paidsearchnav.graphql.dataloaders.audit_service.get_by_ids",
            return_value=mock_audits,
        ) as mock_get:
            loader = create_audit_loader()

            # Load multiple audits
            results = await loader.load_many(["a1", "a2", "a3"])

            assert results[0].id == "a1"
            assert results[1].id == "a2"
            assert results[2] is None

            # Verify batching
            mock_get.assert_called_once_with(["a1", "a2", "a3"])

    @pytest.mark.asyncio
    async def test_customer_audits_loader(self):
        """Test customer audits DataLoader batching."""
        mock_audits = [
            Mock(id="a1", customer_id="c1"),
            Mock(id="a2", customer_id="c1"),
            Mock(id="a3", customer_id="c2"),
        ]

        with patch(
            "paidsearchnav.graphql.dataloaders.audit_service.get_by_customer_ids",
            return_value=mock_audits,
        ) as mock_get:
            loader = create_customer_audits_loader()

            # Load audits for multiple customers
            results = await loader.load_many(["c1", "c2", "c3"])

            # Check c1 has 2 audits
            assert len(results[0]) == 2
            assert all(a.customer_id == "c1" for a in results[0])

            # Check c2 has 1 audit
            assert len(results[1]) == 1
            assert results[1][0].customer_id == "c2"

            # Check c3 has no audits
            assert len(results[2]) == 0

            # Verify batching
            mock_get.assert_called_once_with(["c1", "c2", "c3"])

    @pytest.mark.asyncio
    async def test_audit_results_loader(self):
        """Test audit results DataLoader batching."""
        mock_results = [
            Mock(id="r1", audit_id="a1", analyzer_type="keyword_performance"),
            Mock(id="r2", audit_id="a1", analyzer_type="ad_copy_effectiveness"),
            Mock(id="r3", audit_id="a2", analyzer_type="keyword_performance"),
        ]

        with patch(
            "paidsearchnav.graphql.dataloaders.analysis_service.get_by_audit_ids",
            return_value=mock_results,
        ) as mock_get:
            loader = create_audit_results_loader()

            # Load results for multiple audits
            results = await loader.load_many(["a1", "a2", "a3"])

            # Check a1 has 2 results
            assert len(results[0]) == 2
            assert all(r.audit_id == "a1" for r in results[0])

            # Check a2 has 1 result
            assert len(results[1]) == 1
            assert results[1][0].audit_id == "a2"

            # Check a3 has no results
            assert len(results[2]) == 0

            # Verify batching
            mock_get.assert_called_once_with(["a1", "a2", "a3"])

    def test_dataloader_registry(self):
        """Test DataLoader registry."""
        registry = DataLoaderRegistry()

        # Check all loaders are created
        assert registry.get_customer_loader() is not None
        assert registry.get_audit_loader() is not None
        assert registry.get_customer_audits_loader() is not None
        assert registry.get_audit_results_loader() is not None
        assert registry.get_audit_recommendations_loader() is not None

        # Check they return the same instances
        assert registry.get_customer_loader() is registry.customer_loader
        assert registry.get_audit_loader() is registry.audit_loader
