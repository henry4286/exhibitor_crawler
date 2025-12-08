"""
公司信息爬虫库

模块化的爬虫框架，支持从不同API抓取公司信息
"""

from .config_manager import ConfigManager, CrawlerConfig
from .excel_exporter import ExcelExporter
from .http_client import HttpClient
from .data_parser import DataParser
from .utils import get_nested_value, write_status_file
from .crawler import CompanyCrawler , DoubleFetchCrawler

__all__ = [
    'ConfigManager',
    'CrawlerConfig',
    'ExcelExporter',
    'HttpClient',
    'DataParser',
    'CompanyCrawler',
    'DoubleFetchCrawler',
    'get_nested_value',
    'write_status_file',
]

__version__ = '2.0.0'
