"""Unit tests for negative keyword CSV parsing functionality."""

import pytest

from paidsearchnav.analyzers.negative_conflicts import NegativeConflictAnalyzer
from paidsearchnav.analyzers.shared_negatives import SharedNegativeValidatorAnalyzer


class TestNegativeConflictAnalyzerCSV:
    """Test CSV parsing for NegativeConflictAnalyzer."""

    def test_from_csv_standard_format(self, tmp_path):
        """Test parsing standard negative keywords CSV format."""
        # Create test CSV file
        csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",123,"Ad Group 1",456,"cheap","BROAD","Ad group"
"Campaign 1",123,"Ad Group 1",456,"free","EXACT","Ad group"
"Campaign 1",123,,,"discount","PHRASE","Campaign"
"Campaign 2",124,"Ad Group 2",457,"budget","BROAD","Ad group"
"""
        csv_path = tmp_path / "negative_keywords.csv"
        csv_path.write_text(csv_content)

        # Parse CSV
        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        # Verify parsed data
        assert analyzer._csv_negative_keywords is not None
        assert len(analyzer._csv_negative_keywords) == 4

        # Check first keyword
        first_kw = analyzer._csv_negative_keywords[0]
        assert first_kw["text"] == "cheap"
        assert first_kw["match_type"] == "BROAD"
        assert first_kw["level"] == "AD_GROUP"
        assert first_kw["campaign_name"] == "Campaign 1"
        assert first_kw["ad_group_name"] == "Ad Group 1"

        # Check campaign-level keyword
        campaign_kw = analyzer._csv_negative_keywords[2]
        assert campaign_kw["text"] == "discount"
        assert campaign_kw["match_type"] == "PHRASE"
        assert campaign_kw["level"] == "CAMPAIGN"
        assert campaign_kw["ad_group_name"] is None

    def test_from_csv_with_match_type_indicators(self, tmp_path):
        """Test parsing CSV with match type indicators in keyword text."""
        csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",123,"Ad Group 1",456,"[exact keyword]","","Ad group"
"Campaign 1",123,"Ad Group 1",456,'"phrase keyword"',"","Ad group"
"Campaign 1",123,,,"broad keyword","","Campaign"
"""
        csv_path = tmp_path / "negative_keywords.csv"
        csv_path.write_text(csv_content)

        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        assert len(analyzer._csv_negative_keywords) == 3

        # Check exact match
        assert analyzer._csv_negative_keywords[0]["text"] == "exact keyword"
        assert analyzer._csv_negative_keywords[0]["match_type"] == "EXACT"

        # Check phrase match
        assert analyzer._csv_negative_keywords[1]["text"] == "phrase keyword"
        assert analyzer._csv_negative_keywords[1]["match_type"] == "PHRASE"

        # Check broad match
        assert analyzer._csv_negative_keywords[2]["text"] == "broad keyword"
        assert analyzer._csv_negative_keywords[2]["match_type"] == "BROAD"

    def test_from_csv_fitness_connection_format(self, tmp_path):
        """Test parsing Fitness Connection report format."""
        csv_content = """Negative keyword report
All time
Negative keyword,Keyword or list,Campaign,Ad group,Level,Match type
[senior exercise center near me],Keyword,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh,--,Campaign,Exact match
"fitness connection",Keyword,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh,--,Campaign,Phrase match
planetfitness,Keyword,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh,--,Campaign,Broad match
"""
        csv_path = tmp_path / "fitness_negative_keywords.csv"
        csv_path.write_text(csv_content)

        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        assert len(analyzer._csv_negative_keywords) == 3

        # Check exact match keyword
        assert (
            analyzer._csv_negative_keywords[0]["text"]
            == "senior exercise center near me"
        )
        assert analyzer._csv_negative_keywords[0]["match_type"] == "EXACT"

        # Check phrase match keyword
        assert analyzer._csv_negative_keywords[1]["text"] == "fitness connection"
        assert analyzer._csv_negative_keywords[1]["match_type"] == "PHRASE"

        # Check broad match keyword
        assert analyzer._csv_negative_keywords[2]["text"] == "planetfitness"
        assert analyzer._csv_negative_keywords[2]["match_type"] == "BROAD"

    def test_from_csv_empty_file(self, tmp_path):
        """Test handling of empty CSV file."""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")

        with pytest.raises(ValueError, match="CSV file is empty"):
            NegativeConflictAnalyzer.from_csv(csv_path)

    def test_from_csv_file_not_found(self):
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            NegativeConflictAnalyzer.from_csv("non_existent_file.csv")

    def test_from_csv_file_too_large(self, tmp_path):
        """Test handling of file size limit."""
        csv_path = tmp_path / "large.csv"
        # Create a file larger than 1 byte
        csv_path.write_text("a" * 1000)

        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            NegativeConflictAnalyzer.from_csv(csv_path, max_file_size_mb=0.0000001)

    def test_from_csv_invalid_format(self, tmp_path):
        """Test handling of CSV with no valid data."""
        csv_content = """Some random header
Another line
No valid columns here
"""
        csv_path = tmp_path / "invalid.csv"
        csv_path.write_text(csv_content)

        with pytest.raises(ValueError, match="No valid negative keyword data found"):
            NegativeConflictAnalyzer.from_csv(csv_path)

    @pytest.mark.asyncio
    async def test_analyze_with_csv_data(self, tmp_path):
        """Test analyze method with CSV-loaded data."""
        # Create test CSV
        csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",123,"Ad Group 1",456,"cheap","BROAD","Ad group"
