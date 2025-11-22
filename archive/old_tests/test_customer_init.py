#!/usr/bin/env python3
"""
Test script for customer initialization functionality.
Creates a test user and customer, then tests the initialization endpoint.
"""

import asyncio
import uuid
from datetime import datetime

import asyncpg
import httpx

from paidsearchnav.api.dependencies import create_access_token
from paidsearchnav.core.config import Settings


async def create_test_data():
    """Create test user and customer in the database."""
    # Connect to the database
    conn = await asyncpg.connect(
        host="localhost",
        port=5434,
        user="devuser",
        password="devpass123",
        database="paidsearchnav_dev",
    )

    try:
        # Create test user
        user_id = "test_user_12345"
        await conn.execute(
            """
            INSERT INTO users (id, email, name, user_type, is_active, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO NOTHING
        """,
            user_id,
            "test@fitnessconnection.com",
            "Test User",
            "agency",
            True,
            datetime.utcnow(),
            datetime.utcnow(),
        )

        # Create Fitness Connection customer
        customer_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO customers (id, name, email, google_ads_customer_id, user_type, is_active, created_at, updated_at, settings, user_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (id) DO NOTHING
        """,
            customer_id,
            "Fitness Connection",
            "info@fitnessconnection.com",
            "646-990-6417",
            "agency",
            True,
            datetime.utcnow(),
            datetime.utcnow(),
            "{}",
            user_id,
        )

        # Link user to customer
        access_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO customer_access (id, user_id, customer_id, access_level, is_active, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id, customer_id) DO NOTHING
        """,
            access_id,
            user_id,
            customer_id,
            "admin",
            True,
            datetime.utcnow(),
            datetime.utcnow(),
        )

        print(f"Created test user: {user_id}")
        print(f"Created test customer: {customer_id} (Fitness Connection)")
        return user_id, customer_id

    finally:
        await conn.close()


async def test_customer_initialization():
    """Test the customer initialization endpoint."""

    print("Creating test data...")
    user_id, customer_id = await create_test_data()

    # Load settings
    settings = Settings.from_env()

    # Create JWT token for test user
    token_data = {
        "sub": user_id,
        "email": "test@fitnessconnection.com",
        "name": "Test User",
        "id": user_id,
        "customer_id": customer_id,
        "is_admin": True,
        "roles": ["admin"],
    }

    access_token = create_access_token(token_data, settings)
    print(f"Generated JWT token: {access_token[:50]}...")

    # Test the API endpoints
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    base_url = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test health endpoint
        print("\nTesting health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"Health check: {response.status_code} - {response.json()}")

        # Test get customer endpoint
        print(f"\nTesting get customer endpoint for {customer_id}...")
        response = await client.get(
            f"{base_url}/api/v1/customers/{customer_id}", headers=headers
        )
        print(f"Get customer: {response.status_code}")
        if response.status_code == 200:
            customer_data = response.json()
            print(f"Customer name: {customer_data.get('name')}")
            print(f"Google Ads ID: {customer_data.get('google_ads_customer_id')}")
        else:
            print(f"Error: {response.text}")

        # Test customer initialization endpoint
        print(f"\nTesting customer initialization endpoint for {customer_id}...")
        response = await client.post(
            f"{base_url}/api/v1/customers/{customer_id}/initialize", headers=headers
        )
        print(f"Initialize customer: {response.status_code}")

        if response.status_code == 200:
            init_data = response.json()
            print("✅ Customer initialization successful!")
            print(f"Status: {init_data.get('status')}")
            print(f"S3 folder created: {init_data.get('s3_folder_created')}")
            print(f"S3 base path: {init_data.get('s3_base_path')}")
            print(f"Google Ads validated: {init_data.get('google_ads_validated')}")
            print(f"Duration: {init_data.get('duration_seconds')} seconds")
            if init_data.get("warnings"):
                print(f"Warnings: {init_data.get('warnings')}")
        else:
            print(f"❌ Error initializing customer: {response.status_code}")
            print(f"Response: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_customer_initialization())
