"""GraphQL type definitions."""

from .analysis import AnalysisResult, AnalyzerType
from .audit import (
    Audit,
    AuditProgress,
    AuditStatus,
    ScheduleAuditInput,
    TriggerAuditInput,
)
from .common import Connection, DateRange, PageInfo
from .customer import Customer, CustomerFilter
from .job import ScheduledJob
from .recommendation import Priority, Recommendation, RecommendationStatus

__all__ = [
    "Audit",
    "AuditProgress",
    "AuditStatus",
    "TriggerAuditInput",
    "ScheduleAuditInput",
    "Customer",
    "CustomerFilter",
    "AnalysisResult",
    "AnalyzerType",
    "Recommendation",
    "Priority",
    "RecommendationStatus",
    "DateRange",
    "PageInfo",
    "Connection",
    "ScheduledJob",
]
