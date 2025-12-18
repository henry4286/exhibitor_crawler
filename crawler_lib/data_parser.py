"""
数据解析模块

负责从API响应中提取和解析公司信息
"""

from typing import Any, Dict, List

from .utils import get_nested_value


class DataParser:
    """
    数据解析器
    
    负责从API响应中提取公司信息及联系人信息。
    """
    
    @staticmethod
    def extract_items(response_data: Dict[str, Any], items_key: str) -> List[Dict[str, Any]]:
        """
        从API响应数据中提取指定路径的列表数据。
        
        支持两种响应格式：
        1. 字典响应（常见）：{"data": [...], "total": 100}，需要通过items_key提取列表
        2. 数组响应（特殊）：[{...}, {...}]，直接作为列表处理
        
        如果提取到的数据是字典，会强制转化成单字典列表
        Args:
            response_data: API响应数据（可以是字典或列表）
            items_key: 数据提取路径（如 "data.list"）
        
        Returns:
            提取的列表数据，提取失败会抛出异常
        """
        # 支持直接返回数组格式的响应
        if isinstance(response_data, list):
            return response_data
        
        if not response_data or not isinstance(response_data, dict):
            return []
        
        items = response_data
        # 根据items_key提取嵌套数据
        if items_key and str(items_key) not in ("nan", "", "None"):
            items = get_nested_value(response_data, items_key)
                    
        if isinstance(items, dict):
            items = [items]  
        
        return items if isinstance(items, list) else []
    
    @staticmethod
    def parse_items(items: list, field_mappings: dict) -> list[dict]:
        """
        从响应体的信息主体数据列表中，根据字段映射提取需要的字段信息
        
        Args:
            items: 响应体的信息主体数据列表
            field_mappings: 字段映射配置 {输出字段名: 源数据路径}
        
        Returns:
            解析后的数据信息列表，提取失败会抛出异常
        """
        results = []
        
        for item in items:
            company_info = {}
            
            for output_field, source_path in field_mappings.items():
                try:
                    company_info[output_field] = get_nested_value(item, source_path)
                except Exception:
                    raise ValueError(f"字段提取失败: {output_field} from path {source_path}\n{item}")
            results.append(company_info)
        
        return results