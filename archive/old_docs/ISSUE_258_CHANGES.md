# Issue #258: Error Handling and Validation Coverage

## Summary of Changes

This PR implements robust error handling and validation for CSV parsing in both the CLI and API, addressing issue #258. All recommendations from Claude's review have been implemented.

## Changes Made

### Claude Review Recommendations Implemented

1. **Added charset-normalizer as optional dependency** - Added to `pyproject.toml` under `[project.optional-dependencies.encoding]`
2. **Fixed lenient mode behavior** - Invalid numeric fields now get default values (0/0.0) rather than causing row skip
3. **Verified rate limiting and request size validation** - Already implemented via `RequestLimitMiddleware` (10MB limit)
4. **Replaced magic numbers with constants** - Added `MAX_FILE_SIZE_BYTES`, `ENCODING_DETECTION_SAMPLE_SIZE`, `BYTES_PER_MB`
5. **Improved error messages** - Added examples of valid formats in error messages
6. **Added comprehensive CSV injection tests** - Added `test_comprehensive_csv_injection_protection`
7. **Enhanced docstrings** - Documented error handling behavior in class and method docstrings

### 1. Enhanced CSV Parser (`paidsearchnav/parsers/csv_parser.py`)

- **Empty File Handling**: Added check for empty CSV files (0 bytes)
- **Empty Rows Handling**: Added logic to remove and detect files with only empty rows
- **Invalid Numeric Values**: Enhanced validation for numeric fields with:
  - Currency symbol removal ($, commas)
  - Percentage value handling (e.g., "5.5%" → 0.055)
  - Strict validation mode that raises errors
  - Lenient mode that logs warnings and skips invalid fields
- **Encoding Detection**: Added automatic encoding detection using charset-normalizer (optional dependency)
- **Better Error Messages**: More descriptive error messages for all validation failures

### 2. Enhanced API Error Handling (`paidsearchnav/api/v1/upload.py`)

- Added specific HTTP 400 responses for different error types:
  - Missing required fields
  - Empty CSV files or no data rows
  - Encoding errors
  - Invalid numeric values
  - CSV format errors
  - File size exceeded
- Improved error message mapping to provide clear, user-friendly feedback

### 3. Comprehensive Test Coverage

Created three new test files with extensive error scenario coverage:

#### `tests/unit/parsers/test_csv_parser_errors.py`
- Tests for empty CSV files
- Tests for CSV with only headers
- Tests for CSV with only empty rows
- Tests for missing required headers
- Tests for invalid numeric values (strict and lenient modes)
- Tests for currency and percentage value parsing
- Tests for malformed CSV structure
- Tests for encoding error detection
- Tests for file size limits
- Tests for special characters handling
- Tests for duplicate headers
- Tests for geo performance with invalid location types

#### `tests/api/test_upload_errors.py`
- Tests for all error scenarios in the upload endpoint
- Tests for proper HTTP status codes and error messages
- Tests for filename sanitization
- Tests for various edge cases

#### `tests/unit/cli/test_parse_csv_errors.py`
- Tests for CLI error handling and exit codes
- Tests for clear error messages in CLI output
- Tests for validation mode behavior

## KPIs Met

✅ Unit tests exercise all error paths
✅ Appropriate HTTP 400 responses from API
✅ Clear CLI error output with non-zero exit codes
✅ Informative error messages for users

## Testing

All tests pass:
- Original tests remain passing (no regression)
- 47 new error handling tests added
- Code formatted with ruff
- Type annotations improved where needed