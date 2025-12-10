"""
爬虫核心模块

主爬虫类，协调各模块完成数据抓取任务
"""

import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any

from .config_manager import ConfigManager, CrawlerConfig
from .data_parser import DataParser
from .excel_exporter import ExcelExporter
from .http_client import HttpClient
from .utils import get_nested_value

# 导入统一日志系统
from unified_logger import (
    console, log_error, log_info, log_warning, 
    log_page_progress, log_list_progress, log_contacts_saved
)


class BaseCrawler:
    """
    爬虫基类
    
    包含 CompanyCrawler 和 DoubleFetchCrawler 的共同逻辑：
    - 配置加载和初始化
    - 列表页爬取（crawl_page）
    - 数据去重和验证
    - 文件操作
    - 统计信息管理
    
    子类需要实现的方法：
    - crawl(): 具体的爬取流程
    
    Attributes:
        exhibition_code: 展会代码
        config: 爬虫配置
        max_workers: 最大线程数
        start_page: 起始页码
        exporter: Excel导出器
        http_client: HTTP客户端
        data_parser: 数据解析器
    """
    
    def __init__(self, exhibition_code: str, max_workers: int = 4, start_page: int = 1):
        """
        初始化爬虫基类
        
        Args:
            exhibition_code: 展会代码
            max_workers: 最大线程数，默认为4
            start_page: 起始页码，默认为1
        
        Raises:
            ValueError: 当展会配置不存在时抛出
        """
        self.exhibition_code = exhibition_code
        self.max_workers = max_workers
        self.start_page = start_page
        
        # 加载配置
        config_manager = ConfigManager()
        self.config = config_manager.get_config(exhibition_code)
        
        if self.config is None:
            raise ValueError(f"未找到展会 '{exhibition_code}' 的配置")
        
        # 初始化组件
        self.exporter = ExcelExporter()
        self.http_client = HttpClient()
        self.data_parser = DataParser()
        
        # 统计信息
        self._total_companies = 0
        self._total_pages = 0
        self._stats_lock = threading.Lock()
    
    def _extract_and_parse(
        self,
        response_data: Dict[str, Any],
        items_key: str,
        field_mapping: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        通用数据提取和解析方法
        
        从响应中提取数据列表，并可选地根据字段映射解析。
        
        Args:
            response_data: API响应数据
            items_key: 数据提取路径（如 "data.list"）
            field_mapping: 字段映射字典（如 {"Company": "name", "Phone": "phone"}）
        
        Returns:
            数据列表（原始或已解析）
        """
        # 1. 提取数据列表
        items = self.data_parser.extract_items(response_data, items_key)
        
        # 2. 如果有字段映射，进行解析
        if field_mapping:
            return self.data_parser.parse_items(items, field_mapping)
        
        # 3. 否则返回原始items
        return items

    def _make_request(
        self,
        url: str,
        params_str: str = "",
        data_str: str = "",
        headers: Optional[Dict] = None,
        method: str = "GET",
        context: str = "",
        placeholders: Optional[Dict[str, str]] = None
    ) -> dict | list:
        """
        通用请求方法(适用于列表页请求)：处理请求参数、发送请求、记录日志
        
        这是所有HTTP请求的统一入口，封装了重复的处理逻辑。
        
        Args:
            url: 请求URL（可包含占位符）
            params_str: URL参数字符串（可包含占位符）
            data_str: 请求体字符串（可包含占位符）
            headers: 请求头
            method: 请求方法（GET/POST）
            context: 上下文描述（用于日志）
            placeholders: 占位符字典，如 {"{page}": "1", "#company_id": "123"}
        
        Returns:
            响应数据（已解析为字典）
        """
        import json
        
        # 1. 处理占位符替换
        if placeholders:
            for placeholder, value in placeholders.items():
                url = url.replace(placeholder, str(value))
                params_str = params_str.replace(placeholder, str(value))
                data_str = data_str.replace(placeholder, str(value))
        
        # 2. 解析JSON参数
        request_params = None
        if params_str and params_str not in ("nan", "{}", "", "None"):
            try:
                request_params = json.loads(params_str)
            except:
                pass
        
        # 3. 准备请求数据
        request_data = self.http_client.prepare_request_data(data_str, headers or {})
        
        # 4. 发送请求（带重试）
        response_data = self.http_client.send_request_with_retry(
            url=url,
            method=method,
            headers=headers or {},
            params=request_params,
            data=request_data,
            context=context
        )
        
        return response_data
    
    def crawl_page(self, page: int) -> list[dict]:
        """
        爬取单页数据
        
        Args:
            page: 页码
        
        Returns:
           公司信息列表
        """
        if self.config is None:
            return []
        
        # 1. 构建请求参数
        params_str, data_str = self.http_client.build_request_params(self.config, page)
        skip_count = (page - 1) * 20
        
        # 2. 使用通用请求方法
        response_data = self._make_request(
            url=str(self.config.url),
            params_str=params_str,
            data_str=data_str,
            headers=self.config.headers,
            method=self.config.request_method,
            context=f"列表页{page}",
            placeholders={
                "#page": str(page),
                "#skipCount": str(skip_count)
            }
        )
        
        # 3. 使用通用提取和解析方法
        company_list = self._extract_and_parse(
            response_data=response_data,
            items_key=self.config.items_key,
            field_mapping=self.config.company_info_keys,
        )
        
        return company_list
    
    def _is_same_data(self, data1: list[dict], data2: list[dict]) -> bool:
        """
        检查两页数据是否相同（用于检测无翻页API）
        
        比较策略：
        1. 长度相同
        2. 第一条和最后一条记录的关键字段相同
        
        Args:
            data1: 第一页数据
            data2: 第二页数据
        
        Returns:
            True表示相同，False表示不同
        """
        if len(data1) != len(data2):
            return False
        
        if len(data1) == 0:
            return True
        
        # 比较第一条记录
        if not self._compare_records(data1[0], data2[0]):
            return False
        
        # 如果有多条记录，也比较最后一条
        if len(data1) > 1:
            if not self._compare_records(data1[-1], data2[-1]):
                return False
        
        return True
    
    def _compare_records(self, record1: dict, record2: dict) -> bool:
        """
        比较两条记录是否相同
        
        Args:
            record1: 第一条记录
            record2: 第二条记录
        
        Returns:
            True表示相同，False表示不同
        """
        return record1 == record2
    
    def _is_valid_contact(self, contact: Dict[str, Any]) -> bool:
        """
        检查联系人记录是否有效（除了公司名外至少有一个有效字段）
        
        Args:
            contact: 联系人记录
        
        Returns:
            True表示有效，False表示无效（只有公司名的空记录）
        """
        # 检查除company_name外的所有字段
        for key, value in contact.items():
            if key != 'company_name' and value and str(value).strip():
                return True
        return False
    
    def _remove_duplicate_companies(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去除公司列表中的重复记录
        
        Args:
            companies: 公司列表
        
        Returns:
            去重后的公司列表
        """
        if not companies:
            return companies
        
        seen = set()
        unique_companies = []
        
        for company in companies:
            # 创建唯一标识（基于所有字段的排序后的键值对）
            key = tuple(sorted((k, str(v)) for k, v in company.items()))
            if key not in seen:
                seen.add(key)
                unique_companies.append(company)
        
        return unique_companies
    
    def _remove_duplicates_and_invalid(self, contacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去除重复记录和无效记录
        
        Args:
            contacts: 联系人列表
        
        Returns:
            去重并过滤后的联系人列表
        """
        if not contacts:
            return contacts
        
        # 去重：基于所有字段内容创建唯一键
        seen = set()
        unique_contacts = []
        
        for contact in contacts:
            # 创建唯一标识（基于所有字段的排序后的键值对）
            key = tuple(sorted((k, str(v).strip()) for k, v in contact.items()))
            if key not in seen:
                seen.add(key)
                unique_contacts.append(contact)
        
        # 过滤无效记录（只有公司名没有有效联系方式的记录）
        valid_contacts = [
            contact for contact in unique_contacts 
            if self._is_valid_contact(contact)
        ]
        
        # 如果过滤后还有有效数据，返回过滤后的；否则返回去重后的数据（保留空记录作为备用）
        return valid_contacts if valid_contacts else unique_contacts
    
    def _delete_old_file_if_needed(self):
        """
        如果从第一页开始爬取，删除旧的数据文件
        """
        if self.start_page == 1:
            old_file_path = self.exporter.get_file_path(self.exhibition_code)
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                    log_info(f"已删除旧文件: {old_file_path}")
                except Exception as e:
                    log_error(f"删除旧文件失败", e)
    
    def _reset_stats(self):
        """
        重置统计信息
        """
        self._total_companies = 0
        self._total_pages = 0
    
    # 注意：_make_request 和 _extract_and_parse 方法已从 RequestMixin 继承
    
    def crawl(self) -> bool:
        """
        执行爬取流程（抽象方法，由子类实现）
        
        Returns:
            是否成功获取到数据
        """
        raise NotImplementedError("子类必须实现 crawl() 方法")


class CompanyCrawler(BaseCrawler):
    """
    单次请求爬虫
    
    适用于API一次性返回完整数据的场景。
    
    核心改进：
    - 动态翻页机制，不预先检测总页数
    - 并行模式：批量爬取+动态扩展，自动探测数据边界
    """
    
    def crawl_parallel(self) -> bool:
        """
        并行爬取模式
        
        使用动态扩展策略：
        1. 批量爬取一定数量的页面
        2. 根据结果判断是否需要继续
        3. 如果最后几页都有数据，继续下一批
        4. 如果遇到连续空页，提前停止
        
        Returns:
            是否成功获取到数据
        """
        if self.config is None:
            return False
        
        headers = list(self.config.company_info_keys.keys())
        has_data = False
        
        # 批量爬取参数
        batch_size = 10  # 每批爬取10页
        current_batch_start = self.start_page
        max_consecutive_empty = 3  # 连续空页阈值
        
        while True:
            batch_end = current_batch_start + batch_size - 1
            
            # 使用线程池爬取当前批次
            batch_results = {}
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交当前批次的所有页面任务
                future_to_page = {
                    executor.submit(self.crawl_page, page): page 
                    for page in range(current_batch_start, batch_end + 1)
                }
                
                # 处理完成的任务
                for future in as_completed(future_to_page):
                    page = future_to_page[future]
                    
                    try:
                        company_list = future.result()
                        batch_results[page] = company_list
                        
                        if company_list:
                            self.exporter.save(company_list, self.exhibition_code, headers)
                            has_data = True
                            
                            with self._stats_lock:
                                self._total_companies += len(company_list)
                                self._total_pages += 1
                            
                            # 记录进度（控制台显示）
                            log_page_progress(page, len(company_list))
                        
                    except Exception as e:
                        log_error(f"处理第{page}页时发生错误", e)
                        batch_results[page] = []
            
            # 分析批次结果，决定是否继续
            # 检查最后几页是否都为空
            sorted_pages = sorted(batch_results.keys())
            consecutive_empty_count = 0
            
            for page in reversed(sorted_pages):
                if not batch_results[page]:
                    consecutive_empty_count += 1
                else:
                    break
            
            # 如果连续空页数达到阈值，停止爬取
            if consecutive_empty_count >= max_consecutive_empty:
                log_info(f"检测到连续{consecutive_empty_count}页无数据，停止爬取")
                break
            
            # 如果整批都是空的，也停止
            if all(not batch_results[p] for p in sorted_pages):
                log_info("整批数据都为空，停止爬取")
                break
            
            # 检测批次中是否有重复数据（无翻页API检测）
            if len(sorted_pages) >= 2:
                # 比较批次中第一页和第二页的数据
                first_page = sorted_pages[0]
                second_page = sorted_pages[1]
                if (batch_results[first_page] and batch_results[second_page] and 
                    self._is_same_data(batch_results[first_page], batch_results[second_page])):
                    log_info(f"检测到第{first_page}页和第{second_page}页数据相同，疑似无翻页API，停止爬取")
                    break
            
            # 继续下一批
            current_batch_start = batch_end + 1
        
        return has_data
    
    def crawl(self) -> bool:
        """
        执行完整爬取流程（单次请求模式）
        
        Returns:
            是否成功获取到数据
        """
        try:
           
            # 删除旧文件（如果从第一页开始）
            self._delete_old_file_if_needed()
            
            # 重置统计信息
            self._reset_stats()
            
            # 执行爬取
            has_data = self.crawl_parallel()
            
            return has_data
            
        except Exception as e:
            log_error("爬取过程中发生错误", e)
            return False


class DoubleFetchCrawler(BaseCrawler):
    """
    二次请求爬虫（逐页处理版）
    
    适用于需要先获取列表，再获取详情的场景。
    
    工作流程：
    1. 获取一页公司列表
    2. 立即抓取这页所有公司的联系人
    3. 保存这一页的联系人数据到Excel
    4. 继续下一页
    
    """
    
    def __init__(self, exhibition_code: str, max_workers: int = 4, start_page: int = 1):
        """
        初始化二次请求爬虫
        
        Args:
            exhibition_code: 展会代码
            max_workers: 最大线程数
            start_page: 起始页码
        """
        super().__init__(exhibition_code, max_workers, start_page)
        
        # 使用DetailFetcher来获取联系人
        # 注意：此时 self.config 已经在父类初始化时验证过，不会为 None
        from .detail_fetcher import DetailFetcher
        self.detail_fetcher = DetailFetcher(self.config, max_workers=self.max_workers)
        
        # 二次请求模式的额外统计
        self._total_contacts = 0
    
    def crawl(self) -> bool:
        """
        执行爬取流程（二次请求模式 - 逐页处理）
        
        每获取一页公司列表，就立即抓取联系人并保存，避免数据丢失。
        
        Returns:
            是否成功获取到数据
        """
        if self.config is None:
            log_info("配置未加载")
            return False
        
        page = self.start_page
        has_data = False
        consecutive_empty = 0
        previous_companies = None  # 用于检测重复数据
        
        
        # 确定表头 - 基本配置的字段映射 + 联系人字段映射
        if self.config.info_key:
            headers = list(self.config.company_info_keys.keys()) + list(self.config.info_key.keys())
        else:
            headers = list(self.config.company_info_keys.keys())
       
        try:
            # 删除旧文件（如果从第一页开始）
            self._delete_old_file_if_needed()
            
            while True:
                # 步骤1: 获取这一页的公司列表（原始items）
                items = self.crawl_page(page)
                log_list_progress(page, len(items))
                
                if not items:
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        log_info("连续3页无数据，停止爬取")
                        break
                    page += 1
                    continue
               
                # 检查是否与前一页数据完全相同（避免无翻页API的死循环）
                if previous_companies is not None and self._is_same_data(previous_companies, items):
                    log_info(f"第{page}页数据与第{page-1}页相同，疑似无翻页API，停止爬取")
                    break
                
                consecutive_empty = 0
                # 在提交任务前先去重公司列表（API自身可能返回重复数据）
                unique_companies_basic = self._remove_duplicate_companies(items)

                # 步骤3: 立即抓取这一页公司的联系人
                # 注意：需要传入原始items，因为DetailFetcher需要用原始字段做占位符替换
                # 同时传入解析后的基本信息，用于合并
                all_contacts = self.detail_fetcher.fetch_batch_contacts_with_basic_info(
                    companies_basic_info=unique_companies_basic
                )
                
                # 步骤4: 立即保存这一页的联系人数据
                if all_contacts:
                    # 去重和过滤无效记录
                    unique_contacts = self._remove_duplicates_and_invalid(all_contacts)
                    
                    self.exporter.save(unique_contacts, self.exhibition_code, headers)
                    self._total_contacts += len(unique_contacts)
                    has_data = True
                    
                    # 记录联系人保存进度（控制台显示）
                    log_contacts_saved(page, len(unique_contacts))
                
                # 更新统计
                self._total_companies += len(items)
                previous_companies = items  # 保存当前页数据用于下次比较
                
                # 继续下一页
                page += 1
                
        except KeyboardInterrupt:
            log_error("用户中断，已保存的数据不会丢失")
        except Exception as e:
            log_error("爬取过程出错", e)
        
        return has_data
