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
    
    @staticmethod
    def has_more_data(response_data: Any, items: list, current_page: int) -> bool:
        """
        判断是否还有更多数据
        
        Args:
            response_data: API响应数据
            items: 当前页提取的数据列表
            current_page: 当前页码
        
        Returns:
            是否还有更多数据
        """
        # 如果当前页没有数据，则没有更多数据
        if not items or len(items) == 0:
            return False
        
        # 尝试从响应中获取总数信息
        # 支持多种常见的分页信息字段
        total_fields = ['total', 'totalCount', 'totalRecords', 'count']
        page_info_fields = ['pageInfo', 'pagination', 'paging', 'meta']
        
        # 检查顶层字段
        if isinstance(response_data, dict):
            for field in total_fields:
                total = response_data.get(field)
                if total is not None and isinstance(total, (int, float)):
                    # 假设每页20条
                    return current_page * 20 < total
            
            # 检查分页信息对象
            for field in page_info_fields:
                page_info = response_data.get(field)
                if isinstance(page_info, dict):
                    for total_field in total_fields:
                        total = page_info.get(total_field)
                        if total is not None and isinstance(total, (int, float)):
                            return current_page * 20 < total
                    
                    # 检查hasMore字段
                    has_more = page_info.get('hasMore', page_info.get('hasNextPage'))
                    if has_more is not None:
                        return bool(has_more)
        
        # 如果无法确定，且当前页有数据，则假设还有更多数据
        # 需要继续请求下一页来确认
        return True
