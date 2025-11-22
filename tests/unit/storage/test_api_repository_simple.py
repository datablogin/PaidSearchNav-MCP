"""Simple test to verify API repository is working."""

from unittest.mock import patch

from paidsearchnav.core.config import Settings
from paidsearchnav.storage.api_repository import APIRepository


def test_api_repository_creation():
    """Test that API repository can be created."""
    with patch("paidsearchnav.storage.repository.create_engine"):
        with patch("paidsearchnav.storage.repository.create_async_engine"):
            with patch("paidsearchnav.storage.models.Base.metadata.create_all"):
                settings = Settings(
                    environment="development",
                    debug=True,
                    data_dir="/tmp/test",
                )
                repo = APIRepository(settings)
                assert repo is not None
                assert hasattr(repo, "check_connection")
                assert hasattr(repo, "get_customer")
                assert hasattr(repo, "create_audit")
                assert hasattr(repo, "get_audit")
                assert hasattr(repo, "list_audits")
