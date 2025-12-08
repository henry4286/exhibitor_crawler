"""
工具函数模块

提供通用的辅助函数
"""

import time
from typing import Any


def get_nested_value(data: Any, key_path: str) -> Any:
    """
    从嵌套的JSON数据中获取指定路径的值。
    
    Args:
        data: JSON格式的数据（字典或列表）
        key_path: 使用点号分隔的键路径，如 "data.items.0.name"
    
    Returns:
        键路径对应的值，如果路径无效则返回空字符串
    
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
                current = current.get(key)
            elif isinstance(current, list):
                index = int(key)
                current = current[index] if index < len(current) else None
            else:
                return ""
            
            if current is None:
                return ""
        return current
    except (KeyError, IndexError, ValueError, TypeError):
        return ""


def write_status_file(filename: str, content: str, max_retries: int = 3) -> bool:
    """
    将内容写入状态文件，支持重试机制。
    
    Args:
        filename: 目标文件名
        content: 要写入的内容
        max_retries: 最大重试次数
    
    Returns:
        写入是否成功
    """
    retry_delay = 0.3
    
    for attempt in range(max_retries):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except PermissionError:
            print(f"文件 {filename} 正在被占用，{retry_delay}秒后重试...", flush=True)
            time.sleep(retry_delay)
        except OSError as e:
            print(f"写入文件 {filename} 失败: {e}", flush=True)
            return False
    
    print(f"写入文件 {filename} 失败，已超过最大重试次数", flush=True)
    return False
