"""Example client code for PaidSearchNav API."""

import asyncio

import httpx


class PaidSearchNavClient:
    """Client for interacting with PaidSearchNav API."""

    def __init__(
        self, base_url: str = "http://localhost:8000", api_key: str | None = None
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.token: str | None = None
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key

    async def health_check(self) -> dict:
        """Check API health."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/health")
            response.raise_for_status()
            return response.json()

    async def init_google_auth(
        self, redirect_uri: str, state: str | None = None
    ) -> dict:
        """Initialize Google OAuth2 flow."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/auth/google/init",
                json={"redirect_uri": redirect_uri, "state": state},
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def complete_google_auth(self, code: str, state: str | None = None) -> str:
        """Complete Google OAuth2 flow and get access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/auth/google/callback",
                json={"code": code, "state": state},
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()
            self.token = data["access_token"]
            self.headers["Authorization"] = f"Bearer {self.token}"
            return self.token

    async def create_audit(
        self,
        customer_id: str,
        name: str | None = None,
        analyzers: list[str] | None = None,
    ) -> dict:
        """Create a new audit."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/audits",
                json={
                    "customer_id": customer_id,
                    "name": name,
                    "analyzers": analyzers,
                },
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_audit(self, audit_id: str) -> dict:
        """Get audit details."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/audits/{audit_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def list_audits(
        self,
        customer_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """List audits with pagination."""
        params = {"page": page, "per_page": per_page}
        if customer_id:
            params["customer_id"] = customer_id

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/audits",
                params=params,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_results(self, audit_id: str) -> dict:
        """Get audit results."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/results/{audit_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def generate_report(
        self,
        audit_id: str,
        format: str = "html",
        template: str | None = None,
    ) -> dict:
        """Generate a report for an audit."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/reports/{audit_id}/generate",
                json={"format": format, "template": template},
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()


async def main():
    """Example usage of the API client."""
    # Initialize client
    client = PaidSearchNavClient()

    # Check health
    print("Checking API health...")
    health = await client.health_check()
    print(f"API Status: {health['status']}")
    print(f"Version: {health['version']}")

    # Initialize OAuth2 flow
    print("\nInitializing Google OAuth2...")
    auth_data = await client.init_google_auth("http://localhost:3000/auth/callback")
    print(f"Auth URL: {auth_data['auth_url']}")

    # After user completes OAuth2 flow, exchange code for token
    # auth_code = "code_from_google"
    # token = await client.complete_google_auth(auth_code)
    # print(f"Access Token: {token}")

    # Create an audit (requires authentication)
    # audit = await client.create_audit(
    #     customer_id="1234567890",
    #     name="Q4 2024 Audit",
    #     analyzers=["keyword_match", "search_terms", "geo_performance"]
    # )
    # print(f"Created audit: {audit['id']}")

    # Get audit status
    # audit_details = await client.get_audit(audit['id'])
    # print(f"Audit status: {audit_details['status']}")

    # Get results when complete
    # results = await client.get_results(audit['id'])
    # print(f"Total recommendations: {results['summary']['total_recommendations']}")

    # Generate report
    # report = await client.generate_report(audit['id'], format="pdf")
    # print(f"Report URL: {report['download_url']}")


if __name__ == "__main__":
    asyncio.run(main())
