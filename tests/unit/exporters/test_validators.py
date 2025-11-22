"""Unit tests for Google Ads export validators."""

from paidsearchnav_mcp.models.analysis import Recommendation, RecommendationType
from paidsearchnav_mcp.models.export_models import (
    BidAdjustment,
    CampaignChange,
    KeywordChange,
    NegativeKeyword,
)
from paidsearchnav_mcp.exporters.validators import FormatValidator, ImportSimulator


class TestFormatValidator:
    """Test format validator."""

    def test_validate_recommendation_data(self):
        """Test validation of recommendation data."""
        validator = FormatValidator()

        # Valid recommendation
        valid_rec = Recommendation(
            type=RecommendationType.ADD_KEYWORD,
            priority="HIGH",
            title="Add keyword",
            description="Test",
            action_data={
                "keyword": "test",
                "match_type": "Exact",
                "campaign": "Campaign",
                "ad_group": "Ad Group",
            },
        )

        is_valid, error = validator.validate_recommendation_data(valid_rec)
        assert is_valid
        assert error is None

        # Missing action_data
        invalid_rec = Recommendation(
            type=RecommendationType.ADD_KEYWORD,
            priority="HIGH",
            title="Add keyword",
            description="Test",
            action_data={},
        )

        is_valid, error = validator.validate_recommendation_data(invalid_rec)
        assert not is_valid
        assert "Missing required fields" in error

    def test_validate_keyword_change(self):
        """Test validation of keyword changes."""
        validator = FormatValidator()

        # Valid keyword change
        valid_change = KeywordChange(
            customer_id="1234567890",
            campaign="Valid Campaign",
            ad_group="Valid Ad Group",
            keyword="valid keyword",
            match_type="Exact",
            status="Enabled",
        )

        is_valid, errors = validator.validate_keyword_change(valid_change)
        assert is_valid
        assert len(errors) == 0

        # Invalid keyword change
        invalid_change = KeywordChange(
            customer_id="123",  # Too short
            campaign="",  # Empty
            ad_group="Ad Group",
            keyword="invalid@keyword",  # Invalid character
            match_type="Exact",
            status="Enabled",
            max_cpc=-1,  # Negative
        )

        is_valid, errors = validator.validate_keyword_change(invalid_change)
        assert not is_valid
        assert len(errors) > 0
        assert any("customer ID" in e for e in errors)
        assert any("Campaign name" in e for e in errors)
        assert any("invalid character" in e for e in errors)

    def test_validate_negative_keyword(self):
        """Test validation of negative keywords."""
        validator = FormatValidator()

        # Valid negative keyword
        valid_negative = NegativeKeyword(
            customer_id="1234567890",
            campaign="Valid Campaign",
            keyword="valid negative",
            match_type="Phrase",
        )

        is_valid, errors = validator.validate_negative_keyword(valid_negative)
        assert is_valid
        assert len(errors) == 0

        # Invalid negative keyword
        invalid_negative = NegativeKeyword(
            customer_id="abc",  # Invalid format
            campaign="",  # Empty
            keyword="!invalid",  # Invalid character
            match_type="Exact",
        )

        is_valid, errors = validator.validate_negative_keyword(invalid_negative)
        assert not is_valid
        assert len(errors) > 0

    def test_validate_bid_adjustment(self):
        """Test validation of bid adjustments."""
        validator = FormatValidator()

        # Valid bid adjustment
        valid_adjustment = BidAdjustment(
            customer_id="1234567890",
            campaign="Valid Campaign",
            location="New York",
            bid_adjustment="+20%",
        )

        is_valid, errors = validator.validate_bid_adjustment(valid_adjustment)
        assert is_valid
        assert len(errors) == 0

        # Invalid bid adjustment - no location or device
        invalid_adjustment = BidAdjustment(
            customer_id="1234567890",
            campaign="Campaign",
            bid_adjustment="+20%",
        )

        is_valid, errors = validator.validate_bid_adjustment(invalid_adjustment)
        assert not is_valid
        assert any("Must specify either location or device" in e for e in errors)

        # Invalid bid adjustment - value too low
        extreme_adjustment = BidAdjustment(
            customer_id="1234567890",
            campaign="Campaign",
            location="New York",
            bid_adjustment="-150%",
        )

        is_valid, errors = validator.validate_bid_adjustment(extreme_adjustment)
        assert not is_valid
        assert any("cannot be less than -100%" in e for e in errors)

    def test_validate_campaign_change(self):
        """Test validation of campaign changes."""
        validator = FormatValidator()

        # Valid campaign change
        valid_change = CampaignChange(
            customer_id="1234567890",
            campaign="Valid Campaign",
            budget=100.00,
            bid_strategy="Target CPA",
            target_cpa=25.00,
        )

        is_valid, errors = validator.validate_campaign_change(valid_change)
        assert is_valid
        assert len(errors) == 0

        # Invalid campaign change
        invalid_change = CampaignChange(
            customer_id="123",  # Too short
            campaign="",  # Empty
            budget=-10,  # Negative
        )

        is_valid, errors = validator.validate_campaign_change(invalid_change)
        assert not is_valid
        assert len(errors) > 0
        assert any("customer ID" in e for e in errors)
        assert any("Campaign name" in e for e in errors)
        assert any("Budget cannot be negative" in e for e in errors)

    def test_check_for_conflicts(self):
        """Test checking for conflicts between keywords and negatives."""
        validator = FormatValidator()

        keyword_changes = [
            KeywordChange(
                customer_id="1234567890",
                campaign="Campaign 1",
                ad_group="Ad Group",
                keyword="running shoes",
                match_type="Exact",
                status="Enabled",
            ),
            KeywordChange(
                customer_id="1234567890",
                campaign="Campaign 1",
                ad_group="Ad Group",
                keyword="tennis shoes",
                match_type="Phrase",
                status="Enabled",
            ),
        ]

        negative_keywords = [
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Campaign 1",
                keyword="running shoes",  # Conflicts with positive
                match_type="Exact",
            ),
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Campaign 2",
                keyword="cheap",
                match_type="Broad",
            ),
        ]

        warnings = validator.check_for_conflicts(keyword_changes, negative_keywords)
        assert len(warnings) > 0
        assert any("both positive and negative" in w for w in warnings)


