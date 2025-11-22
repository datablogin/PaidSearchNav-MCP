# Add tests for API security and authentication components

## Description
Critical security components lack test coverage, particularly JWT validation and authentication logic. This poses a significant risk for security vulnerabilities.

## Components to Test
- [ ] `/api/dependencies.py` - Core dependencies including:
  - JWT token validation
  - User authentication from tokens
  - Password hashing and verification
  - Current user extraction
- [ ] `/api/auth_security.py` - Security implementation details
- [ ] `/api/models/requests.py` - Request validation models
- [ ] `/api/models/responses.py` - Response models
- [ ] `/api/utils/validation.py` - Input validation utilities

## Test Requirements
- Test JWT token generation and validation
- Test expired token handling
- Test invalid token formats
- Test password hashing security
- Test user authentication flow
- Test request validation against schemas
- Test SQL injection prevention
- Test XSS prevention in inputs

## Security Test Scenarios
- Invalid JWT signatures
- Expired tokens
- Missing required claims
- Malformed tokens
- Password complexity validation
- Timing attack resistance
- Rate limiting enforcement

## Priority
**Critical** - Security components are fundamental to application safety

## Acceptance Criteria
- [ ] 100% test coverage for authentication logic
- [ ] Tests verify all security edge cases
- [ ] Tests confirm proper error messages (no information leakage)
- [ ] Tests validate cryptographic implementations
- [ ] Performance tests for password hashing