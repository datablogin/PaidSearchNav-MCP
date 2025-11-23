"""Tests for core exceptions module."""

import pickle

import pytest

from paidsearchnav_mcp.core.exceptions import (
    AnalysisError,
    APIError,
    AuthenticationError,
    ConfigurationError,
    PaidSearchNavError,
    RateLimitError,
    StorageError,
    ValidationError,
)


class TestPaidSearchNavError:
    """Test base PaidSearchNavError exception."""

    def test_inheritance(self) -> None:
        """Test that PaidSearchNavError inherits from Exception."""
        assert issubclass(PaidSearchNavError, Exception)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = PaidSearchNavError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, PaidSearchNavError)
        assert isinstance(error, Exception)

    def test_with_no_message(self) -> None:
        """Test instantiation without message."""
        error = PaidSearchNavError()
        assert str(error) == ""

    def test_with_args(self) -> None:
        """Test instantiation with multiple args."""
        error = PaidSearchNavError("Error", 123, {"key": "value"})
        assert error.args == ("Error", 123, {"key": "value"})

    def test_raise_and_catch(self) -> None:
        """Test raising and catching the exception."""
        with pytest.raises(PaidSearchNavError) as exc_info:
            raise PaidSearchNavError("Test error")
        assert str(exc_info.value) == "Test error"


class TestAPIError:
    """Test APIError exception."""

    def test_inheritance(self) -> None:
        """Test inheritance hierarchy."""
        assert issubclass(APIError, PaidSearchNavError)
        assert issubclass(APIError, Exception)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = APIError("API call failed")
        assert str(error) == "API call failed"
        assert isinstance(error, APIError)
        assert isinstance(error, PaidSearchNavError)

    def test_catch_as_base_exception(self) -> None:
        """Test catching APIError as PaidSearchNavError."""
        try:
            raise APIError("API error")
        except PaidSearchNavError as e:
            assert isinstance(e, APIError)
            assert str(e) == "API error"
        else:
            pytest.fail("Exception not raised")


class TestAuthenticationError:
    """Test AuthenticationError exception."""

    def test_inheritance(self) -> None:
        """Test inheritance hierarchy."""
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(AuthenticationError, PaidSearchNavError)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = AuthenticationError("Invalid credentials")
        assert str(error) == "Invalid credentials"
        assert isinstance(error, AuthenticationError)
        assert isinstance(error, APIError)
        assert isinstance(error, PaidSearchNavError)

    def test_catch_hierarchy(self) -> None:
        """Test catching at different levels of hierarchy."""
        # Catch as AuthenticationError
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Auth failed")

        # Catch as APIError
        with pytest.raises(APIError):
            raise AuthenticationError("Auth failed")

        # Catch as PaidSearchNavError
        with pytest.raises(PaidSearchNavError):
            raise AuthenticationError("Auth failed")


class TestRateLimitError:
    """Test RateLimitError exception."""

    def test_inheritance(self) -> None:
        """Test inheritance hierarchy."""
        assert issubclass(RateLimitError, APIError)
        assert issubclass(RateLimitError, PaidSearchNavError)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = RateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"
        assert isinstance(error, RateLimitError)
        assert isinstance(error, APIError)

    def test_with_retry_after(self) -> None:
        """Test with retry-after information."""
        error = RateLimitError("Rate limit exceeded, retry after 60 seconds")
        assert "60 seconds" in str(error)


class TestAnalysisError:
    """Test AnalysisError exception."""

    def test_inheritance(self) -> None:
        """Test inheritance hierarchy."""
        assert issubclass(AnalysisError, PaidSearchNavError)
        # Not a subclass of APIError
        assert not issubclass(AnalysisError, APIError)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = AnalysisError("Analysis failed")
        assert str(error) == "Analysis failed"
        assert isinstance(error, AnalysisError)
        assert isinstance(error, PaidSearchNavError)

    def test_with_details(self) -> None:
        """Test with analysis details."""
        error = AnalysisError("Analysis failed for customer 123")
        assert "customer 123" in str(error)


class TestValidationError:
    """Test ValidationError exception."""

    def test_inheritance(self) -> None:
        """Test inheritance hierarchy."""
        assert issubclass(ValidationError, PaidSearchNavError)
        assert not issubclass(ValidationError, APIError)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = ValidationError("Invalid data")
        assert str(error) == "Invalid data"
        assert isinstance(error, ValidationError)

    def test_with_field_info(self) -> None:
        """Test with field validation info."""
        error = ValidationError("Field 'email' is required")
        assert "email" in str(error)
        assert "required" in str(error)


class TestConfigurationError:
    """Test ConfigurationError exception."""

    def test_inheritance(self) -> None:
        """Test inheritance hierarchy."""
        assert issubclass(ConfigurationError, PaidSearchNavError)
        assert not issubclass(ConfigurationError, APIError)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = ConfigurationError("Invalid configuration")
        assert str(error) == "Invalid configuration"
        assert isinstance(error, ConfigurationError)

    def test_with_config_details(self) -> None:
        """Test with configuration details."""
        error = ConfigurationError("Missing required config: API_KEY")
        assert "API_KEY" in str(error)


class TestStorageError:
    """Test StorageError exception."""

    def test_inheritance(self) -> None:
        """Test inheritance hierarchy."""
        assert issubclass(StorageError, PaidSearchNavError)
        assert not issubclass(StorageError, APIError)

    def test_instantiation(self) -> None:
        """Test basic instantiation."""
        error = StorageError("Storage operation failed")
        assert str(error) == "Storage operation failed"
        assert isinstance(error, StorageError)

    def test_with_operation_details(self) -> None:
        """Test with operation details."""
        error = StorageError("Failed to save analysis: disk full")
        assert "disk full" in str(error)