"""
        csv_path = tmp_path / "negative_keywords.csv"
        csv_path.write_text(csv_content)

        # Load analyzer with CSV data
        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        # Run analysis (without positive keywords, should handle gracefully)
        from datetime import datetime

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result is not None
        assert result.analyzer_name == "Negative Keyword Conflict Analyzer"
        assert result.metrics.custom_metrics["total_negative_keywords"] == 1


class TestSharedNegativeValidatorAnalyzerCSV:
    """Test CSV parsing for SharedNegativeValidatorAnalyzer."""

    def test_from_csv_shared_lists_format(self, tmp_path):
        """Test parsing shared negative lists CSV format."""
        csv_content = """Negative keyword list,Negative keyword,Match type,Status
"Legal Terms List","lawsuit","EXACT","Enabled"
"Legal Terms List","attorney","PHRASE","Enabled"
"Competitor Brands","competitor1","EXACT","Enabled"
"Competitor Brands","competitor2 clinic","PHRASE","Enabled"
"Job Seekers List","jobs","EXACT","Enabled"
"""
        csv_path = tmp_path / "shared_negative_lists.csv"
        csv_path.write_text(csv_content)

        # Parse CSV
        analyzer = SharedNegativeValidatorAnalyzer.from_csv(csv_path)

        # Verify parsed data
        assert analyzer._csv_shared_lists is not None
        assert len(analyzer._csv_shared_lists) == 3  # 3 unique lists

        # Find Legal Terms List
        legal_list = next(
            (
                lst
                for lst in analyzer._csv_shared_lists
                if lst["name"] == "Legal Terms List"
            ),
            None,
        )
        assert legal_list is not None
        assert len(legal_list["negative_keywords"]) == 2
        assert legal_list["negative_keywords"][0]["text"] == "lawsuit"
        assert legal_list["negative_keywords"][0]["match_type"] == "EXACT"

        # Find Competitor Brands list
        competitor_list = next(
            (
                lst
                for lst in analyzer._csv_shared_lists
                if lst["name"] == "Competitor Brands"
            ),
            None,
        )
        assert competitor_list is not None
        assert len(competitor_list["negative_keywords"]) == 2

    def test_from_csv_with_match_type_in_text(self, tmp_path):
        """Test parsing with match type indicators in keyword text."""
        csv_content = """Negative keyword list,Negative keyword,Match type,Status
"List 1","[exact keyword]","","Enabled"
"List 1",'"phrase keyword"',"","Enabled"
"List 2","broad keyword","","Enabled"
"""
        csv_path = tmp_path / "shared_lists.csv"
        csv_path.write_text(csv_content)

        analyzer = SharedNegativeValidatorAnalyzer.from_csv(csv_path)

        assert len(analyzer._csv_shared_lists) == 2

        # Check List 1
        list1 = next(
            (lst for lst in analyzer._csv_shared_lists if lst["name"] == "List 1"), None
        )
        assert list1["negative_keywords"][0]["text"] == "exact keyword"
        assert list1["negative_keywords"][0]["match_type"] == "EXACT"
        assert list1["negative_keywords"][1]["text"] == "phrase keyword"
        assert list1["negative_keywords"][1]["match_type"] == "PHRASE"

        # Check List 2
        list2 = next(
            (lst for lst in analyzer._csv_shared_lists if lst["name"] == "List 2"), None
        )
        assert list2["negative_keywords"][0]["text"] == "broad keyword"
        assert list2["negative_keywords"][0]["match_type"] == "BROAD"

    def test_from_csv_without_list_column(self, tmp_path):
        """Test parsing CSV without list name column (uses default list)."""
        csv_content = """Negative keyword,Match type,Status
