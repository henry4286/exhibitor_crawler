"""
公司信息爬虫库

模块化的爬虫框架，支持从不同API抓取公司信息
"""

from .config_manager import ConfigManager, CrawlerConfig
from .excel_exporter import ExcelExporter
from .http_client import HttpClient
from .data_parser import DataParser
from .utils import get_nested_value
from .crawler import CompanyCrawler, DoubleFetchCrawler, BaseCrawler, ParseError

__all__ = [
    'ConfigManager',
    'CrawlerConfig',
    'ExcelExporter',
    'HttpClient',
    'DataParser',
    'CompanyCrawler',
    'DoubleFetchCrawler',
    'BaseCrawler',
    'ParseError',
    'get_nested_value',
]

__version__ = '2.0.0'
