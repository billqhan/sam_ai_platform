"""
SAM produce web reports Lambda function package.
Generates daily web dashboards with match statistics.
"""

from .handler import lambda_handler
from .data_aggregator import DataAggregator, DailyStats
from .dashboard_generator import DashboardGenerator

__all__ = ['lambda_handler', 'DataAggregator', 'DailyStats', 'DashboardGenerator']