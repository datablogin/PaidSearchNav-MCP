# GitHub Issues: CSV Parser Development for PaidSearchNav

---

### 🛠️ Issue 1: Create CSV Parser Module Structure

**Description:** Set up a new module at `paidsearchnav/parsers/` containing:

- `__init__.py`
- `base.py` (base parser interface)
- `csv_parser.py` (main implementation)
- `field_mappings.py` (field maps)

**Acceptance Criteria / KPIs:**

- Folder and files present and importable
- All files pass `flake8` / `black` formatting
- No unused imports

---

### 🛠️ Issue 2: Implement BaseCSVParser Abstract Class

**Description:** Write an abstract base class `BaseCSVParser` with `parse()` and `validate_headers()` methods, using Python generics.

**KPIs:**

- Type annotations complete
- `abc.ABC` used properly
- Unit test with dummy subclass showing interface enforces requirements

---

### 🛠️ Issue 3: Define Field Mapping Dictionaries

**Description:** Populate `field_mappings.py` with mappings for:

- `Keyword`
- `SearchTerm`
- `GeoPerformanceData`

**KPIs:**

- Mappings match Google Ads export headers exactly
- Unit test asserts that all required Pydantic fields are covered
- Comments describe each mapping clearly

---

### 🛠️ Issue 4: Implement GoogleAdsCSVParser Main Logic

**Description:** In `csv_parser.py`, implement:

- Column renaming
- Dict row conversion
- Data cleanup for null fields
- Special case: `SearchTerm` → detect local intent

**KPIs:**

- Unit tests parse all 3 model types with real or test CSVs
-
  > \= 95% test coverage on `csv_parser.py`
- Handles UTF-8 encoded CSV

---

### 🛠️ Issue 5: CLI Integration: `parse-csv` Command

**Description:** Add a CLI entry point using Click:

```bash
paidsearchnav parse-csv --file keywords.csv --type keyword
```

**KPIs:**

- CLI parses valid files and prints record count
- Errors reported gracefully on bad file or type
- Unit test simulates CLI call

---

### 🛠️ Issue 6: API Upload Endpoint for CSV Parsing

**Description:** In `api/v1/uploads.py`, implement:

```http
POST /api/v1/upload/csv
```

- Accepts `UploadFile`
- Accepts `data_type` query param
- Returns JSON `{ parsed: N }`

**KPIs:**

- Endpoint accessible at `/api/v1/upload/csv`
- OpenAPI schema generated correctly
- Unit tests for all 3 data types

---

### 🛠️ Issue 7: Error Handling and Validation Coverage

**Description:** Implement robust handling for:

- Missing required headers
- Invalid values (e.g., non-numeric cost)
- Empty rows / blank files

**KPIs:**

- Unit tests exercise all error paths
- Appropriate HTTP 400 response from API
- Clear CLI error output with non-zero exit code

---

### 🛠️ Issue 8: Performance Consideration for Large Files

**Description:** Add support for reading large files using pandas chunking in `GoogleAdsCSVParser`.

**KPIs:**

- CLI can parse files > 100,000 rows in < 60 seconds
- No excessive memory usage for 50 MB files

---

