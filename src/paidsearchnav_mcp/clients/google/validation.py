"""Input validation utilities for Google Ads API security."""

import re

from paidsearchnav_mcp.models.campaign import CampaignType


class GoogleAdsInputValidator:
    """Validates inputs for Google Ads API queries to prevent injection attacks."""

    # Regex patterns for validation
    CAMPAIGN_ID_PATTERN = re.compile(r"^\d+$")  # Only digits
    AD_GROUP_ID_PATTERN = re.compile(r"^\d+$")  # Only digits
    SHARED_SET_ID_PATTERN = re.compile(r"^\d+$")  # Only digits
    CUSTOMER_ID_PATTERN = re.compile(
        r"^\d{7,10}$"
    )  # 7-10 digits for Google Ads customer IDs

    # Geographic level validation
    VALID_GEOGRAPHIC_LEVELS = {"COUNTRY", "STATE", "CITY", "ZIP_CODE"}

    @classmethod
    def validate_campaign_types(cls, campaign_types: list[str]) -> list[str]:
        """Validate campaign types against the CampaignType enum.

        Args:
            campaign_types: List of campaign type strings to validate

        Returns:
            List of validated campaign type strings

        Raises:
            ValueError: If any campaign type is invalid
        """
        if not campaign_types:
            return []

        valid_types = set(CampaignType.__members__.keys())
        validated_types = []
        invalid_types = []

        for campaign_type in campaign_types:
            if not isinstance(campaign_type, str):
                invalid_types.append(str(campaign_type))
                continue

            # Convert to uppercase to match enum
            normalized_type = campaign_type.upper().strip()
            if normalized_type in valid_types:
                validated_types.append(normalized_type)
            else:
                invalid_types.append(campaign_type)

        if invalid_types:
            raise ValueError(
                f"Invalid campaign types: {invalid_types}. "
                f"Valid types are: {sorted(valid_types)}"
            )

        return validated_types

    @classmethod
    def validate_campaign_ids(cls, campaign_ids: list[str]) -> list[str]:
        """Validate campaign IDs to ensure they are numeric.

        Args:
            campaign_ids: List of campaign ID strings to validate

        Returns:
            List of validated campaign ID strings

        Raises:
            ValueError: If any campaign ID is invalid
        """
        if not campaign_ids:
            return []

        validated_ids = []
        invalid_ids = []

        for campaign_id in campaign_ids:
            if not isinstance(campaign_id, str):
                campaign_id = str(campaign_id)

            # Remove whitespace
            campaign_id = campaign_id.strip()

            if cls.CAMPAIGN_ID_PATTERN.match(campaign_id):
                validated_ids.append(campaign_id)
            else:
                invalid_ids.append(campaign_id)

        if invalid_ids:
            raise ValueError(f"Invalid campaign IDs (must be numeric): {invalid_ids}")

        return validated_ids

    @classmethod
    def validate_ad_group_ids(cls, ad_group_ids: list[str]) -> list[str]:
        """Validate ad group IDs to ensure they are numeric.

        Args:
            ad_group_ids: List of ad group ID strings to validate

        Returns:
            List of validated ad group ID strings

        Raises:
            ValueError: If any ad group ID is invalid
        """
        if not ad_group_ids:
            return []

        validated_ids = []
        invalid_ids = []

        for ad_group_id in ad_group_ids:
            if not isinstance(ad_group_id, str):
                ad_group_id = str(ad_group_id)

            # Remove whitespace
            ad_group_id = ad_group_id.strip()

            if cls.AD_GROUP_ID_PATTERN.match(ad_group_id):
                validated_ids.append(ad_group_id)
            else:
                invalid_ids.append(ad_group_id)

        if invalid_ids:
            raise ValueError(f"Invalid ad group IDs (must be numeric): {invalid_ids}")

        return validated_ids

    @classmethod
    def validate_shared_set_id(cls, shared_set_id: str) -> str:
        """Validate shared set ID to ensure it is numeric and positive.

        Args:
            shared_set_id: Shared set ID string to validate

        Returns:
            Validated shared set ID string

        Raises:
            ValueError: If shared set ID is invalid
        """
        if not isinstance(shared_set_id, str):
            shared_set_id = str(shared_set_id)

        # Remove whitespace
        shared_set_id = shared_set_id.strip()

        if cls.SHARED_SET_ID_PATTERN.match(shared_set_id):
            # Additional range validation - must be positive
            shared_set_id_int = int(shared_set_id)
            if shared_set_id_int <= 0:
                raise ValueError(
                    f"Invalid shared set ID: '{shared_set_id}'. "
                    "Must be a positive integer greater than 0"
                )
            return shared_set_id
        else:
            raise ValueError(
                f"Invalid shared set ID format: '{shared_set_id}'. "
                "Must be a numeric string representing a positive integer"
            )

    @classmethod
    def validate_customer_id(cls, customer_id: str) -> str:
        """Validate customer ID format.

        Args:
            customer_id: Customer ID string to validate

        Returns:
            Validated customer ID string

        Raises:
            ValueError: If customer ID is invalid
        """
        if not isinstance(customer_id, str):
            customer_id = str(customer_id)

        # Remove whitespace and hyphens
        cleaned_id = customer_id.replace("-", "").strip()

        if cls.CUSTOMER_ID_PATTERN.match(cleaned_id):
            return cleaned_id
        else:
            raise ValueError(
                f"Invalid customer ID format: '{customer_id}'. "
                "Must be 7-10 digits (with or without hyphens)"
            )

    @classmethod
    def validate_geographic_level(cls, geographic_level: str) -> str:
        """Validate geographic level parameter.

        Args:
            geographic_level: Geographic level string to validate

        Returns:
            Validated geographic level string

        Raises:
            ValueError: If geographic level is invalid
        """
        if not isinstance(geographic_level, str):
            geographic_level = str(geographic_level)

        normalized_level = geographic_level.upper().strip()

        if normalized_level in cls.VALID_GEOGRAPHIC_LEVELS:
            return normalized_level
        else:
            raise ValueError(
                f"Invalid geographic level: '{geographic_level}'. "
                f"Valid levels are: {sorted(cls.VALID_GEOGRAPHIC_LEVELS)}"
            )

    @classmethod
    def build_safe_campaign_type_filter(cls, campaign_types: list[str]) -> str:
        """Build a safe campaign type filter for GAQL queries.

        Args:
            campaign_types: List of campaign types to filter by

        Returns:
            Safe GAQL filter string

        Raises:
            ValueError: If any campaign type is invalid
        """
        validated_types = cls.validate_campaign_types(campaign_types)

        if not validated_types:
            return ""

        # Build safe filter using validated enum values
        type_filters = [
            f"campaign.advertising_channel_type = '{ct}'" for ct in validated_types
        ]

        return " OR ".join(type_filters)

    @classmethod
    def build_safe_campaign_id_filter(cls, campaign_ids: list[str]) -> str:
        """Build a safe campaign ID filter for GAQL queries.

        Args:
            campaign_ids: List of campaign IDs to filter by

        Returns:
            Safe GAQL filter string

        Raises:
            ValueError: If any campaign ID is invalid
        """
        validated_ids = cls.validate_campaign_ids(campaign_ids)

        if not validated_ids:
            return ""

        # Build safe filter using validated numeric IDs
        id_filters = [f"campaign.id = {cid}" for cid in validated_ids]

        return " OR ".join(id_filters)

    @classmethod
    def build_safe_ad_group_id_filter(cls, ad_group_ids: list[str]) -> str:
        """Build a safe ad group ID filter for GAQL queries.

        Args:
            ad_group_ids: List of ad group IDs to filter by

        Returns:
            Safe GAQL filter string

        Raises:
            ValueError: If any ad group ID is invalid
        """
        validated_ids = cls.validate_ad_group_ids(ad_group_ids)

        if not validated_ids:
            return ""

        # Build safe filter using validated numeric IDs
        id_filters = [f"ad_group.id = {agid}" for agid in validated_ids]

        return " OR ".join(id_filters)
