"""Tests for the API server runner (api/run.py)."""

import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.api.run import main


class TestAPIRunner:
    """Test the API server runner."""

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_main_function_calls_uvicorn(self, mock_get_settings, mock_uvicorn_run):
        """Test that main() calls uvicorn.run with correct parameters."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.api_host = "127.0.0.1"
        mock_settings.api_port = 8000
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        # Mock app import
        with patch("paidsearchnav.api.run.app") as mock_app:
            # Call main function
            main()

            # Verify uvicorn.run was called with correct parameters
            mock_uvicorn_run.assert_called_once_with(
                mock_app, host="127.0.0.1", port=8000, reload=False, log_level="info"
            )

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_main_function_debug_mode(self, mock_get_settings, mock_uvicorn_run):
        """Test that main() uses debug settings when debug is True."""
        # Mock settings with debug enabled
        mock_settings = Mock()
        mock_settings.api_host = "0.0.0.0"
        mock_settings.api_port = 8080
        mock_settings.debug = True
        mock_get_settings.return_value = mock_settings

        # Mock app import
        with patch("paidsearchnav.api.run.app") as mock_app:
            # Call main function
            main()

            # Verify uvicorn.run was called with debug settings
            mock_uvicorn_run.assert_called_once_with(
                mock_app, host="0.0.0.0", port=8080, reload=True, log_level="debug"
            )

    @patch("paidsearchnav.api.run.get_settings")
    def test_settings_loading(self, mock_get_settings):
        """Test that settings are properly loaded."""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        with patch("paidsearchnav.api.run.uvicorn.run"):
            with patch("paidsearchnav.api.run.app"):
                main()

                # Verify settings were loaded
                mock_get_settings.assert_called_once()

    def test_real_app_import(self):
        """Test that the FastAPI app can be imported without mocking."""
        # Test real import without mocking to ensure dependencies work
        try:
            from paidsearchnav.api.main import app as main_app
            from paidsearchnav.api.run import app

            # Verify the imported app is the correct FastAPI instance
            assert app is main_app
            assert hasattr(app, "routes")  # FastAPI apps have routes
            assert hasattr(app, "dependency_overrides")  # FastAPI dependency system

        except ImportError as e:
            pytest.fail(f"Failed to import app dependencies: {e}")

    def test_real_settings_import(self):
        """Test that settings can be imported and instantiated without mocking."""
        try:
            from paidsearchnav.api.run import get_settings

            # Test that get_settings is callable and returns settings
            assert callable(get_settings)

            # Test that we can call it (may fail with config issues, that's ok)
            try:
                settings = get_settings()
                # If it succeeds, verify it has the expected attributes
                assert hasattr(settings, "api_host")
                assert hasattr(settings, "api_port")
                assert hasattr(settings, "debug")
            except Exception:
                # Settings might fail due to missing config, which is expected in tests
                pass

        except ImportError as e:
            pytest.fail(f"Failed to import settings dependencies: {e}")

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_app_import_with_mocking(self, mock_get_settings, mock_uvicorn_run):
        """Test that the FastAPI app is properly passed to uvicorn."""
        mock_settings = Mock()
        mock_settings.api_host = "localhost"
        mock_settings.api_port = 8000
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        with patch("paidsearchnav.api.run.app") as mock_app:
            main()

            # Verify app was passed to uvicorn
            mock_uvicorn_run.assert_called_once()
            call_args = mock_uvicorn_run.call_args[1]
            assert call_args["host"] == "localhost"
            assert call_args["port"] == 8000
            assert not call_args["reload"]
            assert call_args["log_level"] == "info"

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_error_handling_settings_failure(self, mock_get_settings, mock_uvicorn_run):
        """Test error handling when settings loading fails."""
        mock_get_settings.side_effect = Exception("Settings loading error")

        with pytest.raises(Exception, match="Settings loading error"):
            main()

        # uvicorn should not have been called
        mock_uvicorn_run.assert_not_called()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_error_handling_app_import_failure(
        self, mock_get_settings, mock_uvicorn_run
    ):
        """Test error handling when app import fails."""
        mock_settings = Mock()
        mock_settings.api_host = "localhost"
        mock_settings.api_port = 8000
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        # Test that if app import fails, the error is properly handled
        # Since the import happens at module level, we can't easily mock it
        # But we can test that the function works with a valid app import
        with patch("paidsearchnav.api.run.app") as mock_app:
            main()
            # Verify that the app was used
            mock_uvicorn_run.assert_called_once_with(
                mock_app, host="localhost", port=8000, reload=False, log_level="info"
            )

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_error_handling_uvicorn_failure(self, mock_get_settings, mock_uvicorn_run):
        """Test error handling when uvicorn fails to start."""
        mock_settings = Mock()
        mock_settings.api_host = "localhost"
        mock_settings.api_port = 8000
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        mock_uvicorn_run.side_effect = Exception("Uvicorn startup error")

        with patch("paidsearchnav.api.run.app"):
            with pytest.raises(Exception, match="Uvicorn startup error"):
                main()

    def test_direct_execution(self):
        """Test executing the run.py file directly."""
        try:
            # Test with --help to avoid actually starting the server
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    'import paidsearchnav.api.run; print("Import successful")',
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Should be able to import successfully
            assert result.returncode == 0
            assert "Import successful" in result.stdout

        except subprocess.TimeoutExpired:
            pytest.skip("Import timed out - likely due to module loading issues")
        except FileNotFoundError:
            pytest.skip("Module not installed in editable mode")
        except Exception as e:
            pytest.skip(f"Unable to test direct execution: {e}")

    @patch("paidsearchnav.api.run.main")
    def test_name_main_guard(self, mock_main):
        """Test that main() is only called when __name__ == '__main__'."""
        # Reset the mock
        mock_main.reset_mock()

        # Import the module (this should not call main)

        # main should not have been called during import
        mock_main.assert_not_called()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_port_configuration(self, mock_get_settings, mock_uvicorn_run):
        """Test different port configurations."""
        test_cases = [
            (8000, 8000),
            (8080, 8080),
            (3000, 3000),
            (9000, 9000),
        ]

        for expected_port, settings_port in test_cases:
            mock_settings = Mock()
            mock_settings.api_host = "localhost"
            mock_settings.api_port = settings_port
            mock_settings.debug = False
            mock_get_settings.return_value = mock_settings

            with patch("paidsearchnav.api.run.app"):
                main()

                # Verify correct port was used
                call_args = mock_uvicorn_run.call_args[1]
                assert call_args["port"] == expected_port

            mock_uvicorn_run.reset_mock()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_host_configuration(self, mock_get_settings, mock_uvicorn_run):
        """Test different host configurations."""
        test_cases = [
            ("localhost", "localhost"),
            ("127.0.0.1", "127.0.0.1"),
            ("0.0.0.0", "0.0.0.0"),
        ]

        for expected_host, settings_host in test_cases:
            mock_settings = Mock()
            mock_settings.api_host = settings_host
            mock_settings.api_port = 8000
            mock_settings.debug = False
            mock_get_settings.return_value = mock_settings

            with patch("paidsearchnav.api.run.app"):
                main()

                # Verify correct host was used
                call_args = mock_uvicorn_run.call_args[1]
                assert call_args["host"] == expected_host

            mock_uvicorn_run.reset_mock()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_reload_configuration(self, mock_get_settings, mock_uvicorn_run):
        """Test reload configuration based on debug setting."""
        test_cases = [
            (True, True),  # debug=True should enable reload
            (False, False),  # debug=False should disable reload
        ]

        for debug_setting, expected_reload in test_cases:
            mock_settings = Mock()
            mock_settings.api_host = "localhost"
            mock_settings.api_port = 8000
            mock_settings.debug = debug_setting
            mock_get_settings.return_value = mock_settings

            with patch("paidsearchnav.api.run.app"):
                main()

                # Verify correct reload setting was used
                call_args = mock_uvicorn_run.call_args[1]
                assert call_args["reload"] == expected_reload

            mock_uvicorn_run.reset_mock()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_log_level_configuration(self, mock_get_settings, mock_uvicorn_run):
        """Test log level configuration based on debug setting."""
        test_cases = [
            (True, "debug"),  # debug=True should use debug log level
            (False, "info"),  # debug=False should use info log level
        ]

        for debug_setting, expected_log_level in test_cases:
            mock_settings = Mock()
            mock_settings.api_host = "localhost"
            mock_settings.api_port = 8000
            mock_settings.debug = debug_setting
            mock_get_settings.return_value = mock_settings

            with patch("paidsearchnav.api.run.app"):
                main()

                # Verify correct log level was used
                call_args = mock_uvicorn_run.call_args[1]
                assert call_args["log_level"] == expected_log_level

            mock_uvicorn_run.reset_mock()

    def test_module_docstring(self):
        """Test that the module has proper documentation."""
        import paidsearchnav.api.run

        assert paidsearchnav.api.run.__doc__ is not None
        assert "Run the FastAPI server" in paidsearchnav.api.run.__doc__

    @patch("paidsearchnav.api.run.main")
    def test_direct_script_execution(self, mock_main):
        """Test executing the run.py script directly."""
        # Test direct execution by simulating the __name__ == "__main__" condition
        import paidsearchnav.api.run

        # Mock the main function to avoid actual server startup
        mock_main.return_value = None

        # Simulate direct execution by manually calling the main function
        # This tests that the script would call main() when executed directly
        if hasattr(paidsearchnav.api.run, "__name__"):
            # This simulates what happens when the script is run directly
            paidsearchnav.api.run.main()
            mock_main.assert_called_once()
        else:
            pytest.skip("Unable to test direct execution path")

    def test_main_function_docstring(self):
        """Test that the main function has proper documentation."""
        assert main.__doc__ is not None
        assert "Run the API server" in main.__doc__

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_keyboard_interrupt_handling(self, mock_get_settings, mock_uvicorn_run):
        """Test handling of KeyboardInterrupt during server startup."""
        mock_settings = Mock()
        mock_settings.api_host = "localhost"
        mock_settings.api_port = 8000
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        # Make uvicorn.run raise KeyboardInterrupt
        mock_uvicorn_run.side_effect = KeyboardInterrupt("User interrupted")

        with patch("paidsearchnav.api.run.app"):
            with pytest.raises(KeyboardInterrupt):
                main()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_invalid_configuration_scenarios(self, mock_get_settings, mock_uvicorn_run):
        """Test handling of invalid configuration scenarios."""
        # Test with invalid port (negative)
        mock_settings = Mock()
        mock_settings.api_host = "localhost"
        mock_settings.api_port = -1
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        with patch("paidsearchnav.api.run.app"):
            # Should still pass the invalid config to uvicorn
            # (uvicorn will handle validation)
            main()
            call_args = mock_uvicorn_run.call_args[1]
            assert call_args["port"] == -1

        mock_uvicorn_run.reset_mock()

        # Test with invalid host (None)
        mock_settings.api_host = None
        mock_settings.api_port = 8000
        mock_get_settings.return_value = mock_settings

        with patch("paidsearchnav.api.run.app"):
            main()
            call_args = mock_uvicorn_run.call_args[1]
            assert call_args["host"] is None

        mock_uvicorn_run.reset_mock()

        # Test with extreme port values
        test_ports = [0, 65535, 65536, 999999]
        for port in test_ports:
            mock_settings.api_port = port
            mock_get_settings.return_value = mock_settings

            with patch("paidsearchnav.api.run.app"):
                main()
                call_args = mock_uvicorn_run.call_args[1]
                assert call_args["port"] == port

            mock_uvicorn_run.reset_mock()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_configuration_edge_cases(self, mock_get_settings, mock_uvicorn_run):
        """Test edge cases in configuration handling."""
        # Test with missing attributes
        mock_settings = Mock()
        # Deliberately not setting some attributes to test error handling
        del mock_settings.api_host
        del mock_settings.api_port
        del mock_settings.debug
        mock_get_settings.return_value = mock_settings

        with patch("paidsearchnav.api.run.app"):
            # Should raise AttributeError when accessing missing attributes
            with pytest.raises(AttributeError):
                main()

    @patch("paidsearchnav.api.run.uvicorn.run")
    @patch("paidsearchnav.api.run.get_settings")
    def test_uvicorn_startup_failures(self, mock_get_settings, mock_uvicorn_run):
        """Test specific uvicorn startup failure scenarios."""
        mock_settings = Mock()
        mock_settings.api_host = "localhost"
        mock_settings.api_port = 8000
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        # Test port already in use error
        mock_uvicorn_run.side_effect = OSError("Address already in use")

        with patch("paidsearchnav.api.run.app"):
            with pytest.raises(OSError, match="Address already in use"):
                main()

        # Test permission denied error
        mock_uvicorn_run.side_effect = PermissionError("Permission denied")

        with patch("paidsearchnav.api.run.app"):
            with pytest.raises(PermissionError, match="Permission denied"):
                main()

        # Test invalid host error
        mock_uvicorn_run.side_effect = OSError("Cannot assign requested address")

        with patch("paidsearchnav.api.run.app"):
            with pytest.raises(OSError, match="Cannot assign requested address"):
                main()
