"""
请求处理 Mixin

提供通用的请求处理方法，可被多个类复用
"""

from typing import Optional, Dict, Any, List


class RequestMixin:
    """
    请求处理 Mixin 类
    
    提供通用的HTTP请求处理方法，包括：
    - 占位符替换
    - 参数解析
    - 请求发送
    - 日志记录
    - 数据提取和解析
    
    使用此 Mixin 的类需要具备：
    - self.http_client: HttpClient 实例
    - self.data_parser: DataParser 实例
    """
    
    