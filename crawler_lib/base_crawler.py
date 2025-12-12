"""
爬虫基类模块

包含爬虫的基础功能和共同逻辑
"""

import threading
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any

from .config_manager import ConfigManager, CrawlerConfig
from .data_parser import DataParser
from .excel_exporter import ExcelExporter
from .http_client import HttpClient
from .utils import get_nested_value
from .exceptions import ParseError
 
# 导入统一日志系统
from unified_logger import (
    console, log_error, log_info, log_request, 
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
        # 用于跨页比较的上一页解析结果（用于判断是否停止翻页）
        self._prev_page_items: Optional[List[Dict[str, Any]]] = None

    def _extract_and_parse(
        self,
        response_data: Any,
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
            数据列表，数据提取失败会抛出异常
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

    ) -> dict | list:
        """
        通用请求方法(适用于列表页请求)：处理请求参数、发送请求、记录日志
        
        Args:
            url: 请求URL（可包含占位符）
            params_str: URL参数字符串（可包含占位符）
            data_str: 请求体字符串（可包含占位符）
            headers: 请求头
            method: 请求方法（GET/POST）
            context: 上下文描述（用于日志）
        
        Returns:
            响应数据
        """
       
        # 1. 解析JSON参数
        request_params = None
        if params_str and params_str not in ("nan", "{}", "", "None"):
            try:
                request_params = json.loads(params_str)
            except:
                pass
        
        # 2. 准备请求数据
        request_data = self.http_client.prepare_request_data(data_str, headers or {})
        
        # 3. 发送请求
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

        # 2. 使用通用请求方法
        response_data = self._make_request(
            url=str(self.config.url),
            params_str=params_str,
            data_str=data_str,
            headers=self.config.headers,
            method=self.config.request_method,
            context=f"列表页{page}"
        )
        
        # 3. 使用通用提取和解析方法
        try:
            company_list = self._extract_and_parse(
                response_data=response_data,
                items_key=self.config.items_key,
                field_mapping=self.config.company_info_keys,
            )
            
            return company_list
        except Exception as e:
            
            log_request(url=str(self.config.url),
            params=params_str,
            data=data_str,
            response=response_data)
            
            # 将解析失败作为 ParseError 抛出，供分页引擎判断并停止
            raise ParseError(f"解析第{page}页数据失败: {e}") from e
    
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
        # 清除上一页解析缓存
        self._prev_page_items = None
    
    def _print_summary(self):
        """
        打印爬取汇总信息
        """
        console("\n" + "="*60)
        console("📊 爬取汇总")
        console("="*60)
        console(f"展会代码: {self.exhibition_code}")
        console(f"总页数: {self._total_pages}")
        console(f"总数据条数: {self._total_companies}")
        console("="*60 + "\n")

    def _should_stop_pagination(
        self,
        sorted_pages: list,
        batch_results: Dict[int, Any],
        parse_error_pages: Optional[set] = None
    ) -> bool:
        """
        统一的分页停止判定。

        停止条件（任意满足即停止）：
        1. 当前批次中存在解析错误页（由 `ParseError` 导致，记录在 parse_error_pages 中）
        2. 某页解析结果与上一页解析结果相同（跨页比较），表示无更多数据

        说明：方法会更新 `self._prev_page_items` 为本批次的最后一条有效解析结果（若存在）。
        """
        # 1) 解析错误优先触发停止
        if parse_error_pages:
            return True

        prev = self._prev_page_items
        last_valid = prev

        for p in sorted_pages:
            val = batch_results.get(p)
            # 仅对成功解析出的列表进行比较和更新
            if isinstance(val, list):
                # 如果上一次存在解析结果，且与当前页相同，则停止
                if last_valid is not None and val == last_valid:
                    return True
                last_valid = val

        # 更新上一页解析结果为本批次结尾的有效值
        self._prev_page_items = last_valid
        return False

    def paginate_batches(
        self,
        start_page: int,
        process_batch_callback,
        batch_size: int=5
    ) -> bool:
        """
        批量并行分页引擎：负责并行抓取一批页面、统一停止判定，并把批次结果交给回调处理。

        回调签名: process_batch_callback(batch_results: Dict[int, list]) -> bool|None
            - 如果返回 False 则停止分页；返回 True/None 则继续。
        """
        has_data = False
        current_batch_start = start_page

        # 使用单个线程池复用线程资源，保证总并发为 self.max_workers
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while True:
                batch_end = current_batch_start + batch_size - 1
                batch_results: Dict[int, Optional[list]] = {}
                parse_error_pages: set = set()

                future_to_page = {
                    executor.submit(self.crawl_page, page): page
                    for page in range(current_batch_start, batch_end + 1)
                }

                for future in as_completed(future_to_page):
                    page = future_to_page[future]
                    try:
                        items = future.result()
                        batch_results[page] = items
                        if items:
                            has_data = True
                    except Exception as e:
                        log_error(f"处理第{page}页时发生错误", e)
                        # 区分解析失败（ParseError）与其它异常
                        if isinstance(e, ParseError):
                            parse_error_pages.add(page)
                        # 失败页使用 None 标记
                        batch_results[page] = None

                sorted_pages = sorted(batch_results.keys())

                # 交给回调处理批次结果
                try:
                    cont = process_batch_callback(batch_results)
                    if cont is False:
                        break
                except Exception as e:
                    log_error("处理批次回调时出错", e)
                    break

                # 统一停止判定（解析错误或与上一页相同）
                if self._should_stop_pagination(sorted_pages, batch_results, parse_error_pages):
                    log_info("分页停止判定命中，停止爬取")
                    break

                current_batch_start = batch_end + 1

        return has_data

    def paginate_sequential(self, start_page: int,  process_page_callback) -> bool:
        """
        顺序分页引擎：逐页请求并交给回调处理；内部会检测连续空页与相邻页相同的情况并停止。

        回调签名: process_page_callback(page:int, items:list) -> bool|None
            - 如果返回 False 则停止分页；返回 True/None 则继续。
        """
        page = start_page
        has_data = False

        while True:
            try:
                items = self.crawl_page(page)
            except Exception as e:
                # 如果是解析失败，作为停止信号；其它异常记录后停止
                if isinstance(e, ParseError):
                    log_info(f"第{page}页解析失败（ParseError），停止爬取: {e}")
                else:
                    log_error(f"抓取第{page}页时发生错误", e)
                break

            # 使用统一的停止判定（基于上一次解析结果）
            batch_results = {page: items}
            if self._should_stop_pagination([page], batch_results):
                log_info(f"第{page}页数据与上一页相同或无更多数据，停止爬取")
                break

            has_data = True

            try:
                cont = process_page_callback(page, items)
                if cont is False:
                    break
            except Exception as e:
                log_error(f"处理第{page}页回调时出错", e)
                break

            page += 1

        return has_data

    def paginate_streaming(self, start_page: int, process_page_callback, max_workers: Optional[int] = None) -> bool:
        """
        流式并行分页引擎：持续提交页码任务，任一页完成即刻处理并保存，保持最多 `max_workers` 个并发任务。

        停止判定：
        - 如果某页抛出 `ParseError`，立即停止；
        - 如果某页解析结果与上一页解析结果相同，立即停止；
        - 如果回调返回 False，则停止。

        回调签名: process_page_callback(page:int, items:list) -> bool|None
        """
        max_workers = max_workers or self.max_workers
        next_page = start_page
        has_data = False
        stop = False
        counter_lock = threading.Lock()

        def worker_loop() -> None:
            nonlocal next_page, has_data, stop
            while True:
                # 获取下一个页号
                with counter_lock:
                    if stop:
                        return
                    page = next_page
                    next_page += 1

                try:
                    items = self.crawl_page(page)
                except Exception as e:
                    if isinstance(e, ParseError):
                        log_info(f"第{page}页解析失败（ParseError），停止爬取: {e}")
                    else:
                        log_error(f"处理第{page}页时发生错误", e)
                    stop = True
                    return

                # 检测与上一页相同（无更多数据）
                prev = self._prev_page_items
                if isinstance(items, list) and prev is not None and items == prev:
                    log_info(f"第{page}页数据与上一页相同，停止爬取")
                    # 更新 prev for consistency
                    self._prev_page_items = items
                    stop = True
                    return

                # 更新 prev
                if isinstance(items, list):
                    self._prev_page_items = items

                # 立即处理并保存这一页
                try:
                    cont = process_page_callback(page, items)
                    if cont is False:
                        stop = True
                        return
                except Exception as e:
                    log_error(f"处理第{page}页回调时出错", e)
                    stop = True
                    return

                if items:
                    has_data = True

        # 启动 worker 数量等于并发限制的长期运行任务
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            workers = [executor.submit(worker_loop) for _ in range(max_workers)]
            # 等待所有 worker 退出（遇到 stop 或者没有更多任务）
            for f in as_completed(workers):
                pass

        return has_data
    
    
    def crawl(self) -> bool:
        """
        执行爬取流程（抽象方法，由子类实现）
        
        Returns:
            是否成功获取到数据
        """
        raise NotImplementedError("子类必须实现 crawl() 方法")
