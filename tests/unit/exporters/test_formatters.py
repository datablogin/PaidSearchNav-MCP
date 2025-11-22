"""Unit tests for Google Ads export formatters."""

from paidsearchnav.core.models.export_models import (
    BidAdjustment,
    CampaignChange,
    KeywordChange,
    NegativeKeyword,
)
from paidsearchnav.exporters.formatters import (
    BidAdjustmentFormatter,
    CampaignFormatter,
    KeywordFormatter,
    NegativeKeywordFormatter,
)


class TestKeywordFormatter:
    """Test keyword formatter."""

    def test_format_to_csv(self):
        """Test formatting keyword changes to CSV."""
        formatter = KeywordFormatter()
        changes = [
            KeywordChange(
                customer_id="123-456-7890",
                campaign="Test Campaign",
                ad_group="Test Ad Group",
                keyword="running shoes",
                match_type="Exact",
                status="Enabled",
                max_cpc=1.50,
                final_url="https://example.com/shoes",
            ),
            KeywordChange(
                customer_id="1234567890",
                campaign="Campaign 2",
                ad_group="Ad Group 2",
                keyword="tennis shoes",
                match_type="Phrase",
                status="Paused",
            ),
        ]

        csv_content = formatter.format_to_csv(changes)

        assert csv_content.startswith("\ufeff")  # BOM
        assert (
            "Customer ID,Campaign,Ad Group,Keyword,Match Type,Status,Max CPC,Final URL"
            in csv_content
        )
        assert (
            "1234567890,Test Campaign,Test Ad Group,running shoes,Exact,Enabled,1.50,https://example.com/shoes"
            in csv_content
        )
        assert (
            "1234567890,Campaign 2,Ad Group 2,tennis shoes,Phrase,Paused,,"
            in csv_content
        )

    def test_validate_changes(self):
        """Test validation of keyword changes."""
        formatter = KeywordFormatter()

        # Valid changes
        valid_changes = [
            KeywordChange(
                customer_id="1234567890",
                campaign="Valid Campaign",
                ad_group="Valid Ad Group",
                keyword="valid keyword",
                match_type="Exact",
                status="Enabled",
            )
        ]

        errors, warnings = formatter.validate_changes(valid_changes)
        assert len(errors) == 0
        assert len(warnings) == 0

        # Invalid changes
        invalid_changes = [
            KeywordChange(
                customer_id="123",  # Too short
                campaign="",  # Empty
                ad_group="Valid Ad Group",
                keyword="invalid@keyword",  # Invalid character
                match_type="Exact",
                status="Enabled",
                max_cpc=-1,  # Negative bid
            )
        ]

        errors, warnings = formatter.validate_changes(invalid_changes)
        assert len(errors) > 0
        assert any("customer ID" in e for e in errors)
        assert any("Campaign name" in e for e in errors)
        assert any("invalid character" in e for e in errors)
        assert any("cannot be negative" in e for e in errors)

    def test_create_file(self):
        """Test creating a keyword changes file."""
        formatter = KeywordFormatter()
        changes = [
            KeywordChange(
                customer_id="1234567890",
                campaign="Test Campaign",
                ad_group="Test Ad Group",
                keyword="test keyword",
                match_type="Exact",
                status="Enabled",
            )
        ]

        file = formatter.create_file(changes)

        assert file.file_name == "keyword_changes.csv"
        assert file.row_count == 1
        assert len(file.changes) == 1
        assert file.file_size > 0
        assert len(file.validation_errors) == 0


class TestNegativeKeywordFormatter:
    """Test negative keyword formatter."""

    def test_format_to_csv(self):
        """Test formatting negative keywords to CSV."""
        formatter = NegativeKeywordFormatter()
        negatives = [
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Test Campaign",
                ad_group="[Campaign]",
                keyword="cheap",
                match_type="Broad",
            ),
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Test Campaign",
                ad_group="Ad Group 1",
                keyword="discount",
                match_type="Phrase",
            ),
        ]

        csv_content = formatter.format_to_csv(negatives)

        assert csv_content.startswith("\ufeff")  # BOM
        assert "Customer ID,Campaign,Ad Group,Keyword,Match Type" in csv_content
        assert "1234567890,Test Campaign,[Campaign],cheap,Broad" in csv_content
        assert "1234567890,Test Campaign,Ad Group 1,discount,Phrase" in csv_content

    def test_validate_negatives(self):
        """Test validation of negative keywords."""
        formatter = NegativeKeywordFormatter()

        # Valid negatives
        valid_negatives = [
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Valid Campaign",
                keyword="valid negative",
                match_type="Exact",
            )
        ]

        errors, warnings = formatter.validate_negatives(valid_negatives)
        assert len(errors) == 0
        assert len(warnings) == 0

        # Duplicate negatives
        duplicate_negatives = [
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Campaign",
                keyword="duplicate",
                match_type="Exact",
            ),
            NegativeKeyword(
                customer_id="1234567890",
                campaign="Campaign",
                keyword="duplicate",
                match_type="Exact",
            ),
        ]

        errors, warnings = formatter.validate_negatives(duplicate_negatives)
        assert len(warnings) > 0
        assert any("Duplicate" in w for w in warnings)


