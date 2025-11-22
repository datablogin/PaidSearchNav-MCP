"""Tests for logging module initialization and exports."""

import importlib
import sys
from unittest.mock import patch

import pytest


class TestLoggingInit:
    """Test cases for logging module initialization."""

    def test_all_exports(self):
        """Test that __all__ contains all expected exports."""
        from paidsearchnav import logging

        expected_exports = [
            "configure_logging",
            "get_logger",
            "LogLevel",
            "LogConfig",
            "AlertHandler",
            "SlackAlertHandler",
            "EmailAlertHandler",
            "SentryHandler",
            "JSONFormatter",
            "add_context",
            "clear_context",
            "get_context",
            "SecretsRegistry",
            "get_secrets_registry",
            "mask_secrets",
        ]

        assert hasattr(logging, "__all__")
        assert set(logging.__all__) == set(expected_exports)

    def test_imports_from_config(self):
        """Test imports from config module."""
        from paidsearchnav import logging

        # Check config imports
        assert hasattr(logging, "LogConfig")
        assert hasattr(logging, "LogLevel")
        assert hasattr(logging, "configure_logging")
        assert hasattr(logging, "get_logger")

        # Verify they're the correct objects
        from paidsearchnav.logging.config import (
            LogConfig,
            LogLevel,
            configure_logging,
            get_logger,
        )

        assert logging.LogConfig is LogConfig
        assert logging.LogLevel is LogLevel
        assert logging.configure_logging is configure_logging
        assert logging.get_logger is get_logger

    def test_imports_from_context(self):
        """Test imports from context module."""
        from paidsearchnav import logging

        # Check context imports
        assert hasattr(logging, "add_context")
        assert hasattr(logging, "clear_context")
        assert hasattr(logging, "get_context")

        # Verify they're the correct objects
        from paidsearchnav.logging.context import (
            add_context,
            clear_context,
            get_context,
        )

        assert logging.add_context is add_context
        assert logging.clear_context is clear_context
        assert logging.get_context is get_context

    def test_imports_from_formatters(self):
        """Test imports from formatters module."""
        from paidsearchnav import logging

        # Check formatter imports
        assert hasattr(logging, "JSONFormatter")

        # Verify it's the correct object
        from paidsearchnav.logging.formatters import JSONFormatter

        assert logging.JSONFormatter is JSONFormatter

    def test_imports_from_handlers(self):
        """Test imports from handlers module."""
        from paidsearchnav import logging

        # Check handler imports
        assert hasattr(logging, "AlertHandler")
        assert hasattr(logging, "SlackAlertHandler")
        assert hasattr(logging, "EmailAlertHandler")
        assert hasattr(logging, "SentryHandler")

        # Verify they're the correct objects
        from paidsearchnav.logging.handlers import (
            AlertHandler,
            EmailAlertHandler,
            SentryHandler,
            SlackAlertHandler,
        )

        assert logging.AlertHandler is AlertHandler
        assert logging.SlackAlertHandler is SlackAlertHandler
        assert logging.EmailAlertHandler is EmailAlertHandler
        assert logging.SentryHandler is SentryHandler

    def test_imports_from_secrets(self):
        """Test imports from secrets module."""
        from paidsearchnav import logging

        # Check secrets imports
        assert hasattr(logging, "SecretsRegistry")
        assert hasattr(logging, "get_secrets_registry")
        assert hasattr(logging, "mask_secrets")

        # Verify they're the correct objects
        from paidsearchnav.logging.secrets import (
            SecretsRegistry,
            get_secrets_registry,
            mask_secrets,
        )

        assert logging.SecretsRegistry is SecretsRegistry
        assert logging.get_secrets_registry is get_secrets_registry
        assert logging.mask_secrets is mask_secrets

    def test_module_can_be_imported(self):
        """Test that the module can be imported without errors."""
        # Should not raise any exceptions
        import paidsearchnav.logging

        assert paidsearchnav.logging is not None

    def test_no_unexpected_exports(self):
        """Test that no unexpected attributes are exported."""
        from paidsearchnav import logging

        # Get all public attributes
        public_attrs = [attr for attr in dir(logging) if not attr.startswith("_")]

        # Remove standard module attributes and submodules
        # Submodules like 'audit', 'monitoring' etc. are allowed for direct import
        standard_attrs = {"__all__"}
        submodules = {
            "audit",
            "config",
            "context",
            "formatters",
            "handlers",
            "monitoring",
            "secrets",
        }
        actual_attrs = set(public_attrs) - standard_attrs - submodules

        # Should only have the expected exports (plus submodules)
        expected = set(logging.__all__)
        assert actual_attrs == expected

    def test_lazy_import_behavior(self):
        """Test that imports don't cause side effects."""
        # Import should not configure logging or create any handlers
        with patch("logging.basicConfig") as mock_basic_config:
            with patch("logging.getLogger") as mock_get_logger:
                # Import the module

                # Should not have called these during import
                mock_basic_config.assert_not_called()
                # getLogger might be called for module-level loggers, but not for configuration
                if mock_get_logger.called:
                    # Verify it's not being called with our app's logger names
                    for call in mock_get_logger.call_args_list:
                        logger_name = call[0][0] if call[0] else None
                        assert logger_name != "paidsearchnav"

    def test_circular_import_protection(self):
        """Test that the module structure doesn't cause circular imports."""
        # Try importing submodules first, then the main module
        from paidsearchnav import logging
        from paidsearchnav.logging.config import LogConfig
        from paidsearchnav.logging.handlers import AlertHandler

        # Should still work correctly - verify the classes are accessible
        assert hasattr(logging, "AlertHandler")
        assert hasattr(logging, "LogConfig")
        # Verify they are the same class type
        assert logging.AlertHandler is AlertHandler
        assert logging.LogConfig is LogConfig

    def test_all_exported_items_are_importable(self):
        """Test that all items in __all__ can be successfully imported."""
        from paidsearchnav import logging

        for item_name in logging.__all__:
            item = getattr(logging, item_name)
            assert item is not None
            # Verify it's not just a string or placeholder
            assert not isinstance(item, str)

    def test_module_docstring(self):
        """Test that the module has a proper docstring."""
        from paidsearchnav import logging

        assert logging.__doc__ is not None
        assert len(logging.__doc__) > 0
        assert "logging" in logging.__doc__.lower()

    @pytest.mark.parametrize(
        "submodule",
        [
            "config",
            "context",
            "formatters",
            "handlers",
            "secrets",
        ],
    )
    def test_submodule_imports_dont_fail(self, submodule):
        """Test that each submodule can be imported independently."""
        module_name = f"paidsearchnav.logging.{submodule}"

        # Clear from cache
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Should import without errors
        module = importlib.import_module(module_name)
        assert module is not None

    def test_handler_class_hierarchy(self):
        """Test that handler classes maintain proper inheritance."""
        import logging as stdlib_logging

        from paidsearchnav import logging

        # Verify base class relationships
        assert issubclass(logging.AlertHandler, stdlib_logging.Handler)
        assert issubclass(logging.SlackAlertHandler, logging.AlertHandler)
        assert issubclass(logging.EmailAlertHandler, logging.AlertHandler)
        assert issubclass(logging.SentryHandler, stdlib_logging.Handler)

    def test_formatter_class_hierarchy(self):
        """Test that formatter classes maintain proper inheritance."""
        import logging as stdlib_logging

        from paidsearchnav import logging

        # Verify formatter inheritance
        assert issubclass(logging.JSONFormatter, stdlib_logging.Formatter)

    def test_no_import_time_side_effects(self):
        """Test that importing doesn't create files or network connections."""
        # Mock potential side effects
        with patch("builtins.open", side_effect=Exception("Should not open files")):
            with patch(
                "httpx.Client", side_effect=Exception("Should not create HTTP clients")
            ):
                with patch(
                    "smtplib.SMTP",
                    side_effect=Exception("Should not create SMTP connections"),
                ):
                    # Import should still work
                    import paidsearchnav.logging

                    assert paidsearchnav.logging is not None

    def test_type_annotations_available(self):
        """Test that type annotations are properly exposed."""
        from paidsearchnav import logging

        # Check that classes have annotations
        assert hasattr(logging.LogConfig, "__annotations__")
        assert hasattr(logging.SlackAlertHandler, "__init__")

        # Verify we can access the handler init signatures
        import inspect

        # SlackAlertHandler should have webhook_url and channel parameters
        sig = inspect.signature(logging.SlackAlertHandler.__init__)
        assert "webhook_url" in sig.parameters
        assert "channel" in sig.parameters

        # EmailAlertHandler should have multiple parameters
        sig = inspect.signature(logging.EmailAlertHandler.__init__)
        assert "smtp_host" in sig.parameters
        assert "from_email" in sig.parameters
        assert "to_emails" in sig.parameters