class TestImportSimulator:
    """Test import simulator."""

    def test_simulate_keyword_import(self):
        """Test simulating keyword import."""
        simulator = ImportSimulator()

        changes = [
            KeywordChange(
                customer_id="1234567890",
                campaign="Campaign 1",
                ad_group="Ad Group 1",
                keyword="test keyword",
                match_type="Exact",
                status="Enabled",
            ),
            KeywordChange(
                customer_id="1234567890",
                campaign="Campaign 1",
                ad_group="Ad Group 1",
                keyword="test keyword",  # Duplicate
                match_type="Exact",
                status="Enabled",
            ),
        ]

        success, issues = simulator.simulate_keyword_import(changes)
        assert not success
        assert len(issues) > 0
        assert any("Duplicate keyword" in issue for issue in issues)

    def test_simulate_negative_import(self):
        """Test simulating negative keyword import."""
        simulator = ImportSimulator()

        negatives = [
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Campaign 1",
                keyword="shoes",
                match_type="Broad",
            )
        ]

        existing_keywords = {
            "Campaign 1": {
                "Ad Group 1": {("running shoes", "Exact"), ("tennis shoes", "Phrase")}
            }
        }

        success, issues = simulator.simulate_negative_import(
            negatives, existing_keywords
        )
        assert not success
        assert len(issues) > 0
        assert any("would block" in issue for issue in issues)

    def test_simulate_bid_adjustment_import(self):
        """Test simulating bid adjustment import."""
        simulator = ImportSimulator()

        adjustments = [
            BidAdjustment(
                customer_id="1234567890",
                campaign="Campaign 1",
                location="New York",
                bid_adjustment="+20%",
            ),
            BidAdjustment(
                customer_id="1234567890",
                campaign="Campaign 1",
                location="New York",  # Duplicate
                bid_adjustment="+30%",
            ),
        ]

        success, issues = simulator.simulate_bid_adjustment_import(adjustments)
        assert not success
        assert len(issues) > 0
        assert any("Conflicting bid adjustments" in issue for issue in issues)

    def test_simulate_campaign_import(self):
        """Test simulating campaign import."""
        simulator = ImportSimulator()

        changes = [
            CampaignChange(
                customer_id="1234567890",
                campaign="Campaign 1",
                budget=0.50,  # Too low
                bid_strategy="Target CPA",
                target_cpa=25.00,
            ),
            CampaignChange(
                customer_id="1234567890",
                campaign="Campaign 1",  # Duplicate
                budget=100.00,
            ),
        ]

        success, issues = simulator.simulate_campaign_import(changes)
        assert not success
        assert len(issues) > 0
        assert any("below minimum" in issue for issue in issues)
        assert any("Multiple changes" in issue for issue in issues)

    def test_run_full_simulation(self):
        """Test running full import simulation."""
        simulator = ImportSimulator()

        keyword_changes = [
            KeywordChange(
                customer_id="1234567890",
                campaign="Campaign 1",
                ad_group="Ad Group",
                keyword="test",
                match_type="Exact",
                status="Enabled",
            )
        ]

        negative_keywords = [
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Campaign 1",
                keyword="test",  # Conflicts with positive
                match_type="Exact",
            )
        ]

        bid_adjustments = [
            BidAdjustment(
                customer_id="1234567890",
                campaign="Campaign 1",
                location="New York",
                bid_adjustment="-91%",  # Very low (triggers warning)
            )
        ]

        campaign_changes = [
            CampaignChange(
                customer_id="1234567890",
                campaign="Campaign 1",
                budget=100.00,
            )
        ]

        success, all_issues = simulator.run_full_simulation(
            keyword_changes=keyword_changes,
            negative_keywords=negative_keywords,
            bid_adjustments=bid_adjustments,
            campaign_changes=campaign_changes,
        )

        assert not success
        assert "negative_keywords" in all_issues
        assert "bid_adjustments" in all_issues

    def test_count_blocked_keywords(self):
        """Test counting blocked keywords."""
        simulator = ImportSimulator()

        keywords = {
            "Ad Group 1": {
                ("running shoes", "Exact"),
                ("tennis shoes", "Phrase"),
                ("cheap shoes", "Broad"),
            }
        }

        # Exact match negative
        count = simulator._count_blocked_keywords("running shoes", "Exact", keywords)
        assert count == 1

        # Phrase match negative
        count = simulator._count_blocked_keywords("shoes", "Phrase", keywords)
        assert count == 3  # All contain "shoes"

        # Broad match negative
        count = simulator._count_blocked_keywords("cheap", "Broad", keywords)
        assert count == 1  # Only "cheap shoes" contains "cheap"