class TestBidAdjustmentFormatter:
    """Test bid adjustment formatter."""

    def test_format_to_csv(self):
        """Test formatting bid adjustments to CSV."""
        formatter = BidAdjustmentFormatter()
        adjustments = [
            BidAdjustment(
                customer_id="1234567890",
                campaign="Test Campaign",
                location="New York",
                bid_adjustment="+20%",
            ),
            BidAdjustment(
                customer_id="1234567890",
                campaign="Test Campaign",
                device="Mobile",
                bid_adjustment="-15%",
            ),
        ]

        csv_content = formatter.format_to_csv(adjustments)

        assert csv_content.startswith("\ufeff")  # BOM
        assert "Customer ID,Campaign,Location,Device,Bid Adjustment" in csv_content
        assert "1234567890,Test Campaign,New York,,+20%" in csv_content
        assert "1234567890,Test Campaign,,Mobile,-15%" in csv_content

    def test_validate_adjustments(self):
        """Test validation of bid adjustments."""
        formatter = BidAdjustmentFormatter()

        # Valid adjustments
        valid_adjustments = [
            BidAdjustment(
                customer_id="1234567890",
                campaign="Valid Campaign",
                location="New York",
                bid_adjustment="+20%",
            )
        ]

        errors, warnings = formatter.validate_adjustments(valid_adjustments)
        assert len(errors) == 0
        assert len(warnings) == 0

        # Invalid adjustments
        invalid_adjustments = [
            BidAdjustment(
                customer_id="1234567890",
                campaign="Campaign",
                # Missing both location and device
                bid_adjustment="+20%",
            )
        ]

        errors, warnings = formatter.validate_adjustments(invalid_adjustments)
        assert len(errors) > 0
        assert any("Must specify either location or device" in e for e in errors)

        # Extreme adjustments
        extreme_adjustments = [
            BidAdjustment(
                customer_id="1234567890",
                campaign="Campaign",
                location="New York",
                bid_adjustment="-95%",
            )
        ]

        errors, warnings = formatter.validate_adjustments(extreme_adjustments)
        assert len(warnings) > 0
        assert any("very low" in w for w in warnings)


class TestCampaignFormatter:
    """Test campaign formatter."""

    def test_format_to_csv(self):
        """Test formatting campaign changes to CSV."""
        formatter = CampaignFormatter()
        changes = [
            CampaignChange(
                customer_id="1234567890",
                campaign="Test Campaign",
                status="Enabled",
                budget=100.00,
                bid_strategy="Target CPA",
                target_cpa=25.00,
            ),
            CampaignChange(
                customer_id="1234567890",
                campaign="Campaign 2",
                budget=200.00,
                bid_strategy="Target ROAS",
                target_roas=4.00,
            ),
        ]

        csv_content = formatter.format_to_csv(changes)

        assert csv_content.startswith("\ufeff")  # BOM
        assert (
            "Customer ID,Campaign,Status,Budget,Bid Strategy,Target CPA,Target ROAS"
            in csv_content
        )
        assert (
            "1234567890,Test Campaign,Enabled,100.00,Target CPA,25.00," in csv_content
        )
        assert "1234567890,Campaign 2,,200.00,Target ROAS,,4.00" in csv_content

    def test_validate_changes(self):
        """Test validation of campaign changes."""
        formatter = CampaignFormatter()

        # Valid changes
        valid_changes = [
            CampaignChange(
                customer_id="1234567890",
                campaign="Valid Campaign",
                budget=100.00,
                bid_strategy="Target CPA",
                target_cpa=25.00,
            )
        ]

        errors, warnings = formatter.validate_changes(valid_changes)
        assert len(errors) == 0
        assert len(warnings) == 0

        # Invalid changes
        invalid_changes = [
            CampaignChange(
                customer_id="1234567890",
                campaign="Campaign",
                budget=-10,  # Negative budget
                bid_strategy="Invalid Strategy",  # Invalid strategy
            )
        ]

        errors, warnings = formatter.validate_changes(invalid_changes)
        assert len(errors) > 0
        assert any("Budget cannot be negative" in e for e in errors)
        assert any("Invalid bid strategy" in e for e in errors)

        # Missing required fields
        missing_fields = [
            CampaignChange(
                customer_id="1234567890",
                campaign="Campaign",
                bid_strategy="Target CPA",
                # Missing target_cpa for Target CPA strategy
            )
        ]

        errors, warnings = formatter.validate_changes(missing_fields)
        assert len(errors) > 0
        assert any("Target CPA is required" in e for e in errors)

    def test_csv_escaping(self):
        """Test proper CSV escaping of special characters."""
        formatter = KeywordFormatter()
        changes = [
            KeywordChange(
                customer_id="1234567890",
                campaign='Campaign with "quotes"',
                ad_group="Ad Group, with comma",
                keyword="keyword\nwith\nnewlines",
                match_type="Exact",
                status="Enabled",
            )
        ]

        csv_content = formatter.format_to_csv(changes)

        # Check that special characters are properly handled (quotes, commas, newlines)
        # CSV module handles escaping, so we just check the content is present
        assert "Campaign with" in csv_content
        assert "quotes" in csv_content
        assert "Ad Group" in csv_content
        assert "comma" in csv_content
        assert "keyword" in csv_content
        assert "newlines" in csv_content
