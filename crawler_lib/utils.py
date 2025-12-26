"""
工具函数模块

提供通用的辅助函数
"""

import time
import re
from typing import Any, Dict, Optional,List


def replace_placeholders(template: str, data: Dict[str, Any]) -> str:
    """
    简化版占位符替换：直接从映射后的数据中获取值
    
    Args:
        template: 包含占位符的模板字符串
        data: 已映射的数据（如 {"Company": "公司名", "ID": "123"}）
    
    Returns:
        替换后的字符串
    """
    if not template or not isinstance(template, str):
        return template
    
    import re
    # 查找所有占位符 #key
    placeholder_pattern = r'#([a-zA-Z0-9._]+)'
    placeholders = re.findall(placeholder_pattern, template)
    
    result = template
    for placeholder in placeholders:
        # 直接从映射后的数据中获取值
        if placeholder in data:
            value = data[placeholder]
            if value is not None and value != "":
                result = result.replace(f"#{placeholder}", str(value))
    
    return result
        

def get_nested_value(data: Any, key_path: str) -> Any:
    """
    从嵌套的JSON数据中获取指定路径的值，提取失败会给默认值不会抛出异常
    
    Args:
        data: JSON格式的数据（字典或列表）
        key_path: 使用点号分隔的键路径，如 "data.items.0.name"
    
    Returns:
        键路径对应的值，如果路径无效则抛出异常。
        可能原因：
        1. 配置中的请求参数错误，导致获取到的响应体data异常
        2. key_path路径错误，导致无法正确提取数据
    
    Examples:
        >>> data = {"user": {"name": "张三", "contacts": [{"phone": "123"}]}}
        >>> get_nested_value(data, "user.name")
        '张三'
        >>> get_nested_value(data, "user.contacts.0.phone")
        '123'
    """
    if not key_path:
        return data
    
    current = data
    for key in key_path.split('.'):
        if isinstance(current, dict):
            current = current.get(key, None)
        elif isinstance(current, list):
            try:
                index = int(key)
                current = current[index] if index < len(current) else None
            except ValueError:
                # 键不是数字，无法访问列表属性
                return None
        
    return current
