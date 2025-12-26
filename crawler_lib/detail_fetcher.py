"""
详情获取模块

处理二次请求模式：先获取公司列表，再获取每个公司的详细信息
使用统一的无限重试机制，保证数据抓取成功
"""

import json
from typing import Any, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


from .config_manager import CrawlerConfig
from .http_client import HttpClient
from .data_parser import DataParser
from .utils import replace_placeholders

from .base_crawler import BaseCrawler

class DetailFetcher(BaseCrawler):
    """
    详情获取器
    
    负责在二次请求模式下获取公司详细信息。
    支持多线程并发获取以提高效率。
    使用统一的无限重试机制，保证请求成功。
    """
    
    def __init__(self, config: CrawlerConfig, max_workers: int = 4):
        """
        初始化详情获取器
        
        Args:
            config: 爬虫配置
            max_workers: 最大并发线程数
        """
        # 统计信息
        self._success_count = 0

        super().__init__(config.exhibition_code, max_workers)
        

    def fetch_company_contacts(self, company: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        获取公司的联系人信息（使用统一的无限重试机制）
        
        策略：
        - 正常请求：无延迟
        - 限流/失败：指数退避重试，直到成功
        - **新增**：空数据检测与重试
        - **升级**：支持动态占位符替换 #key
        - **修复**：使用原始数据进行参数替换，避免映射后的数据路径问题
        
        Args:
            company: 公司基本信息（已映射的数据）
        
        Returns:
            联系人信息列表（必定成功返回）
        """

        
        # 类型检查
        if self.config is None:
            raise ValueError("配置不能为空")
        
        # 构建详情请求URL和参数
        url = str(self.config.url_detail or "")
        
        # **修复**：直接使用映射后的数据进行参数替换
        # 因为传入的company是已经映射后的数据，可以直接从中获取字段值
        
        # 处理params（支持字典和字符串类型）
        params = None
        if self.config.params_detail:
            if isinstance(self.config.params_detail, dict):
                # 检查整个字典是否包含占位符
                dict_has_placeholder = any(
                    isinstance(value, str) and '#' in value 
                    for value in self.config.params_detail.values()
                )
                
                if dict_has_placeholder:
                    # 只有包含占位符时才遍历和替换
                    params = {}
                    for key, value in self.config.params_detail.items():
                        if isinstance(value, str) and '#' in value:
                            params[key] = replace_placeholders(value, company)
                        else:
                            params[key] = value
                else:
                    # 不包含占位符，直接复制
                    params = self.config.params_detail.copy()
            else:
                # 如果是字符串，先检查是否包含占位符，再决定是否替换
                try:
                    params_str = str(self.config.params_detail)
                    if '#' in params_str:
                        params_str = replace_placeholders(params_str, company)
                    if params_str and params_str not in ("nan", "{}", ""):
                        params = json.loads(params_str)
                except:
                    pass
        
        # 处理data（支持字典和字符串类型）
        data = None
        if self.config.data_detail:
            if isinstance(self.config.data_detail, dict):
                # 检查整个字典是否包含占位符
                dict_has_placeholder = any(
                    isinstance(value, str) and '#' in value 
                    for value in self.config.data_detail.values()
                )
                
                if dict_has_placeholder:
                    # 只有包含占位符时才遍历和替换
                    data = {}
                    for key, value in self.config.data_detail.items():
                        if isinstance(value, str) and '#' in value:
                            data[key] = replace_placeholders(value, company)
                        else:
                            data[key] = value
                else:
                    # 不包含占位符，直接复制
                    data = self.config.data_detail.copy()
            else:
                # 如果是字符串，先检查是否包含占位符，再决定是否替换
                try:
                    data_str = str(self.config.data_detail)
                    if '#' in data_str:
                        data_str = replace_placeholders(data_str, company)
                    if data_str and data_str not in ("nan", "{}", ""):
                        data = json.loads(data_str)
                except:
                    pass
       
        # 使用动态占位符替换URL（先检查是否包含占位符）
        if '#' in url:
            url = replace_placeholders(url, company)
      
        # 获取请求头和方法
        headers = self.config.headers_detail or {}
        request_method = (self.config.request_method_detail or 'GET').upper()

        # 使用统一的带重试请求方法（带空数据检测）
        response_data = self.http_client.send_request_with_retry(
            url=url,
            method=request_method,
            headers=headers,
            params=params,
            data=data,
            context="联系人获取",
        )
        
        #print("详情响应数据:", response_data)
        # 提取联系人数据（传递请求信息用于日志）
        items_key_detail = self.config.items_key_detail or ""
        info_key = self.config.info_key or {}
        
        # 构建请求信息用于日志记录
        request_info = {
            'url': url,
            'method': request_method,
            'params': params,
            'data': data
        }
        
        contacts = self._extract_and_parse(
            response_data, 
            items_key_detail, 
            info_key,
            request_info
        )
        
        with self._stats_lock:
            self._success_count += 1
        
        return contacts
    
    def _create_empty_contact(self) -> List[Dict[str, Any]]:
        """创建空的联系人记录"""
        contact_info = {}
        if self.config and self.config.info_key:
            for output_key in self.config.info_key.keys():
                contact_info[output_key] = ""
        return [contact_info]
    
    def fetch_batch_contacts_with_basic_info(self, 
                                            companies_basic_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量获取联系人并合并基本信息（二次请求模式专用）
        
        Args:
            companies_basic_info: 解析后的公司基本信息列表（用于合并）
        
        Returns:
            联系人列表（每个联系人包含公司基本信息和联系人详情）
        """
        results = []
        
        results_lock = threading.Lock()
        
        # 如果配置为单线程（max_workers == 1），则改为顺序执行，避免线程池开销
        if getattr(self, 'max_workers', 1) == 1:
            for index, item in enumerate(companies_basic_info):
                try:
                    contacts_list = self.fetch_company_contacts(item)
                    basic_info = companies_basic_info[index]

                    # 将基本信息合并到每个联系人记录中
                    for contact in contacts_list:
                        full_record = basic_info.copy()
                        full_record.update(contact)
                        results.append(full_record)

                    company_name = basic_info.get('Company', '未知公司')
                    print(f"✅ 成功获取公司 {company_name} 的 {len(contacts_list)} 个联系人", flush=True)
                except Exception as e:
                    basic_info = companies_basic_info[index]
                    company_name = basic_info.get('Company', '未知公司')
                    print(f"❌ 处理公司 {company_name} 时发生异常: {e}", flush=True)

            print(f"✅ 第{self.start_page}页 - 顺序批量获取完成，成功: {self._success_count}", flush=True)
            return results

        # 否则使用线程池并发执行（默认行为）
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self.fetch_company_contacts, item): i 
                for i, item in enumerate(companies_basic_info)
            }
            
            # 收集结果并合并基本信息
            for future in as_completed(future_to_index):
                try:
                    contacts_list = future.result()  # 联系人列表
                    index = future_to_index[future]
                    basic_info = companies_basic_info[index]  # 对应的基本信息
                    
                    with results_lock:

                        # 将基本信息合并到每个联系人记录中
                        for contact in contacts_list:
                            full_record = basic_info.copy()  # 先复制基本信息
                            full_record.update(contact)  # 再添加联系人信息
                            results.append(full_record)
                            
                        company_name = basic_info.get('Company', '未知公司')
                        #print(f"✅ 成功获取公司 {company_name} 的 {len(contacts_list)} 个联系人", flush=True)
                except Exception as e:
                    index = future_to_index[future]
                    basic_info = companies_basic_info[index]
                    company_name = basic_info.get('Company', '未知公司')
                    print(f"❌ 处理公司 {company_name} 时发生异常: {e}", flush=True)

        print(f"✅ 第{self.start_page}页 - 批量获取完成，成功: {self._success_count}", flush=True)

        return results