"keyword1","EXACT","Enabled"
"keyword2","PHRASE","Enabled"
"keyword3","BROAD","Enabled"
"""
        csv_path = tmp_path / "no_list_column.csv"
        csv_path.write_text(csv_content)

        analyzer = SharedNegativeValidatorAnalyzer.from_csv(csv_path)

        assert len(analyzer._csv_shared_lists) == 1
        assert analyzer._csv_shared_lists[0]["name"] == "Default List"
        assert len(analyzer._csv_shared_lists[0]["negative_keywords"]) == 3

    def test_from_csv_paused_status(self, tmp_path):
        """Test handling of paused/disabled status."""
        csv_content = """Negative keyword list,Negative keyword,Match type,Status
"Active List","keyword1","EXACT","Enabled"
"Paused List","keyword2","PHRASE","Paused"
"Disabled List","keyword3","BROAD","Disabled"
"""
        csv_path = tmp_path / "status_test.csv"
        csv_path.write_text(csv_content)

        analyzer = SharedNegativeValidatorAnalyzer.from_csv(csv_path)

        # All keywords should be in their respective lists regardless of status
        assert len(analyzer._csv_shared_lists) == 3

    def test_from_csv_empty_file(self, tmp_path):
        """Test handling of empty CSV file."""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")

        with pytest.raises(ValueError, match="CSV file is empty"):
            SharedNegativeValidatorAnalyzer.from_csv(csv_path)

    def test_from_csv_missing_required_column(self, tmp_path):
        """Test handling of CSV missing required columns."""
        csv_content = """Random Column,Another Column
"value1","value2"
"""
        csv_path = tmp_path / "missing_columns.csv"
        csv_path.write_text(csv_content)

        with pytest.raises(
            ValueError, match="CSV missing required 'Negative keyword' column"
        ):
            SharedNegativeValidatorAnalyzer.from_csv(csv_path)

    @pytest.mark.asyncio
    async def test_analyze_with_csv_data(self, tmp_path):
        """Test analyze method with CSV-loaded data."""
        # Create test CSV
        csv_content = """Negative keyword list,Negative keyword,Match type,Status
