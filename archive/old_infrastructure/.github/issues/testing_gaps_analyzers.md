# Add tests for remaining analyzer components

## Description
Several analyzers lack test coverage. These are core business logic components that perform the actual audit analysis.

## Components to Test
- [ ] `/analyzers/keyword_match.py` - Keyword match type analyzer
- [ ] `/analyzers/pmax.py` - Performance Max campaign analyzer
- [ ] `/analyzers/geo_performance.py` - Geographic performance analyzer

## Test Requirements
For each analyzer:
- Test the `analyze()` method with various data scenarios
- Test edge cases (empty data, null values, malformed data)
- Test recommendation generation logic
- Test metric calculations
- Test data aggregation logic
- Test performance with large datasets

## Specific Test Cases

### Keyword Match Analyzer
- Test match type distribution analysis
- Test recommendation thresholds
- Test cost efficiency calculations
- Test conversion rate comparisons

### Performance Max Analyzer
- Test asset group analysis
- Test performance metrics aggregation
- Test campaign type detection
- Test PMax-specific recommendations

### Geo Performance Analyzer
- Test location data parsing
- Test geographic aggregation
- Test performance by region calculations
- Test location-based recommendations

## Priority
**High** - Analyzers contain core business logic

## Acceptance Criteria
- [ ] Each analyzer has comprehensive unit tests
- [ ] Tests cover all public methods
- [ ] Tests verify recommendation accuracy
- [ ] Tests handle edge cases gracefully
- [ ] Performance tests with 1000+ data points