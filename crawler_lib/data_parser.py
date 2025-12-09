"""
数据解析模块

负责从API响应中提取和解析公司信息
"""

from typing import Any

from .utils import get_nested_value


class DataParser:
    """
    数据解析器
    
    负责从API响应中提取公司信息。
    """
    
    @staticmethod
    def extract_items(response_data: Any, items_key: str) -> list:
        """
        从响应数据中提取公司列表
        
        Args:
            response_data: API响应数据
            items_key: 用于定位公司列表的键路径
        
        Returns:
            公司信息列表
        """
        # 处理特殊格式的响应（如数组格式）
        if isinstance(response_data, list) and len(response_data) > 1:
            items = response_data[1].get("Table", [])
        else:
            items = response_data
        
        # 根据items_key提取嵌套数据
        if items_key and str(items_key) not in ("nan", "", "None"):
            for key in items_key.split('.'):
                if isinstance(items, dict):
                    items = items.get(key, [])
                elif isinstance(items, list) and key.isdigit():
                    index = int(key)
                    items = items[index] if index < len(items) else []
                else:
                    break
        
        return items if isinstance(items, list) else []
    
    @staticmethod
    def parse_company_info(items: list, field_mappings: dict) -> list[dict]:
        """
        解析公司信息列表
        
        Args:
            items: 原始公司数据列表
            field_mappings: 字段映射配置 {输出字段名: 源数据路径}
        
        Returns:
            解析后的公司信息列表
        """
        company_list = []
        
        for item in items:
            company_info = {}
            for output_field, source_path in field_mappings.items():
                company_info[output_field] = get_nested_value(item, source_path)
            company_list.append(company_info)
        
        return company_list