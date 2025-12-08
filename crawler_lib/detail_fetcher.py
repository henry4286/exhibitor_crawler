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
from .utils import get_nested_value


class DetailFetcher:
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
        self.config = config
        self.max_workers = max_workers
        self.http_client = HttpClient()
        self.data_parser = DataParser()
        
        # 统计信息
        self._stats_lock = threading.Lock()
        self._success_count = 0
        self._fail_count = 0
    
    def fetch_company_detail(self, company: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        获取单个公司的详细信息
        
        Args:
            company: 公司基本信息
        
        Returns:
            公司详细信息，如果失败则返回None
        """
        try:
            # 获取公司ID
            company_id = get_nested_value(company, self.config.id_key or "id")
            if not company_id:
                print(f"⚠️  公司缺少ID字段，跳过", flush=True)
                return None
            
            # 构建详情请求参数
            params_str = str(self.config.params_detail or "{}")
            data_str = str(self.config.data_detail or "{}")
            url = str(self.config.url_detail or "")
            
            # 替换公司ID占位符
            params_str = params_str.replace("#company_id", str(company_id))
            data_str = data_str.replace("#company_id", str(company_id))
            url = url.replace("#company_id", str(company_id))
            
            # 解析参数
            import json
            params = json.loads(params_str) if params_str not in ("nan", "{}", "") else None
            data = json.loads(data_str) if data_str not in ("nan", "{}", "") else None
            
            # 发送请求
            response_data = self.http_client.send_request(
                self.config,
                page=1  # 详情请求不需要分页
            )
            
            # 提取详情数据
            if self.config.items_key_detail:
                detail_data = get_nested_value(response_data, self.config.items_key_detail)
            else:
                detail_data = response_data
            
            # 合并公司基本信息和详情
            result = company.copy()
            if isinstance(detail_data, dict):
                result.update(detail_data)
            elif isinstance(detail_data, list) and len(detail_data) > 0:
                result.update(detail_data[0])
            
            with self._stats_lock:
                self._success_count += 1
            
            return result
            
        except Exception as e:
            company_name = get_nested_value(company, self.config.company_name_key or "name")
            print(f"❌ 获取公司 {company_name} 详情失败: {e}", flush=True)
            
            with self._stats_lock:
                self._fail_count += 1
            
            # 即使失败也返回基本信息
            return company
    
    def fetch_company_contacts(self, company: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        获取公司的联系人信息（使用统一的无限重试机制）
        
        策略：
        - 正常请求：无延迟
        - 限流/失败：指数退避重试，直到成功
        
        Args:
            company: 公司基本信息
        
        Returns:
            联系人信息列表（必定成功返回）
        """
        # 获取公司ID和名称
        company_id = get_nested_value(company, self.config.id_key or "id")
        company_name = get_nested_value(company, self.config.company_name_key or "name")
        
        if not company_id:
            # 没有ID，返回空记录
            return self._create_empty_contact(company_name)
        
        # 构建详情请求URL和参数
        url = str(self.config.url_detail or "")
        params_str = str(self.config.params_detail or "")
        data_str = str(self.config.data_detail or "")
        
        # 替换占位符
        url = url.replace("#company_id", str(company_id))
        if params_str:
            params_str = params_str.replace("#company_id", str(company_id))
        if data_str:
            data_str = data_str.replace("#company_id", str(company_id))
        
        # 处理params
        params = None
        if params_str and params_str not in ("nan", "{}", ""):
            try:
                params = json.loads(params_str)
            except:
                pass
        
        # 处理data
        data = None
        if data_str and data_str not in ("nan", "{}", ""):
            try:
                data = json.loads(data_str)
            except:
                pass
        
        # 获取请求头和方法
        headers = self.config.headers_detail or {}
        request_method = (self.config.request_method_detail or 'GET').upper()
        
        # 使用统一的带重试请求方法
        response_data = self.http_client.send_request_with_retry(
            url=url,
            method=request_method,
            headers=headers,
            params=params,
            data=data,
            context=f"联系人[{company_name}]"
        )
        
        # 提取联系人数据
        contacts = self._parse_contact_data(response_data, company_name)
        
        with self._stats_lock:
            self._success_count += 1
        
        return contacts
    
    def _create_empty_contact(self, company_name: str) -> List[Dict[str, Any]]:
        """创建空的联系人记录"""
        contact_info = {"company_name": company_name or "未知公司"}
        if self.config.info_key:
            for output_key in self.config.info_key.keys():
                contact_info[output_key] = ""
        return [contact_info]
    
    def _parse_contact_data(self, response_data: Any, company_name: str) -> List[Dict[str, Any]]:
        """
        解析联系人数据
        
        Args:
            response_data: API响应数据
            company_name: 公司名称
        
        Returns:
            联系人信息列表
        """
        # 提取联系人数据
        if self.config.items_key_detail:
            contact_data = get_nested_value(response_data, self.config.items_key_detail)
        else:
            contact_data = response_data
        
        # 如果是字符串，尝试解析为JSON
        if isinstance(contact_data, str) and contact_data:
            try:
                contact_data = json.loads(contact_data)
            except json.JSONDecodeError:
                pass
        
        contacts = []
        
        if isinstance(contact_data, dict):
            # 单个联系人
            contact_info = {"company_name": company_name or "未知公司"}
            if self.config.info_key:
                for output_key, input_key in self.config.info_key.items():
                    contact_info[output_key] = get_nested_value(contact_data, input_key)
            contacts.append(contact_info)
            
        elif isinstance(contact_data, list):
            # 多个联系人
            for contact in contact_data:
                contact_info = {"company_name": company_name or "未知公司"}
                if self.config.info_key:
                    for output_key, input_key in self.config.info_key.items():
                        contact_info[output_key] = get_nested_value(contact, input_key)
                contacts.append(contact_info)
        
        # 如果没有联系人数据，创建空记录
        if not contacts:
            contacts = self._create_empty_contact(company_name)
        
        return contacts
    
    def fetch_batch_details(self, companies: List[Dict[str, Any]], 
                           fetch_contacts: bool = False) -> List[Any]:
        """
        批量获取公司详情
        
        Args:
            companies: 公司列表
            fetch_contacts: 是否获取联系人信息（True）还是详情信息（False）
        
        Returns:
            详情信息列表或联系人列表
        """
        results = []
        
        if not companies:
            return results
        
        print(f"📥 开始批量获取 {len(companies)} 个公司的{'联系人' if fetch_contacts else '详情'}", flush=True)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交任务
            if fetch_contacts:
                future_to_company = {
                    executor.submit(self.fetch_company_contacts, company): company 
                    for company in companies
                }
            else:
                future_to_company = {
                    executor.submit(self.fetch_company_detail, company): company 
                    for company in companies
                }
            
            # 收集结果
            for future in as_completed(future_to_company):
                try:
                    result = future.result()
                    if result:
                        if fetch_contacts:
                            results.extend(result)  # 联系人是列表
                        else:
                            results.append(result)  # 详情是单个对象
                except Exception as e:
                    company = future_to_company[future]
                    company_name = get_nested_value(company, self.config.company_name_key or "name")
                    print(f"❌ 处理公司 {company_name} 时发生异常: {e}", flush=True)
        
        print(f"✅ 批量获取完成，成功: {self._success_count}, 失败: {self._fail_count}", flush=True)
        
        return results
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        with self._stats_lock:
            return {
                'success': self._success_count,
                'fail': self._fail_count,
                'total': self._success_count + self._fail_count
            }
    
    def reset_stats(self):
        """重置统计信息"""
        with self._stats_lock:
            self._success_count = 0
            self._fail_count = 0
    
    def _is_business_success(self, response_data: Dict[str, Any]) -> bool:
        """
        检查业务层面是否成功
        
        常见的失败响应格式：
        1. {"code": 1000, "message": "请求过于频繁", "success": false}
        2. {"success": false, "msg": "限流"}
        3. {"status": 0, "message": "失败"}
        4. {"error": "...", "data": null}
        
        Args:
            response_data: API响应数据
        
        Returns:
            True表示业务成功，False表示业务失败（需要重试）
        """
        if not isinstance(response_data, dict):
            return True  # 非字典数据，可能是列表，认为成功
        
        # 检查常见的失败标识
        # 1. success字段
        if 'success' in response_data:
            if response_data['success'] is False or response_data['success'] == 'false':
                return False
        
        # 2. code字段（通常0或200表示成功，其他表示失败）
        if 'code' in response_data:
            code = response_data['code']
            # 常见成功code: 0, 200, "0", "200"
            if code not in [0, 200, '0', '200']:
                return False
        
        # 3. status字段
        if 'status' in response_data:
            status = response_data['status']
            # 常见失败status: 0, false, "error"
            if status in [0, False, 'false', 'error', '0']:
                return False
        
        # 4. error字段存在且非空
        if 'error' in response_data:
            error = response_data['error']
            if error and error not in ['', None, 'null']:
                return False
        
        # 5. 检查是否包含明显的错误消息关键词
        error_keywords = ['请求过于频繁', '限流', '访问受限', '请稍后', '失败', 'rate limit', 
                         'too many', 'forbidden', 'error', '错误']
        
        # 检查message/msg字段
        for msg_key in ['message', 'msg', 'error_msg', 'errmsg']:
            if msg_key in response_data:
                msg = str(response_data[msg_key]).lower()
                for keyword in error_keywords:
                    if keyword.lower() in msg:
                        return False
        
        # 都没有检测到失败标识，认为成功
        return True
    
    def _extract_error_message(self, response_data: Dict[str, Any]) -> str:
        """
        从响应中提取错误消息
        
        Args:
            response_data: API响应数据
        
        Returns:
            错误消息字符串
        """
        if not isinstance(response_data, dict):
            return "未知错误"
        
        # 尝试从各种可能的字段中提取错误消息
        for key in ['message', 'msg', 'error', 'error_msg', 'errmsg', 'error_message']:
            if key in response_data:
                msg = response_data[key]
                if msg:
                    return str(msg)
        
        # 如果有code，也包含进来
        if 'code' in response_data:
            return f"错误代码: {response_data['code']}"
        
        # 返回整个响应的简化版本
        return str(response_data)[:100]
