from paidsearchnav.api.dependencies import create_access_token
from paidsearchnav.core.config import Settings

# Load settings from environment (.env or PSN_* variables)
settings = Settings.from_env()

# Create token for test user (include required 'customer_id')
token_data = {
    "sub": "test_user_12345",
    "email": "test@fitnessconnection.com",
    "name": "Test User",
    "id": "test_user_12345",
    "customer_id": "cust_1234567890",  # REQUIRED for API access
    "is_admin": True,
    "roles": ["admin"],
}

# Use the imported function
token = create_access_token(token_data, settings)
print(f"JWT Token: {token}")
