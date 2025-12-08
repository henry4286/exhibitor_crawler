"""
请求模式枚举

定义爬虫的请求模式类型
"""

from enum import Enum


class RequestMode(Enum):
    """请求模式枚举"""
    SINGLE = "single"      # 单次请求模式：直接从列表API获取完整数据
    DOUBLE = "double"      # 二次请求模式：先获取公司列表，再逐个获取详情
    
    @classmethod
    def from_string(cls, mode_str: str) -> 'RequestMode':
        """从字符串创建枚举值"""
        mode_str = (mode_str or "single").lower().strip()
        
        if mode_str in ("double", "detail", "two", "2"):
            return cls.DOUBLE
        else:
            return cls.SINGLE
