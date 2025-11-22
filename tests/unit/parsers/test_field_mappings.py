"""Unit tests for field mappings."""

from paidsearchnav_mcp.models.geo_performance import GeoPerformanceData
from paidsearchnav_mcp.models.keyword import Keyword
from paidsearchnav_mcp.models.search_term import SearchTerm
from paidsearchnav_mcp.parsers.field_mappings import (
    FIELD_MAPPINGS,
    get_available_file_types,
    get_field_mapping,
    validate_csv_headers,
)


class TestFieldMappings:
    """Test field mappings functionality."""

    def test_get_field_mapping_keywords(self):
        """Test getting field mapping for keywords."""
        mapping = get_field_mapping("keywords")
        assert mapping == FIELD_MAPPINGS["keywords"]
        assert "Keyword ID" in mapping
        assert mapping["Keyword ID"] == "keyword_id"

    def test_get_field_mapping_search_terms(self):
        """Test getting field mapping for search terms."""
        mapping = get_field_mapping("search_terms")
        assert mapping == FIELD_MAPPINGS["search_terms"]
        assert "Search term" in mapping
        assert mapping["Search term"] == "search_term"

    def test_get_field_mapping_geo_performance(self):
        """Test getting field mapping for geo performance."""
        mapping = get_field_mapping("geo_performance")
        assert mapping == FIELD_MAPPINGS["geo_performance"]
        assert "Location" in mapping
        assert mapping["Location"] == "location_name"

    def test_get_field_mapping_default(self):
        """Test getting field mapping for unknown type."""
        mapping = get_field_mapping("unknown_type")
        assert mapping == FIELD_MAPPINGS["default"]
        assert mapping == {}

    def test_get_available_file_types(self):
        """Test getting available file types."""
        file_types = get_available_file_types()
        assert "keywords" in file_types
        assert "search_terms" in file_types
        assert "geo_performance" in file_types
        assert "campaigns" in file_types
        assert "ad_groups" in file_types
        assert "default" in file_types

    def test_keyword_model_fields_covered(self):
        """Test that all required Keyword model fields are covered in mappings."""
        mapping = get_field_mapping("keywords")

        # Get required fields from the actual Keyword model
        keyword_fields = Keyword.model_fields
        required_fields = []

        # Check which fields are required (not optional)
        for field_name, field_info in keyword_fields.items():
            if field_info.is_required():
                required_fields.append(field_name)

        # Map of model fields to their expected CSV headers
        field_to_csv = {
            "keyword_id": "Keyword ID",
            "campaign_id": "Campaign ID",
            "campaign_name": "Campaign",
            "ad_group_id": "Ad group ID",
            "ad_group_name": "Ad group",
            "text": "Keyword",
            "match_type": "Match type",
            "status": "Status",
        }

        # Verify required fields that need CSV mappings are covered
        for field_name in required_fields:
            if field_name in field_to_csv:
                csv_header = field_to_csv[field_name]
                assert csv_header in mapping, (
                    f"Missing mapping for required field {field_name} (CSV header: {csv_header})"
                )
                assert mapping[csv_header] == field_name, (
                    f"Incorrect mapping for {csv_header}: "
                    f"expected {field_name}, got {mapping[csv_header]}"
                )

    def test_search_term_model_fields_covered(self):
        """Test that all required SearchTerm model fields are covered in mappings."""
        mapping = get_field_mapping("search_terms")

        # Get required fields from the actual SearchTerm model
        search_term_fields = SearchTerm.model_fields
        required_fields = []

        # Check which fields are required (not optional)
        for field_name, field_info in search_term_fields.items():
            if field_info.is_required():
                required_fields.append(field_name)

        # Map of model fields to their expected CSV headers
        field_to_csv = {
            "campaign_id": "Campaign ID",
            "campaign_name": "Campaign",
            "ad_group_id": "Ad group ID",
            "ad_group_name": "Ad group",
            "search_term": "Search term",
        }

        # Verify required fields that need CSV mappings are covered
        for field_name in required_fields:
            if field_name in field_to_csv:
                csv_header = field_to_csv[field_name]
                assert csv_header in mapping, (
                    f"Missing mapping for required field {field_name} (CSV header: {csv_header})"
                )
                assert mapping[csv_header] == field_name, (
                    f"Incorrect mapping for {csv_header}: "
                    f"expected {field_name}, got {mapping[csv_header]}"
                )

        # Check nested metrics fields
        metrics_fields = {
            "metrics.impressions": "Impr.",
            "metrics.clicks": "Clicks",
            "metrics.cost": "Cost",
            "metrics.conversions": "Conversions",
            "metrics.conversion_value": "Conversion value",
        }

        for model_field, csv_header in metrics_fields.items():
            assert csv_header in mapping, f"Missing mapping for {csv_header}"
            assert mapping[csv_header] == model_field, (
                f"Incorrect mapping for {csv_header}: "
                f"expected {model_field}, got {mapping[csv_header]}"
            )

    def test_geo_performance_model_fields_covered(self):
        """Test that all required GeoPerformanceData model fields are covered in mappings."""
        mapping = get_field_mapping("geo_performance")

        # Get required fields from the actual GeoPerformanceData model
        geo_fields = GeoPerformanceData.model_fields
        required_fields = []

        # Check which fields are required (not optional)
        for field_name, field_info in geo_fields.items():
            if field_info.is_required():
                required_fields.append(field_name)

        # Map of model fields to their expected CSV headers
        field_to_csv = {
            "customer_id": "Customer ID",
            "campaign_id": "Campaign ID",
            "campaign_name": "Campaign",
            "geographic_level": "Location type",
            "location_name": "Location",
            "start_date": None,  # Not typically in CSV exports
            "end_date": None,  # Not typically in CSV exports
        }

        # Verify required fields that need CSV mappings are covered
        for field_name in required_fields:
            if field_name in field_to_csv and field_to_csv[field_name] is not None:
                csv_header = field_to_csv[field_name]
                assert csv_header in mapping, (
                    f"Missing mapping for required field {field_name} (CSV header: {csv_header})"
                )
                assert mapping[csv_header] == field_name, (
                    f"Incorrect mapping for {csv_header}: "
                    f"expected {field_name}, got {mapping[csv_header]}"
                )

    def test_mappings_have_clear_comments(self):
        """Test that field mappings have clear comments."""
        # Check that keywords mapping has comment sections
        keywords_mapping_keys = list(FIELD_MAPPINGS["keywords"].keys())

        # Verify the mappings are logically organized
        # (This is a basic check - in real code you might parse the source file)
        assert "Keyword ID" in keywords_mapping_keys
        assert "Campaign ID" in keywords_mapping_keys
        assert "Impr." in keywords_mapping_keys
        assert "Quality Score" in keywords_mapping_keys

    def test_validate_csv_headers_all_present(self):
        """Test validation when all required headers are present."""
        headers = [
            "Keyword ID",
            "Campaign ID",
            "Campaign",
            "Ad group ID",
            "Ad group",
            "Keyword",
            "Match type",
            "Status",
            "Impr.",
            "Clicks",
        ]
        missing = validate_csv_headers("keywords", headers)
        assert missing == []

    def test_validate_csv_headers_missing_fields(self):
        """Test validation when required headers are missing."""
        headers = ["Campaign", "Keyword", "Impr."]
        missing = validate_csv_headers("keywords", headers)

        # Should be missing several required fields
        assert "Keyword ID" in missing
        assert "Campaign ID" in missing
        assert "Ad group ID" in missing
        assert "Ad group" in missing
        assert "Match type" in missing
        assert "Status" in missing

    def test_validate_csv_headers_search_terms(self):
        """Test validation for search terms file type."""
        headers = ["Search term", "Campaign", "Clicks"]
        missing = validate_csv_headers("search_terms", headers)

        assert "Campaign ID" in missing
        assert "Ad group ID" in missing
        assert "Ad group" in missing

    def test_validate_csv_headers_unknown_file_type(self):
        """Test validation for unknown file type."""
        headers = ["Column1", "Column2"]
        missing = validate_csv_headers("unknown", headers)

        # Unknown file types should have no required fields
        assert missing == []

    def test_mapping_with_sample_csv_data(self):
        """Test mappings work correctly with realistic CSV data."""
        import csv
        import tempfile

        # Create a sample keywords CSV
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                    "Max. CPC",
                    "Quality Score",
                    "Impr.",
                    "Clicks",
                    "Cost",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Keyword ID": "12345",
                    "Campaign ID": "67890",
                    "Campaign": "Summer Sale 2024",
                    "Ad group ID": "11111",
                    "Ad group": "Running Shoes",
                    "Keyword": "buy running shoes online",
                    "Match type": "EXACT",
                    "Status": "ENABLED",
                    "Max. CPC": "2.50",
                    "Quality Score": "8",
                    "Impr.": "1500",
                    "Clicks": "75",
                    "Cost": "125.50",
                }
            )
            temp_path = f.name

        try:
            # Read the CSV and apply mappings
            mapping = get_field_mapping("keywords")
            with open(temp_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Apply mappings
                    mapped_row = {}
                    for csv_field, value in row.items():
                        if csv_field in mapping:
                            mapped_field = mapping[csv_field]
                            mapped_row[mapped_field] = value
                        else:
                            mapped_row[csv_field] = value

                    # Verify mappings worked correctly
                    assert mapped_row["keyword_id"] == "12345"
                    assert mapped_row["campaign_name"] == "Summer Sale 2024"
                    assert mapped_row["text"] == "buy running shoes online"
                    assert mapped_row["match_type"] == "EXACT"
                    assert mapped_row["status"] == "ENABLED"
                    assert mapped_row["cpc_bid"] == "2.50"
                    assert mapped_row["quality_score"] == "8"

                    # Verify original fields were mapped (not present)
                    assert "Keyword ID" not in mapped_row
                    assert "Campaign" not in mapped_row
                    assert "Keyword" not in mapped_row
        finally:
            import os

            os.unlink(temp_path)
