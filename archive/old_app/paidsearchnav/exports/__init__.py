"""Data export pipeline for enterprise analytics integration."""

from .base import ExportConfig, ExportDestination, ExportResult


# Lazy imports to avoid import errors during testing
def get_bigquery_exporter():
    """Lazy import of BigQueryExporter."""
    from .bigquery import BigQueryExporter

    return BigQueryExporter


def get_export_manager():
    """Lazy import of ExportManager."""
    from .manager import ExportManager

    return ExportManager


__all__ = [
    "ExportDestination",
    "ExportConfig",
    "ExportResult",
    "get_bigquery_exporter",
    "get_export_manager",
]
