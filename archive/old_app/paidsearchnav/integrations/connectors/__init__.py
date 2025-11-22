"""CRM platform connectors."""

from .hubspot import HubSpotConnector
from .salesforce import SalesforceConnector

__all__ = ["HubSpotConnector", "SalesforceConnector"]
