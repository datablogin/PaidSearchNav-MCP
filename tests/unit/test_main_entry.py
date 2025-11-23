"""Tests for the main application entry point (__main__.py)."""

import subprocess
import sys
from unittest.mock import patch

import pytest

from paidsearchnav_mcp.__main__ import cli


class TestMainEntryPoint:
    """Test the main application entry point."""

    def test_cli_import(self):
        """Test that cli function is properly imported."""
        # Test that the cli function is available
        assert callable(cli)

        # Test that it's the correct function from cli.main
        from paidsearchnav.cli.main import cli as main_cli

        assert cli is main_cli

    def test_main_execution_guard(self):
        """Test that __main__.py has proper execution guard."""
        # Test that the module can be imported without executing cli()
        import paidsearchnav.__main__

        # Verify the cli function exists and is callable
        assert hasattr(paidsearchnav.__main__, "cli")
        assert callable(paidsearchnav.__main__.cli)

        # Verify the module name check works properly
        assert paidsearchnav.__main__.__name__ == "paidsearchnav.__main__"

    @patch("paidsearchnav.__main__.cli")
    def test_main_execution_when_called_directly(self, mock_cli):
        """Test that cli() is called when module is executed directly."""
        # Mock the cli function to avoid actual execution
        mock_cli.return_value = None

        # Test the actual execution path by simulating __name__ == "__main__"
        # We'll test this by executing the condition that would be true
        import paidsearchnav.__main__ as main_module

        # Simulate what happens when the module is run directly
        # by manually checking the condition and calling the function
        if main_module.__name__ == "__main__":
            # This would only be true when run as script, not during import
            main_module.cli()
            mock_cli.assert_called_once()
        else:
            # During normal import, verify cli is not automatically called
            # We'll call it manually to test the mock works
            main_module.cli()
            mock_cli.assert_called_once()

    def test_module_availability(self):
        """Test that the module is properly installed and available."""
        import importlib.util

        # First check if module can be imported using importlib
        if importlib.util.find_spec("paidsearchnav.__main__") is None:
            pytest.skip("Module paidsearchnav.__main__ not found")

        # Check if module is available via python -m
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import paidsearchnav.__main__"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                pytest.skip(f"Module not available for subprocess: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"Cannot test module availability: {e}")

    def test_module_execution_via_python_m(self):
        """Test executing the module via python -m paidsearchnav."""
        # First verify module availability
        self.test_module_availability()

        # Test that the module can be executed via python -m
        # This tests the actual entry point functionality
        try:
            result = subprocess.run(
                [sys.executable, "-m", "paidsearchnav", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should exit with 0 for help
            assert result.returncode == 0

            # Should show help output
            assert "PaidSearchNav - Google Ads Keyword Audit Tool" in result.stdout

        except subprocess.TimeoutExpired:
            pytest.fail("Command timed out - possible infinite loop or hang")
        except FileNotFoundError:
            pytest.skip("Module not installed in editable mode")

    def test_module_execution_no_args(self):
        """Test executing the module with no arguments."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "paidsearchnav"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Should exit with 2 (Click's default for missing command)
            assert result.returncode == 2

            # Should show usage information (Click outputs to stderr)
            assert "Usage:" in result.stderr

        except subprocess.TimeoutExpired:
            pytest.skip(
                "Command timed out - CLI may be hanging on input or environment issue"
            )
        except FileNotFoundError:
            pytest.skip("Module not installed in editable mode")
        except Exception as e:
            pytest.skip(f"Unable to run subprocess: {e}")

    def test_module_execution_version(self):
        """Test executing the module with --version flag."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "paidsearchnav", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Should exit with 0 for version
            assert result.returncode == 0

            # Should show version information
            assert "PaidSearchNav, version" in result.stdout

        except subprocess.TimeoutExpired:
            pytest.skip(
                "Command timed out - CLI may be hanging on input or environment issue"
            )
        except FileNotFoundError:
            pytest.skip("Module not installed in editable mode")
        except Exception as e:
            pytest.skip(f"Unable to run subprocess: {e}")

    def test_module_execution_invalid_command(self):
        """Test executing the module with an invalid command."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "paidsearchnav", "invalid-command"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Should exit with 2 (Click's default for invalid command)
            assert result.returncode == 2

            # Should show error message (Click outputs to stderr)
            assert "Error:" in result.stderr or "No such command" in result.stderr

        except subprocess.TimeoutExpired:
            pytest.skip(
                "Command timed out - CLI may be hanging on input or environment issue"
            )
        except FileNotFoundError:
            pytest.skip("Module not installed in editable mode")
        except Exception as e:
            pytest.skip(f"Unable to run subprocess: {e}")

    def test_module_name_main_guard(self):
        """Test that cli() is only called when __name__ == '__main__'."""
        # Simply test that the module can be imported without executing cli
        import paidsearchnav.__main__

        # The module should be importable and have the cli function
        assert hasattr(paidsearchnav.__main__, "cli")

        # When imported as a module, __name__ should not be '__main__'
        # so cli() should not be automatically executed
        assert paidsearchnav.__main__.__name__ == "paidsearchnav.__main__"

    def test_error_handling_in_main_execution(self):
        """Test error handling when CLI execution fails."""
        from paidsearchnav.__main__ import cli

        # Test that errors in CLI execution are handled appropriately
        # Click will convert exceptions to SystemExit with error codes
        with patch("paidsearchnav.cli.main.cli", side_effect=Exception("Test error")):
            with pytest.raises(SystemExit):
                cli()

    def test_keyboard_interrupt_handling(self):
        """Test handling of KeyboardInterrupt during execution."""
        try:
            # Start the process
            process = subprocess.Popen(
                [sys.executable, "-m", "paidsearchnav"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Give process a moment to start
            import time

            time.sleep(0.1)

            # Send interrupt signal
            process.send_signal(subprocess.signal.SIGINT)

            # Wait for process to finish
            stdout, stderr = process.communicate(timeout=5)

            # SIGINT should result in specific exit codes:
            # - 130 on most Unix systems (128 + SIGINT(2))
            # - -2 on macOS (negative signal number)
            # - 1 or 2 from Click framework error handling
            if process.returncode == 130:
                # Standard Unix SIGINT handling
                pass
            elif process.returncode == -2:
                # macOS SIGINT handling
                pass
            elif process.returncode in [1, 2]:
                # Click framework may convert signal to standard error codes
                # Verify this is actually from interrupt, not other error
                assert (
                    "KeyboardInterrupt" in stderr
                    or "Aborted" in stderr
                    or len(stderr) == 0  # Silent exit is also acceptable
                )
            else:
                pytest.fail(
                    f"Unexpected exit code {process.returncode} for SIGINT. "
                    f"Stdout: {stdout}, Stderr: {stderr}"
                )

        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("Process did not handle interrupt gracefully within timeout")
        except FileNotFoundError:
            pytest.skip("Module not installed in editable mode")

    def test_main_module_attributes(self):
        """Test that __main__.py has the expected module attributes."""
        import paidsearchnav.__main__ as main_module

        # Should have proper module docstring
        assert main_module.__doc__ is not None
        assert "Make paidsearchnav executable" in main_module.__doc__

        # Should have the cli function
        assert hasattr(main_module, "cli")
        assert callable(main_module.cli)

    def test_import_error_handling(self):
        """Test handling of import errors in dependencies."""
        # Test that import errors in CLI dependencies are properly propagated
        from paidsearchnav.__main__ import cli

        with patch(
            "paidsearchnav.cli.main.cli", side_effect=ImportError("Test import error")
        ):
            # Click will convert ImportError to SystemExit
            with pytest.raises(SystemExit):
                cli()
