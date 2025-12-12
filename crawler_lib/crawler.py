"""
爬虫核心模块

主爬虫类，协调各模块完成数据抓取任务

此文件保持向后兼容性，所有类都从各自的模块中导入
"""

# 从各个模块导入所有类和异常
from .exceptions import ParseError
from .base_crawler import BaseCrawler
from .company_crawler import CompanyCrawler
from .double_fetch_crawler import DoubleFetchCrawler

# 保持原有的模块级别变量和函数（如果有的话）
__all__ = [
    'ParseError',
    'BaseCrawler', 
    'CompanyCrawler',
    'DoubleFetchCrawler'
]