class TestExceptionSerialization:
    """Test exception serialization capabilities."""

    def test_pickle_base_exception(self) -> None:
        """Test that base exception can be pickled."""
        error = PaidSearchNavError("Test error")
        pickled = pickle.dumps(error)
        unpickled = pickle.loads(pickled)
        assert str(unpickled) == "Test error"
        assert type(unpickled) is type(PaidSearchNavError())

    def test_pickle_api_error(self) -> None:
        """Test that APIError can be pickled."""
        error = APIError("API error", {"code": 500})
        pickled = pickle.dumps(error)
        unpickled = pickle.loads(pickled)
        assert unpickled.args == ("API error", {"code": 500})
        assert type(unpickled) is type(APIError())

    def test_pickle_authentication_error(self) -> None:
        """Test that AuthenticationError can be pickled."""
        error = AuthenticationError("Auth failed")
        pickled = pickle.dumps(error)
        unpickled = pickle.loads(pickled)
        assert str(unpickled) == "Auth failed"
        assert type(unpickled) is type(AuthenticationError())

    @pytest.mark.parametrize(
        "exception_class,message",
        [
            (PaidSearchNavError, "Base error"),
            (APIError, "API error"),
            (AuthenticationError, "Auth error"),
            (RateLimitError, "Rate limit"),
            (AnalysisError, "Analysis error"),
            (ValidationError, "Validation error"),
            (ConfigurationError, "Config error"),
            (StorageError, "Storage error"),
        ],
    )
    def test_pickle_all_exceptions(
        self, exception_class: type[Exception], message: str
    ) -> None:
        """Test that all exception types can be pickled."""
        error = exception_class(message)
        pickled = pickle.dumps(error)
        unpickled = pickle.loads(pickled)
        assert str(unpickled) == str(error)
        assert type(unpickled) is type(error)


class TestExceptionHierarchy:
    """Test the complete exception hierarchy."""

    def test_complete_hierarchy(self) -> None:
        """Test that all exceptions follow the expected hierarchy."""
        # All exceptions should inherit from PaidSearchNavError
        all_exceptions = [
            APIError,
            AuthenticationError,
            RateLimitError,
            AnalysisError,
            ValidationError,
            ConfigurationError,
            StorageError,
        ]

        for exc_class in all_exceptions:
            assert issubclass(exc_class, PaidSearchNavError)

        # API-related exceptions
        api_exceptions = [AuthenticationError, RateLimitError]
        for exc_class in api_exceptions:
            assert issubclass(exc_class, APIError)

        # Non-API exceptions should not inherit from APIError
        non_api_exceptions = [
            AnalysisError,
            ValidationError,
            ConfigurationError,
            StorageError,
        ]
        for exc_class in non_api_exceptions:
            assert not issubclass(exc_class, APIError)

    def _assert_exception_caught(
        self, exception: Exception, catch_type: type[Exception]
    ) -> None:
        """Helper to assert an exception is caught by a specific type."""
        try:
            raise exception
        except catch_type:
            pass  # Expected
        else:
            pytest.fail(
                f"Exception {type(exception).__name__} not caught by {catch_type.__name__}"
            )

    def _assert_exception_not_caught(
        self, exception: Exception, catch_type: type[Exception]
    ) -> None:
        """Helper to assert an exception is NOT caught by a specific type."""
        with pytest.raises(type(exception)):
            try:
                raise exception
            except catch_type:
                pytest.fail(
                    f"Exception {type(exception).__name__} incorrectly caught by {catch_type.__name__}"
                )

    def test_exception_catching_patterns(self) -> None:
        """Test common exception catching patterns."""
        # Pattern 1: All exceptions should be caught by PaidSearchNavError
        all_exceptions = [
            APIError("api"),
            AuthenticationError("auth"),
            RateLimitError("rate"),
            AnalysisError("analysis"),
            ValidationError("validation"),
            ConfigurationError("config"),
            StorageError("storage"),
        ]

        for exc in all_exceptions:
            self._assert_exception_caught(exc, PaidSearchNavError)

        # Pattern 2: Only API errors should be caught by APIError
        api_errors = [
            APIError("api"),
            AuthenticationError("auth"),
            RateLimitError("rate"),
        ]

        for exc in api_errors:
            self._assert_exception_caught(exc, APIError)

        # Pattern 3: Non-API errors should NOT be caught by APIError
        non_api_errors = [
            AnalysisError("analysis"),
            ValidationError("validation"),
            ConfigurationError("config"),
            StorageError("storage"),
        ]

        for exc in non_api_errors:
            self._assert_exception_not_caught(exc, APIError)


class TestExceptionMessages:
    """Test exception message handling."""

    def test_empty_messages(self) -> None:
        """Test exceptions with empty messages."""
        exceptions = [
            PaidSearchNavError(),
            APIError(),
            AuthenticationError(),
            RateLimitError(),
            AnalysisError(),
            ValidationError(),
            ConfigurationError(),
            StorageError(),
        ]

        for exc in exceptions:
            assert str(exc) == ""

    def test_unicode_messages(self) -> None:
        """Test exceptions with unicode messages."""
        message = "Error with émoji 🚀 and unicode ñ"
        exceptions = [
            PaidSearchNavError(message),
            APIError(message),
            ValidationError(message),
        ]

        for exc in exceptions:
            assert str(exc) == message

    def test_multiline_messages(self) -> None:
        """Test exceptions with multiline messages."""
        message = """Error occurred:
        - Line 1
        - Line 2
        Details: Something went wrong"""

        error = AnalysisError(message)
        assert str(error) == message
        assert "Line 1" in str(error)
        assert "Line 2" in str(error)
