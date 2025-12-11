"""
工具函数模块

提供通用的辅助函数
"""

import time
import re
from typing import Any, Dict, Optional,List


def replace_placeholders(template: str, data: Dict[str, Any], field_mapping: Optional[Dict[str, str]] = None) -> str:
    """
    动态替换字符串中的占位符 #key
    
    占位符格式: #key，其中 key 是第一次请求响应中的字段名
    支持嵌套字段路径，如 #data.company.id
    
    Args:
        template: 包含占位符的模板字符串
        data: 第一次请求获取的数据（字典格式）
        field_mapping: 字段映射配置（可选），用于扩展支持的占位符
    
    Returns:
        替换后的字符串
    
    Examples:
        >>> data = {"id": "123", "name": "公司A", "info": {"city": "北京"}}
        >>> replace_placeholders("company/#id/detail", data)
        'company/123/detail'
        >>> replace_placeholders("city=#info.city", data)
        'city=北京'
    """
    if not template or not isinstance(template, str):
        return template
    
    # 查找所有占位符 #key
    placeholder_pattern = r'#([a-zA-Z0-9._]+)'
    placeholders = re.findall(placeholder_pattern, template)
    
    result = template
    for placeholder in placeholders:

        value = None
        # 从数据中获取对应的值
        for output_key, input_key in field_mapping.items():
            if input_key == placeholder:
                value = get_nested_value(data, output_key)
                break
        
        # 替换占位符
        if value is not None and value != "":
            result = result.replace(f"#{placeholder}", str(value))
    
    return result


def get_nested_value(data: Any, key_path: str) -> Any:
    """
    从嵌套的JSON数据中获取指定路径的值。
    
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
    try:
        for key in key_path.split('.'):
            if isinstance(current, dict):
                current = current[key]
            elif isinstance(current, list):
                try:
                    index = int(key)
                    current = current[index] if index < len(current) else None
                except ValueError:
                    # 键不是数字，无法访问列表属性
                    return ""
            else:
                return ""
            
            if current is None:
                return ""
        return current
    except (KeyError, IndexError, ValueError, TypeError):
        raise

