"""Tests for database URL parsing logic in repository.py"""

from paidsearchnav_mcp.storage.repository import _convert_postgres_url_scheme


class TestDatabaseUrlParsing:
    """Test database URL parsing and conversion logic."""

    def test_convert_postgres_url_scheme_basic(self):
        """Test basic PostgreSQL URL scheme conversion."""
        # Test converting sync to async
        sync_url = "postgresql://user:pass@localhost:5432/db"
        async_url = _convert_postgres_url_scheme(sync_url, "postgresql+asyncpg")
        assert async_url == "postgresql+asyncpg://user:pass@localhost:5432/db"

        # Test converting async to sync
        async_url = "postgresql+asyncpg://user:pass@localhost:5432/db"
        sync_url = _convert_postgres_url_scheme(async_url, "postgresql")
        assert sync_url == "postgresql://user:pass@localhost:5432/db"

    def test_convert_postgres_url_scheme_complex(self):
        """Test PostgreSQL URL conversion with complex URLs."""
        # URL with query parameters
        complex_url = "postgresql://user:pass@host.example.com:5432/database_name?sslmode=require&application_name=myapp"
        converted = _convert_postgres_url_scheme(complex_url, "postgresql+asyncpg")
        expected = "postgresql+asyncpg://user:pass@host.example.com:5432/database_name?sslmode=require&application_name=myapp"
        assert converted == expected

    def test_convert_postgres_url_scheme_edge_cases(self):
        """Test edge cases in URL conversion."""
        # Empty URL
        assert _convert_postgres_url_scheme("", "postgresql") == ""

        # None URL
        assert _convert_postgres_url_scheme(None, "postgresql") is None

        # Non-PostgreSQL URL (should remain unchanged)
        mysql_url = "mysql://user:pass@localhost:3306/db"
        assert _convert_postgres_url_scheme(mysql_url, "postgresql") == mysql_url

        # SQLite URL (should remain unchanged)
        sqlite_url = "sqlite:///path/to/db.sqlite"
        assert _convert_postgres_url_scheme(sqlite_url, "postgresql") == sqlite_url

    def test_convert_postgres_url_scheme_special_characters(self):
        """Test URL conversion with special characters in password."""
        # URL with special characters that need proper URL encoding
        url_with_special = "postgresql://user:p@ss%40word@localhost:5432/db"
        converted = _convert_postgres_url_scheme(url_with_special, "postgresql+asyncpg")
        expected = "postgresql+asyncpg://user:p@ss%40word@localhost:5432/db"
        assert converted == expected

    def test_convert_postgres_url_scheme_no_password(self):
        """Test URL conversion without password."""
        url_no_pass = "postgresql://user@localhost:5432/db"
        converted = _convert_postgres_url_scheme(url_no_pass, "postgresql+asyncpg")
        expected = "postgresql+asyncpg://user@localhost:5432/db"
        assert converted == expected

    def test_convert_postgres_url_scheme_multiple_occurrences_bug_prevention(self):
        """Test that URL conversion handles multiple occurrences correctly.

        This test specifically validates that the fix using urllib.parse
        prevents the bug where string.replace() could corrupt URLs containing
        the scheme pattern multiple times.
        """
        # This would be problematic with simple string replace
        tricky_url = "postgresql://user:postgresql://pass@localhost:5432/db"
        converted = _convert_postgres_url_scheme(tricky_url, "postgresql+asyncpg")
        # The password part should remain unchanged - only the scheme should change
        expected = "postgresql+asyncpg://user:postgresql://pass@localhost:5432/db"
        assert converted == expected