"Test List","keyword1","EXACT","Enabled"
"Test List","keyword2","PHRASE","Enabled"
"""
        csv_path = tmp_path / "shared_lists.csv"
        csv_path.write_text(csv_content)

        # Load analyzer with CSV data
        analyzer = SharedNegativeValidatorAnalyzer.from_csv(csv_path)

        # Run analysis (without campaigns, should handle gracefully)
        from datetime import datetime

        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result is not None
        assert result.analyzer_name == "Shared Negative List Validator"
        assert result.metrics.custom_metrics["total_shared_lists"] == 1


class TestCSVIntegration:
    """Test integration between CSV parsing and analysis."""

    @pytest.mark.asyncio
    async def test_negative_conflict_csv_integration(self, tmp_path):
        """Test full workflow of loading CSV and finding conflicts."""
        # Create negative keywords CSV
        neg_csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",100,"Ad Group 1",1000,"shoes","BROAD","Campaign"
"""
        neg_csv_path = tmp_path / "negatives.csv"
        neg_csv_path.write_text(neg_csv_content)

        # Load analyzer
        analyzer = NegativeConflictAnalyzer.from_csv(neg_csv_path)

        # Mock positive keywords for conflict detection
        from paidsearchnav.core.models.keyword import (
            Keyword,
            KeywordMatchType,
            KeywordStatus,
        )

        mock_positive_keywords = [
            Keyword(
                keyword_id="1",
                campaign_id="100",
                campaign_name="Campaign 1",
                ad_group_id="1000",
                ad_group_name="Ad Group 1",
                text="buy shoes online",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.ENABLED,
                quality_score=8,
                impressions=1000,
                clicks=100,
                cost=200.0,
                conversions=10.0,
                conversion_value=500.0,
            )
        ]

        analyzer._csv_positive_keywords = mock_positive_keywords

        # Run analysis
        from datetime import datetime

        result = await analyzer.analyze(
            customer_id="test",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should find a conflict (negative "shoes" blocks positive "buy shoes online")
        assert result.metrics.issues_found == 1
        conflicts = result.raw_data["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["negative_keyword"]["text"] == "shoes"
        assert conflicts[0]["positive_keyword"]["text"] == "buy shoes online"

    def test_csv_unicode_handling(self, tmp_path):
        """Test handling of Unicode characters in CSV."""
        csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",123,"Ad Group 1",456,"café","BROAD","Ad group"
"Campaign 1",123,"Ad Group 1",456,"naïve","EXACT","Ad group"
"Campaign 1",123,,,"résumé","PHRASE","Campaign"
"Campaign 2",124,"Ad Group 2",457,"北京","EXACT","Ad group"
"Campaign 2",124,"Ad Group 2",457,"東京","PHRASE","Ad group"
"Campaign 2",124,,,"🚀 rocket","BROAD","Campaign"
"""
        csv_path = tmp_path / "unicode.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        assert len(analyzer._csv_negative_keywords) >= 3
        # Check French characters
        assert any(kw["text"] == "café" for kw in analyzer._csv_negative_keywords)
        assert any(kw["text"] == "naïve" for kw in analyzer._csv_negative_keywords)
        assert any(kw["text"] == "résumé" for kw in analyzer._csv_negative_keywords)
        # Check Chinese characters
        assert any(kw["text"] == "北京" for kw in analyzer._csv_negative_keywords)
        assert any(kw["text"] == "東京" for kw in analyzer._csv_negative_keywords)

    def test_csv_with_bom(self, tmp_path):
        """Test handling of CSV files with BOM (Byte Order Mark)."""
        csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",123,"Ad Group 1",456,"test keyword","BROAD","Ad group"
"""
        csv_path = tmp_path / "bom_test.csv"
        # Write with UTF-8 BOM
        with open(csv_path, "wb") as f:
            f.write(b"\xef\xbb\xbf")  # UTF-8 BOM
            f.write(csv_content.encode("utf-8"))

        # Should handle BOM gracefully
        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)
        assert len(analyzer._csv_negative_keywords) == 1
        assert analyzer._csv_negative_keywords[0]["text"] == "test keyword"

    def test_csv_injection_prevention(self, tmp_path, caplog):
        """Test that potential CSV injection patterns are handled safely."""
        csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",123,"Ad Group 1",456,"=1+1","BROAD","Ad group"
"Campaign 1",123,"Ad Group 1",456,"+SUM(A1:A10)","EXACT","Ad group"
"Campaign 1",123,,,"-cmd.exe","PHRASE","Campaign"
"Campaign 1",123,,,"@macroname","BROAD","Campaign"
"Campaign 1",123,,,"safe keyword","BROAD","Campaign"
"""
        csv_path = tmp_path / "injection_test.csv"
        csv_path.write_text(csv_content)

        import logging

        with caplog.at_level(logging.WARNING):
            analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        # Only safe keywords should pass validation
        assert len(analyzer._csv_negative_keywords) == 1
        assert analyzer._csv_negative_keywords[0]["text"] == "safe keyword"

        # Check that warnings were logged for dangerous patterns
        assert "CSV injection" in caplog.text
        assert "=1+1" in caplog.text

    def test_progress_callback(self, tmp_path):
        """Test progress callback functionality."""
        csv_content = """Campaign,Campaign ID,Ad group,Ad group ID,Negative keyword,Match type,Level
"Campaign 1",123,"Ad Group 1",456,"keyword1","BROAD","Ad group"
"Campaign 1",123,"Ad Group 1",456,"keyword2","EXACT","Ad group"
"""
        csv_path = tmp_path / "progress_test.csv"
        csv_path.write_text(csv_content)

        progress_messages = []

        def progress_callback(message):
            progress_messages.append(message)

        analyzer = NegativeConflictAnalyzer.from_csv(
            csv_path, progress_callback=progress_callback
        )

        # Should have received progress messages
        assert len(progress_messages) > 0
        assert any("Loading" in msg for msg in progress_messages)
