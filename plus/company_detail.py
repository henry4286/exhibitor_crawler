"""
多线程版本的公司详情爬虫程序
通过配置文件驱动的两次请求爬虫，获取公司及联系人信息
支持多线程并发处理，提高数据抓取速度
支持智能重试机制，处理HTTP错误和业务层面的失败
"""

import json
import os
import sys
import time
import random
import threading
import multiprocessing
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from abc import ABC, abstractmethod
from queue import Queue
from dataclasses import dataclass, field
from enum import Enum
import urllib3

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlencode

import save_to_excel

# 全局调试模式控制
DEBUG_MODE = False


class RetryError(Exception):
    """重试失败异常"""
    def __init__(self, message: str, last_response: Any = None, attempts: int = 0):
        super().__init__(message)
        self.last_response = last_response
        self.attempts = attempts


@dataclass
class RetryConfig:
    """重试配置数据类
    
    Attributes:
        max_retries: 最大重试次数（默认3次）
        base_delay: 基础延迟时间，单位秒（默认1秒）
        max_delay: 最大延迟时间，单位秒（默认60秒）
        exponential_base: 指数退避的基数（默认2）
        jitter: 是否添加随机抖动（默认True，避免惊群效应）
        retry_on_http_errors: 需要重试的HTTP状态码列表
        retry_on_exceptions: 需要重试的异常类型列表
    """
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_http_errors: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_exceptions: List[type] = field(default_factory=lambda: [
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    ])
    
    def calculate_delay(self, attempt: int) -> float:
        """计算第N次重试的延迟时间（指数退避 + 可选抖动）"""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            # 添加±25%的随机抖动
            jitter_range = delay * 0.25
            delay = delay + random.uniform(-jitter_range, jitter_range)
        return max(0, delay)


class ResponseValidator:
    """响应验证器 - 用于判断API响应是否表示成功
    
    支持多种验证规则，可通过配置文件动态指定：
    1. 字段值检查：检查响应中特定字段是否等于/不等于某个值
    2. 字段存在检查：检查响应中是否存在特定字段
    3. 关键词检查：检查响应中是否包含失败相关的关键词
    4. 自定义验证函数
    
    配置格式（JSON字符串）:
    {
        "success_field": "success",           # 成功标志字段路径
        "success_value": true,                # 成功时的值（可选，默认为true）
        "code_field": "code",                 # 状态码字段路径（可选）
        "success_codes": [0, 200, 1],         # 成功的状态码列表（可选）
        "failure_keywords": ["频繁", "稍后", "限制", "失败"],  # 失败关键词（可选）
        "data_field": "data"                  # 数据字段路径，用于检查是否有实际数据（可选）
    }
    """
    
    # 通用失败关键词（中英文）
    DEFAULT_FAILURE_KEYWORDS = [
        # 中文关键词
        "请求过于频繁", "稍后再试", "请稍后", "操作频繁", "访问过快",
        "请求限制", "访问限制", "频率限制", "限流", "被限制",
        "服务器繁忙", "系统繁忙", "服务繁忙", "请求失败", "操作失败",
        "token失效", "token过期", "登录失效", "会话过期", "未授权",
        "参数错误", "参数无效", "非法请求", "请求无效",
        # 英文关键词
        "rate limit", "too many requests", "try again later", "please wait",
        "request failed", "server busy", "service unavailable",
        "token expired", "unauthorized", "invalid token",
        "invalid request", "bad request"
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化验证器
        
        Args:
            config: 验证配置字典，如果为None则使用默认的通用验证规则
        """
        self.config = config or {}
        self.success_field = self.config.get('success_field')
        self.success_value = self.config.get('success_value', True)
        self.code_field = self.config.get('code_field')
        self.success_codes = self.config.get('success_codes', [0, 200, 1, "0", "200", "1"])
        self.failure_keywords = self.config.get('failure_keywords', self.DEFAULT_FAILURE_KEYWORDS)
        self.data_field = self.config.get('data_field')
        self.message_field = self.config.get('message_field', 'message')
    
    def validate(self, response: Any) -> Tuple[bool, str]:
        """验证响应是否成功
        
        Args:
            response: API响应数据（通常是字典）
            
        Returns:
            Tuple[bool, str]: (是否成功, 失败原因描述)
        """
        if response is None:
            return False, "响应为空"
        
        # 如果响应不是字典，尝试进行基本验证
        if not isinstance(response, dict):
            if isinstance(response, list):
                # 列表响应通常表示成功
                return True, ""
            return False, f"响应格式异常: {type(response)}"
        
        # 1. 检查成功标志字段
        if self.success_field:
            success_value = self._get_nested_value(response, self.success_field)
            if success_value is not None:
                # 处理字符串形式的布尔值
                if isinstance(success_value, str):
                    success_value = success_value.lower() in ('true', '1', 'yes', 'ok')
                if success_value != self.success_value:
                    msg = self._get_nested_value(response, self.message_field) or "业务处理失败"
                    return False, f"业务失败: {msg}"
        
        # 2. 检查状态码字段
        if self.code_field:
            code_value = self._get_nested_value(response, self.code_field)
            if code_value is not None:
                # 转换为可比较的格式
                code_str = str(code_value)
                success_codes_str = [str(c) for c in self.success_codes]
                if code_str not in success_codes_str:
                    msg = self._get_nested_value(response, self.message_field) or f"状态码异常: {code_value}"
                    return False, f"状态码错误({code_value}): {msg}"
        
        # 3. 检查失败关键词
        response_str = json.dumps(response, ensure_ascii=False).lower()
        for keyword in self.failure_keywords:
            if keyword.lower() in response_str:
                msg = self._get_nested_value(response, self.message_field) or f"检测到失败关键词: {keyword}"
                return False, f"关键词匹配: {msg}"
        
        # 4. 检查数据字段是否存在且非空（可选）
        if self.data_field:
            data_value = self._get_nested_value(response, self.data_field)
            if data_value is None or (isinstance(data_value, (list, dict, str)) and len(data_value) == 0):
                # 数据为空不一定是错误，可能只是没有数据，这里只记录但不判断为失败
                debug_print(f"数据字段 '{self.data_field}' 为空")
        
        return True, ""
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """从嵌套字典中获取值"""
        if not key_path:
            return None
        
        keys = key_path.split('.')
        current = data
        
        try:
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list):
                    try:
                        current = current[int(key)]
                    except (ValueError, IndexError):
                        return None
                else:
                    return None
                if current is None:
                    return None
            return current
        except Exception:
            return None
    
    @classmethod
    def from_config_string(cls, config_str: Optional[str]) -> 'ResponseValidator':
        """从配置字符串创建验证器"""
        if not config_str or pd.isna(config_str) or config_str == '':
            return cls()
        
        try:
            if isinstance(config_str, str):
                config = json.loads(config_str)
            elif isinstance(config_str, dict):
                config = config_str
            else:
                config = {}
            return cls(config)
        except (json.JSONDecodeError, TypeError):
            return cls()

def debug_print(message: str, force_flush: bool = True):
    """调试信息打印函数，只在DEBUG_MODE为True时输出"""
    if DEBUG_MODE:
        print(f"[{threading.current_thread().name}] {message}", flush=force_flush)


class ConfigManager:
    """配置管理器，负责读取和解析Excel配置文件"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
    
    def load_config(self, exhibition_code: str) -> Dict[str, Any]:
        """加载指定展览的配置"""
        try:
            df = pd.read_excel(self.config_path)
            config_row = df[df['exhibition_code'] == exhibition_code]
            
            if config_row.empty:
                raise ValueError(f"No configuration found for exhibition_code: {exhibition_code}")
            
            self.config = config_row.iloc[0].to_dict()
            return self.config
            
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")
    
    def get_company_list_config(self) -> Dict[str, Any]:
        """获取公司列表请求配置"""
        if not self.config:
            raise ValueError("Config not loaded")
        
        return {
            'url': self.config.get('url'),
            'method': self.config.get('request_method', 'GET'),
            'headers': self._safe_json_load(self.config.get('headers') or '{}'),
            'params': self._safe_json_load(self.config.get('params') or '{}'),
            'data': self._safe_json_load(self.config.get('data') or '{}'),
            'paging_key': self.config.get('pagging'),
            'items_key': self.config.get('items_key'),
            'company_name_key': self.config.get('company_name_key'),
            'id_key': self.config.get('id_key')
        }
    
    def get_company_detail_config(self) -> Dict[str, Any]:
        """获取公司详情请求配置"""
        if not self.config:
            raise ValueError("Config not loaded")
        
        return {
            'url': self.config.get('url_detail'),
            'method': self.config.get('request_method_detail'),
            'headers': self._safe_json_load(self.config.get('headers_detail') or '{}'),
            'params': self._safe_json_load(self.config.get('params_detail') or '{}'),
            'data': self._safe_json_load(self.config.get('data_detail') or '{}'),
            'items_key': self.config.get('items_key_detail'),
            'info_key': self._safe_json_load(self.config.get('info_key') or '{}')
        }
    
    def get_retry_config(self) -> RetryConfig:
        """获取重试配置
        
        从Excel配置中读取重试相关参数，如果没有配置则使用默认值
        支持的配置字段：
        - retry_max_retries: 最大重试次数
        - retry_base_delay: 基础延迟时间（秒）
        - retry_max_delay: 最大延迟时间（秒）
        """
        if not self.config:
            return RetryConfig()
        
        return RetryConfig(
            max_retries=int(self.config.get('retry_max_retries', 3)),
            base_delay=float(self.config.get('retry_base_delay', 1.0)),
            max_delay=float(self.config.get('retry_max_delay', 60.0)),
            exponential_base=float(self.config.get('retry_exponential_base', 2.0)),
            jitter=bool(self.config.get('retry_jitter', True))
        )
    
    def get_response_validator(self) -> ResponseValidator:
        """获取响应验证器配置
        
        从Excel配置中读取验证器参数，如果没有配置则使用默认验证器
        支持的配置字段（JSON格式）：
        - response_validator: 响应验证配置JSON字符串
        """
        if not self.config:
            return ResponseValidator()
        
        validator_config = self.config.get('response_validator')
        return ResponseValidator.from_config_string(validator_config)
    
    def _safe_json_load(self, json_str: Any) -> Dict[str, Any]:
        """安全地加载JSON字符串"""
        try:
            if pd.isna(json_str) or json_str == '' or json_str is None:
                return {}
            if isinstance(json_str, str):
                return json.loads(json_str)
            elif isinstance(json_str, dict):
                return json_str
            else:
                return {}
        except (json.JSONDecodeError, TypeError):
            return {}


class ThreadSafeHTTPClient:
    """线程安全的HTTP客户端，负责发送请求
    
    支持智能重试机制：
    1. HTTP层面的错误重试（网络错误、超时、服务器错误等）
    2. 业务层面的错误重试（通过ResponseValidator验证响应内容）
    3. 指数退避策略，避免对服务器造成压力
    """
    
    def __init__(self, retry_config: Optional[RetryConfig] = None, 
                 response_validator: Optional[ResponseValidator] = None):
        """初始化HTTP客户端
        
        Args:
            retry_config: 重试配置，如果为None则使用默认配置
            response_validator: 响应验证器，如果为None则使用默认验证器
        """
        # 禁用SSL警告
        urllib3.disable_warnings()
        # 创建session会话池，提高连接复用率
        self._session_lock = threading.Lock()
        self._sessions = {}
        # 重试配置
        self.retry_config = retry_config or RetryConfig()
        # 响应验证器
        self.response_validator = response_validator or ResponseValidator()
        # 重试统计（线程安全）
        self._stats_lock = threading.Lock()
        self._retry_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_retries': 0,
            'http_errors': 0,
            'business_errors': 0
        }
    
    def _get_session(self, thread_id: str) -> requests.Session:
        """获取线程专用的session"""
        with self._session_lock:
            if thread_id not in self._sessions:
                self._sessions[thread_id] = requests.Session()
                # 配置session - 注意：这里不使用HTTPAdapter的max_retries
                # 因为我们实现了自己的重试逻辑，可以处理业务层面的失败
                adapter = HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=20,
                    max_retries=0  # 禁用Adapter层的重试，使用我们自己的重试逻辑
                )
                self._sessions[thread_id].mount('http://', adapter)
                self._sessions[thread_id].mount('https://', adapter)
            return self._sessions[thread_id]
    
    def _execute_request(self, session: requests.Session, url: str, method: str,
                        headers: Optional[Dict[str, Any]] = None,
                        params: Optional[Dict[str, Any]] = None,
                        data: Optional[Dict[str, Any]] = None) -> requests.Response:
        """执行单次HTTP请求（内部方法）"""
        request_params = {
            'headers': headers or {},
            'verify': False,
            'timeout': 30
        }
        
        if method.upper() == 'GET':
            if params:
                request_params['params'] = params
            return session.get(url, **request_params)
            
        elif method.upper() == 'POST':
            if params:
                request_params['params'] = urlencode(params)
            if data:
                if headers and "Content-Type" in headers and "urlencoded" in headers["Content-Type"]:
                    request_params['data'] = urlencode(data)
                else:
                    request_params['data'] = json.dumps(data)
            return session.post(url, **request_params)
            
        else:
            raise ValueError(f"Unsupported request method: {method}")
    
    def send_request(self, url: str, method: str, headers: Optional[Dict[str, Any]] = None,
                    params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None,
                    retry_config: Optional[RetryConfig] = None,
                    response_validator: Optional[ResponseValidator] = None) -> Dict[str, Any]:
        """发送HTTP请求（带智能重试机制）
        
        Args:
            url: 请求URL
            method: 请求方法（GET/POST）
            headers: 请求头
            params: URL参数
            data: 请求体数据
            retry_config: 本次请求的重试配置（覆盖默认配置）
            response_validator: 本次请求的响应验证器（覆盖默认验证器）
            
        Returns:
            解析后的JSON响应数据
            
        Raises:
            RetryError: 重试次数用尽后仍然失败
            ValueError: 不支持的请求方法
        """
        thread_id = threading.current_thread().name
        session = self._get_session(thread_id)
        
        # 使用本次请求的配置或默认配置
        config = retry_config or self.retry_config
        validator = response_validator or self.response_validator
        
        # 更新统计
        with self._stats_lock:
            self._retry_stats['total_requests'] += 1
        
        last_exception = None
        last_response = None
        
        for attempt in range(config.max_retries + 1):
            try:
                # 如果不是第一次尝试，等待一段时间
                if attempt > 0:
                    delay = config.calculate_delay(attempt - 1)
                    debug_print(f"🔄 第{attempt}次重试，等待{delay:.2f}秒...")
                    print(f"⏳ [{thread_id}] 第{attempt}次重试，等待{delay:.2f}秒后重新请求...", flush=True)
                    time.sleep(delay)
                    
                    with self._stats_lock:
                        self._retry_stats['total_retries'] += 1
                
                # 执行请求
                response = self._execute_request(session, url, method, headers, params, data)
                
                # 检查HTTP状态码
                if response.status_code in config.retry_on_http_errors:
                    with self._stats_lock:
                        self._retry_stats['http_errors'] += 1
                    raise requests.exceptions.HTTPError(
                        f"HTTP {response.status_code}: 服务器返回错误状态码",
                        response=response
                    )
                
                # 尝试解析响应
                try:
                    response_data = json.loads(response.content)
                except json.JSONDecodeError as e:
                    debug_print(f"JSON解析失败: {e}")
                    # 如果响应不是JSON，检查HTTP状态码
                    response.raise_for_status()
                    # 如果状态码正常但不是JSON，返回原始文本
                    return {"_raw_response": response.text}
                
                last_response = response_data
                
                # 使用验证器检查业务层面的成功/失败
                is_success, error_msg = validator.validate(response_data)
                
                if is_success:
                    # 请求成功
                    with self._stats_lock:
                        self._retry_stats['successful_requests'] += 1
                    
                    if attempt > 0:
                        print(f"✅ [{thread_id}] 第{attempt}次重试成功！", flush=True)
                    
                    return response_data
                else:
                    # 业务层面的失败，需要重试
                    with self._stats_lock:
                        self._retry_stats['business_errors'] += 1
                    
                    debug_print(f"业务验证失败: {error_msg}")
                    
                    if attempt < config.max_retries:
                        print(f"⚠️  [{thread_id}] 请求失败（{error_msg}），准备重试...", flush=True)
                    
                    # 继续重试循环
                    last_exception = RetryError(error_msg, last_response, attempt + 1)
                    continue
                    
            except (requests.exceptions.Timeout, 
                    requests.exceptions.ConnectionError, 
                    requests.exceptions.ChunkedEncodingError) as e:
                # 可重试的网络异常
                last_exception = e
                with self._stats_lock:
                    self._retry_stats['http_errors'] += 1
                
                debug_print(f"请求异常 (attempt {attempt + 1}): {type(e).__name__}: {e}")
                
                if attempt < config.max_retries:
                    print(f"⚠️  [{thread_id}] 请求异常（{type(e).__name__}），准备重试...", flush=True)
                continue
                
            except requests.exceptions.HTTPError as e:
                # HTTP错误
                last_exception = e
                with self._stats_lock:
                    self._retry_stats['http_errors'] += 1
                
                # 检查是否是可重试的状态码
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code in config.retry_on_http_errors:
                        debug_print(f"HTTP错误 {e.response.status_code}，准备重试...")
                        if attempt < config.max_retries:
                            print(f"⚠️  [{thread_id}] HTTP错误（{e.response.status_code}），准备重试...", flush=True)
                        continue
                
                # 不可重试的HTTP错误
                raise
                
            except Exception as e:
                # 其他不可重试的异常
                debug_print(f"不可重试的异常: {type(e).__name__}: {e}")
                raise
        
        # 所有重试都失败了
        with self._stats_lock:
            self._retry_stats['failed_requests'] += 1
        
        error_msg = f"请求失败，已重试{config.max_retries}次"
        if last_exception:
            error_msg += f"，最后一次错误: {last_exception}"
        
        print(f"❌ [{thread_id}] {error_msg}", flush=True)
        
        # 如果有最后的响应数据，抛出包含响应的异常
        if last_response is not None:
            raise RetryError(error_msg, last_response, config.max_retries + 1)
        elif last_exception:
            raise RetryError(error_msg, None, config.max_retries + 1) from last_exception
        else:
            raise RetryError(error_msg, None, config.max_retries + 1)
    
    def send_request_no_retry(self, url: str, method: str, headers: Optional[Dict[str, Any]] = None,
                             params: Optional[Dict[str, Any]] = None, 
                             data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送HTTP请求（不带重试，用于兼容旧代码）"""
        thread_id = threading.current_thread().name
        session = self._get_session(thread_id)
        
        response = self._execute_request(session, url, method, headers, params, data)
        response.raise_for_status()
        return json.loads(response.content)
    
    def get_retry_stats(self) -> Dict[str, int]:
        """获取重试统计信息"""
        with self._stats_lock:
            return self._retry_stats.copy()
    
    def reset_retry_stats(self):
        """重置重试统计"""
        with self._stats_lock:
            self._retry_stats = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'total_retries': 0,
                'http_errors': 0,
                'business_errors': 0
            }
    
    def print_retry_stats(self):
        """打印重试统计信息"""
        stats = self.get_retry_stats()
        print("\n📊 请求统计信息:", flush=True)
        print(f"   总请求数: {stats['total_requests']}", flush=True)
        print(f"   成功请求: {stats['successful_requests']}", flush=True)
        print(f"   失败请求: {stats['failed_requests']}", flush=True)
        print(f"   重试次数: {stats['total_retries']}", flush=True)
        print(f"   HTTP错误: {stats['http_errors']}", flush=True)
        print(f"   业务错误: {stats['business_errors']}", flush=True)
        
        if stats['total_requests'] > 0:
            success_rate = stats['successful_requests'] / stats['total_requests'] * 100
            print(f"   成功率: {success_rate:.1f}%", flush=True)


class DataProcessor:
    """数据处理器，负责解析和转换数据"""
    
    @staticmethod
    def get_nested_value(data: Dict[str, Any], key_path: str) -> Any:
        """从嵌套字典中获取值，支持点号分隔的路径"""
        if not key_path or pd.isna(key_path):
            return ""
        
        keys = key_path.split('.')
        current = data
        
        try:
            for i, key in enumerate(keys):
                debug_print(f"调试信息 - 处理键 {i}: '{key}', 当前类型: {type(current)}")
                if isinstance(current, dict):
                    if key not in current:
                        debug_print(f"调试信息 - 键 '{key}' 不存在于字典中")
                        return ""
                    current = current[key]
                elif isinstance(current, list):
                    try:
                        key_index = int(key)
                        if key_index < len(current):
                            current = current[key_index]
                        else:
                            debug_print(f"调试信息 - 索引 {key_index} 超出列表范围 {len(current)}")
                            return ""
                    except ValueError:
                        debug_print(f"调试信息 - 无法将键 '{key}' 转换为整数")
                        return ""
                else:
                    debug_print(f"调试信息 - 当前值不是字典或列表，类型: {type(current)}")
                    return ""
                debug_print(f"调试信息 - 处理后当前值: {type(current)}")
            return current
        except (KeyError, IndexError, ValueError, TypeError) as e:
            debug_print(f"调试信息 - get_nested_value错误: {e}, key_path: {key_path}, current_type: {type(current)}")
            return ""
    
    @staticmethod
    def update_nested_value(data: Dict[str, Any], key_path: str, value: Any) -> Dict[str, Any]:
        """更新嵌套字典中的值"""
        if not isinstance(data, dict):
            raise ValueError("Input should be a dictionary")
        
        keys = key_path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
        return data
    
    @staticmethod
    def extract_contact_info(company_data: Dict[str, Any], contact_data: Union[Dict, List],
                           company_name_key: str, info_key: Dict[str, str]) -> List[Dict[str, Any]]:
        """提取联系人信息"""
        contacts = []
        
        # 获取公司基础信息
        company_name = DataProcessor.get_nested_value(company_data, company_name_key) or "未知公司"
        
        # 处理公司字段映射（排除公司名称字段，避免重复）
        company_fields = company_name_key.split(',') if company_name_key else []
        # 获取第一个字段作为公司名称字段（通常company_name_key就是公司名称的路径）
        primary_company_field = company_fields[0].strip() if company_fields else None
        
        if isinstance(contact_data, dict):
            # 单个联系人
            contact_info = {"company_name": company_name}
            
            # 添加额外的公司信息字段（跳过第一个，因为已经作为company_name添加）
            for field in company_fields[1:]:
                field = field.strip()
                if field:
                    contact_info[field] = DataProcessor.get_nested_value(company_data, field)
            
            # 映射联系人字段
            for output_key, input_key in info_key.items():
                contact_info[output_key] = DataProcessor.get_nested_value(contact_data, input_key)
            
            contacts.append(contact_info)
            
        elif isinstance(contact_data, list):
            # 多个联系人
            for contact in contact_data:
                contact_info = {"company_name": company_name}
                
                # 添加额外的公司信息字段（跳过第一个，因为已经作为company_name添加）
                for field in company_fields[1:]:
                    field = field.strip()
                    if field:
                        contact_info[field] = company_data.get(field, "")
                
                # 映射联系人字段
                for output_key, input_key in info_key.items():
                    contact_info[output_key] = DataProcessor.get_nested_value(contact, input_key)
                
                contacts.append(contact_info)
                
        else:
            # 没有联系人数据，只保存公司信息
            contact_info = {"company_name": company_name}
            
            # 添加额外的公司信息字段（跳过第一个，因为已经作为company_name添加）
            for field in company_fields[1:]:
                field = field.strip()
                if field:
                    contact_info[field] = company_data.get(field, "")
            
            # 空的联系人字段
            for output_key in info_key.keys():
                contact_info[output_key] = ""
            
            contacts.append(contact_info)
        
        return contacts


class ThreadSafeProgressManager:
    """线程安全的进度管理器，负责断点续传功能"""
    
    def __init__(self, exhibition_code: str):
        self.exhibition_code = exhibition_code
        # 使用脚本所在目录的绝对路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(script_dir, 'temp')
        # 确保temp目录存在
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        self.progress_file = os.path.join(temp_dir, f"progress_{exhibition_code}.json")
        self.saved_companies_file = os.path.join(temp_dir, f"saved_companies_{exhibition_code}.txt")
        self._file_lock = threading.Lock()
        self._memory_lock = threading.Lock()
    
    def load_progress(self) -> Dict[str, Any]:
        """加载进度"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载进度文件失败：{e}", flush=True)
        
        return {
            'page_index': 1,
            'contact_counter': 0,
            'processed_companies_count': 0
        }
    
    def load_saved_companies(self) -> set:
        """加载已处理的公司ID集合"""
        try:
            if os.path.exists(self.saved_companies_file):
                with open(self.saved_companies_file, 'r', encoding='utf-8') as f:
                    return set(line.strip() for line in f if line.strip())
        except Exception as e:
            print(f"加载已处理公司列表失败：{e}", flush=True)
        
        return set()
    
    def save_progress(self, page_index: int, contact_counter: int, processed_count: int):
        """保存进度"""
        try:
            with self._file_lock:
                progress_data = {
                    'page_index': page_index,
                    'contact_counter': contact_counter,
                    'processed_companies_count': processed_count,
                    'last_update': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存进度失败：{e}", flush=True)
    
    def save_company_id(self, company_id: str):
        """保存已处理的公司ID"""
        try:
            with self._file_lock:
                with open(self.saved_companies_file, 'a', encoding='utf-8') as f:
                    f.write(f"{company_id}\n")
        except Exception as e:
            print(f"保存公司ID失败：{e}", flush=True)
    
    def is_company_processed(self, company_id: str, saved_companies: set) -> bool:
        """检查公司是否已处理"""
        return str(company_id) in saved_companies
    
    def reset_progress(self):
        """重置进度文件"""
        try:
            with self._file_lock:
                if os.path.exists(self.progress_file):
                    os.remove(self.progress_file)
                    print(f"🗑️  已删除进度文件：{self.progress_file}")
        except Exception as e:
            print(f"删除进度文件失败：{e}", flush=True)
        
        try:
            with self._file_lock:
                if os.path.exists(self.saved_companies_file):
                    os.remove(self.saved_companies_file)
                    print(f"🗑️  已删除公司列表文件：{self.saved_companies_file}")
        except Exception as e:
            print(f"删除公司列表文件失败：{e}", flush=True)


class ThreadSafeDataSaver:
    """线程安全的数据保存器"""
    
    def __init__(self, exhibition_code: str, batch_size: int = 50):
        self.exhibition_code = exhibition_code
        self.batch_size = batch_size
        self._data_queue = Queue()
        self._save_lock = threading.Lock()
        self._contact_counter = 0
        self._total_saved = 0
    
    def add_contacts(self, contacts: List[Dict[str, Any]]):
        """添加联系人数据到队列"""
        with self._save_lock:
            self._data_queue.put(contacts)
            self._contact_counter += len(contacts)
    
    def save_batch(self) -> int:
        """保存当前批次的数据"""
        contacts_to_save = []
        
        # 从队列中取出数据
        while not self._data_queue.empty() and len(contacts_to_save) < self.batch_size:
            try:
                contacts = self._data_queue.get_nowait()
                contacts_to_save.extend(contacts)
            except:
                break
        
        if contacts_to_save:
            try:
                save_to_excel.save(contacts_to_save, self.exhibition_code)
                with self._save_lock:
                    self._total_saved += len(contacts_to_save)
                    saved_count = len(contacts_to_save)
                    print(f"💾 线程安全保存批次：{saved_count}个联系人（总计：{self._total_saved}个）", flush=True)
                    return saved_count
            except Exception as e:
                print(f"❌ 保存数据失败：{e}", flush=True)
                return 0
        
        return 0
    
    def get_contact_count(self) -> int:
        """获取已处理的联系人总数"""
        with self._save_lock:
            return self._contact_counter
    
    def get_total_saved(self) -> int:
        """获取已保存的联系人总数"""
        with self._save_lock:
            return self._total_saved
    
    def force_save_all(self):
        """强制保存所有剩余数据"""
        while not self._data_queue.empty():
            self.save_batch()


class MultiThreadedDataCrawler:
    """多线程数据爬虫类
    
    支持智能重试机制的多线程数据爬虫，可处理：
    1. HTTP层面的错误（网络超时、连接错误等）
    2. 业务层面的错误（如"请求过于频繁"等）
    3. 自动重试并使用指数退避策略
    """
    
    def __init__(self, exhibition_code: str, config_path: str, 
                 page_workers: Optional[int] = None, company_workers: Optional[int] = None):
        self.exhibition_code = exhibition_code
        self.config_manager = ConfigManager(config_path)
        
        # 加载配置（需要先加载配置才能获取重试配置）
        self.config = self.config_manager.load_config(exhibition_code)
        self.company_list_config = self.config_manager.get_company_list_config()
        self.company_detail_config = self.config_manager.get_company_detail_config()
        
        # 获取重试配置和响应验证器
        self.retry_config = self.config_manager.get_retry_config()
        self.response_validator = self.config_manager.get_response_validator()
        
        # 创建带有重试配置的HTTP客户端
        self.http_client = ThreadSafeHTTPClient(
            retry_config=self.retry_config,
            response_validator=self.response_validator
        )
        
        self.data_processor = DataProcessor()
        self.progress_manager = ThreadSafeProgressManager(exhibition_code)
        self.data_saver = ThreadSafeDataSaver(exhibition_code)
        
        # 获取CPU核心数并智能设置默认线程数
        cpu_count = multiprocessing.cpu_count()
        
        # 多线程配置 - 基于CPU核心数智能设置
        if page_workers is None:
            # 页面获取线程：I/O密集型，可以多一些，但不超过4个
            self.page_workers = min(cpu_count, 4)
        else:
            self.page_workers = page_workers
            
        if company_workers is None:
            # 公司处理线程：每页10-20条公司，数据量不大，不超过CPU核心数
            self.company_workers = min(cpu_count, 6)
        else:
            self.company_workers = company_workers
        
        # 初始化状态
        self.wait_time = random.uniform(0.1, 0.3)  # 降低页面间延迟
        self.contact_counter = 0
        self.processed_count = 0
        
        # 打印重试配置信息
        print(f"🔄 重试配置：最大重试次数={self.retry_config.max_retries}, "
              f"基础延迟={self.retry_config.base_delay}秒, "
              f"最大延迟={self.retry_config.max_delay}秒", flush=True)
    
    def get_companies_page(self, page_index: int) -> Optional[List[Dict[str, Any]]]:
        """获取指定页的公司列表"""
        try:
            # 准备请求参数
            params = self.company_list_config['params'].copy()
            data = self.company_list_config['data'].copy()
            
            # 调试信息
            debug_print(f"调试信息 - 页码: {page_index}")
            debug_print(f"调试信息 - 原始params: {params}")
            debug_print(f"调试信息 - 原始data: {data}")
            debug_print(f"调试信息 - 分页键: {self.company_list_config['paging_key']}")
            
            # 处理分页
            paging_key = self.company_list_config['paging_key']
            if paging_key and page_index is not None and not pd.isna(paging_key):
                # 保持原始参数类型，避免类型转换问题
                page_value = str(page_index)  # 转换为字符串
                if params:
                    params = self.data_processor.update_nested_value(params, paging_key, page_value)
                if data:
                    data = self.data_processor.update_nested_value(data, paging_key, page_value)
            
            debug_print(f"调试信息 - 处理后params: {params}")
            debug_print(f"调试信息 - 处理后data: {data}")
            
            # 发送请求
            response = self.http_client.send_request(
                url=self.company_list_config['url'],
                method=self.company_list_config['method'],
                headers=self.company_list_config['headers'],
                params=params,
                data=data
            )
            
            debug_print(f"调试信息 - 响应类型: {type(response)}")
            debug_print(f"调试信息 - 响应keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
            debug_print(f"调试信息 - response['returnObj']: {response.get('returnObj')}")
            debug_print(f"调试信息 - response['returnObj']类型: {type(response.get('returnObj'))}")
            if response.get('returnObj'):
                debug_print(f"调试信息 - returnObj keys: {list(response['returnObj'].keys()) if isinstance(response['returnObj'], dict) else 'Not a dict'}")
            
            # 检查其他可能的数据字段
            debug_print(f"调试信息 - response['pager']: {response.get('pager')}")
            debug_print(f"调试信息 - response['isSuccess']: {response.get('isSuccess')}")
            debug_print("调试信息 - 完整响应内容:")
            debug_print(json.dumps(response, ensure_ascii=False, indent=2))
            
            # 提取公司列表
            items_key = self.company_list_config['items_key']
            debug_print(f"调试信息 - items_key: {items_key}")
            debug_print(f"调试信息 - items_key类型: {type(items_key)}")
            debug_print(f"调试信息 - pd.isna(items_key): {pd.isna(items_key)}")
            
            if pd.isna(items_key) or items_key == '':
                companies = response if isinstance(response, list) else [response]
            else:
                companies = self.data_processor.get_nested_value(response, items_key)
            
            debug_print(f"调试信息 - 提取的公司列表类型: {type(companies)}")
            debug_print(f"调试信息 - 提取的公司列表内容: {str(companies)[:200] if companies else 'None'}")
            debug_print(f"调试信息 - 提取的公司列表长度: {len(companies) if isinstance(companies, list) else 'Not a list'}")
            
            return companies
                
        except Exception as e:
            print(f"获取第{page_index}页公司列表失败：{e}", flush=True)
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}", flush=True)
            return None
    
    def get_company_contacts(self, company_id: str) -> Optional[Union[Dict, List]]:
        """获取指定公司的联系人信息"""
        try:
            # 准备请求参数
            params = self.company_detail_config['params'].copy()
            data = self.company_detail_config['data'].copy()
            url = self.company_detail_config['url']
            
            # 替换公司ID占位符
            if params:
                params = {k: (v if v != '#company_id' else company_id) for k, v in params.items()}
            if data:
                data = {k: (v if v != '#company_id' else company_id) for k, v in data.items()}
            url = url.replace("#company_id", str(company_id))
            
            # 发送请求
            response = self.http_client.send_request(
                url=url,
                method=self.company_detail_config['method'],
                headers=self.company_detail_config['headers'],
                params=params,
                data=data
            )
            
            # 提取联系人数据
            items_key = self.company_detail_config['items_key']
            if not pd.isna(items_key) and items_key and items_key != "{}":
                return self.data_processor.get_nested_value(response, items_key)
            else:
                return response
                
        except Exception as e:
            print(f"获取公司{company_id}联系人信息失败：{e}", flush=True)
            return None
    
    def process_company(self, company: Dict[str, Any], saved_companies: set) -> bool:
        """处理单个公司（线程安全）"""
        try:
            # 获取公司信息
            company_id = self.data_processor.get_nested_value(company, self.company_list_config['id_key'])
            
            if not company_id:
                debug_print(f"公司没有ID，跳过")
                return False
            
            # 检查是否已处理
            if self.progress_manager.is_company_processed(company_id, saved_companies):
                company_name = self.data_processor.get_nested_value(
                    company, self.company_list_config['company_name_key']
                ) or "未知公司"
                debug_print(f"⏭️  跳过已处理的公司：{company_name}")
                return True
            
            # 获取公司名称
            company_name = self.data_processor.get_nested_value(
                company, self.company_list_config['company_name_key']
            ) or "未知公司"
            
            debug_print(f"正在获取{company_name}的联系人信息")
            
            # 获取联系人信息
            contacts = self.get_company_contacts(company_id)
            
            # 提取联系人数据
            contact_list = self.data_processor.extract_contact_info(
                company_data=company,
                contact_data=contacts if contacts is not None else {},
                company_name_key=self.company_list_config['company_name_key'],
                info_key=self.company_detail_config['info_key']
            )
            
            # 添加到线程安全的保存器
            if contact_list:
                self.data_saver.add_contacts(contact_list)
            
            # 保存已处理的公司ID
            self.progress_manager.save_company_id(company_id)
            
            return True
            
        except Exception as e:
            company_name = self.data_processor.get_nested_value(
                company, self.company_list_config['company_name_key']
            ) or "未知公司"
            print(f"处理公司{company_name}失败：{e}", flush=True)
            return False
    
    def process_companies_batch(self, companies: List[Dict[str, Any]], saved_companies: set) -> Tuple[int, int]:
        """批量处理公司（多线程）"""
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=self.company_workers) as executor:
            # 提交所有任务
            future_to_company = {
                executor.submit(self.process_company, company, saved_companies): company 
                for company in companies
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_company):
                try:
                    if future.result():
                        success_count += 1
                except Exception as e:
                    company = future_to_company[future]
                    company_name = self.data_processor.get_nested_value(
                        company, self.company_list_config['company_name_key']
                    ) or "未知公司"
                    print(f"处理公司{company_name}时发生异常：{e}", flush=True)
        
        return success_count, len(companies)
    
    def get_companies_page_concurrent(self, start_page: int, max_pages: int = 5) -> List[Dict[str, Any]]:
        """并发获取多页公司列表"""
        all_companies = []
        
        with ThreadPoolExecutor(max_workers=self.page_workers) as executor:
            # 提交页面获取任务
            future_to_page = {
                executor.submit(self.get_companies_page, start_page + i): start_page + i 
                for i in range(min(self.page_workers, max_pages))
            }
            
            # 收集结果
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    companies = future.result()
                    if companies:
                        all_companies.extend(companies)
                        print(f"📄 并发获取第{page_num}页，{len(companies)}条记录", flush=True)
                    else:
                        print(f"⚠️  第{page_num}页无数据", flush=True)
                except Exception as e:
                    print(f"❌ 获取第{page_num}页失败：{e}", flush=True)
        
        return all_companies
    
    def run(self):
        """运行多线程爬虫主程序"""
        print(f"🚀 开始处理展览：{self.exhibition_code}（多线程模式）", flush=True)
        
        # 计算实际总线程数
        actual_total_threads = self.page_workers + self.company_workers + 1  # +1 for background saver
        print(f"⚙️  线程配置：页面获取线程={self.page_workers}，公司处理线程={self.company_workers}，实际总线程数={actual_total_threads}", flush=True)
        
        # 加载进度
        progress_data = self.progress_manager.load_progress()
        saved_companies = self.progress_manager.load_saved_companies()
        
        start_page = progress_data.get('page_index', 1)
        self.contact_counter = progress_data.get('contact_counter', 0)
        self.processed_count = progress_data.get('processed_companies_count', 0)
        
        print(f"📋 加载进度：从第{start_page}页开始，已处理{self.processed_count}个公司，已获取{self.contact_counter}个联系人", flush=True)
        
        # 启动后台保存线程
        def background_saver():
            while True:
                time.sleep(5)  # 每5秒检查一次是否需要保存
                if self.data_saver.save_batch() > 0:
                    debug_print("后台保存线程已保存数据")
        
        saver_thread = threading.Thread(target=background_saver, daemon=True)
        saver_thread.start()
        
        # 开始分页处理
        page_index = start_page
        previous_companies = []
        
        try:
            while True:
                time.sleep(self.wait_time)
                
                # 获取当前页公司列表
                companies = self.get_companies_page(page_index)
                
                if not companies:
                    print("No response received.", flush=True)
                    break
                
                if not companies or companies == previous_companies:
                    print("No more data available or no new data found. Exiting.", flush=True)
                    break
                
                previous_companies = companies
                print(f"📄 已获取第{page_index}页，共{len(companies)}条参展商记录", flush=True)
                
                # 多线程处理当前页的公司
                success_count, total_count = self.process_companies_batch(companies, saved_companies)
                self.processed_count += success_count
                
                print(f"✅ 第{page_index}页处理完成：成功{success_count}/{total_count}个公司", flush=True)
                
                # 保存进度
                self.progress_manager.save_progress(
                    page_index, 
                    self.data_saver.get_contact_count(), 
                    self.processed_count
                )
                
                page_index += 1
        
        except KeyboardInterrupt:
            print("\n⚠️  用户中断程序，正在保存数据...", flush=True)
        
        finally:
            # 强制保存所有剩余数据
            print("💾 正在保存所有剩余数据...", flush=True)
            self.data_saver.force_save_all()
            
            # 保存最终进度
            self.progress_manager.save_progress(
                page_index, 
                self.data_saver.get_contact_count(), 
                self.processed_count
            )
            
            print(f"\n🎉 数据处理完成！", flush=True)
            print(f"=" * 50, flush=True)
            print(f"📊 处理结果统计：", flush=True)
            print(f"   总共获取: {self.data_saver.get_contact_count()} 个联系人信息", flush=True)
            print(f"   已保存数: {self.data_saver.get_total_saved()} 个联系人", flush=True)
            print(f"   处理公司: {self.processed_count} 个", flush=True)
            print(f"   处理页数: {page_index - start_page + 1} 页", flush=True)
            
            # 打印请求统计信息（包括重试统计）
            self.http_client.print_retry_stats()
            
            print(f"\n📁 文件信息：", flush=True)
            print(f"   进度文件：{self.progress_manager.progress_file}", flush=True)
            print(f"   公司列表：{self.progress_manager.saved_companies_file}", flush=True)
            print(f"=" * 50, flush=True)


def main():
    """主函数"""
    global DEBUG_MODE
    
    if len(sys.argv) < 2 or sys.argv[1] in ['--help', '-h', 'help']:
        print("Usage: python common_detail_multithreaded.py <exhibition_code> [options]", flush=True)
        print("Options:", flush=True)
        print("  --reset                重置进度，从头开始处理", flush=True)
        print("  --debug                开启调试模式，显示详细调试信息", flush=True)
        print("  --page-workers <num>   设置页面获取线程数（默认基于CPU核心数智能设置）", flush=True)
        print("  --company-workers <num> 设置公司处理线程数（默认基于CPU核心数智能设置）", flush=True)
        print("  --help                 显示此帮助信息", flush=True)
        print("", flush=True)
        print("示例:", flush=True)
        print("  python common_detail_multithreaded.py 农产品 --page-workers 4 --company-workers 16", flush=True)
        sys.exit(0)
    
    exhibition_code = sys.argv[1]
    
    # 解析命令行参数
    reset_progress = False
    page_workers = None  # 使用智能默认值
    company_workers = None  # 使用智能默认值
    
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--reset":
            reset_progress = True
        elif arg == "--debug":
            DEBUG_MODE = True
            print("🔍 调试模式已开启", flush=True)
        elif arg == "--page-workers" and i + 1 < len(args):
            page_workers = int(args[i + 1])
            i += 1
        elif arg == "--company-workers" and i + 1 < len(args):
            company_workers = int(args[i + 1])
            i += 1
        i += 1
    
    # 检查是否要重置进度
    if reset_progress:
        progress_manager = ThreadSafeProgressManager(exhibition_code)
        progress_manager.reset_progress()
        print("🔄 进度已重置，将从头开始处理", flush=True)
        return
    
    try:
        # 构建配置文件路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, '..', 'config.detais.xlsx')
        
        print(f"配置文件路径: {config_path}", flush=True)
        print(f"展览代码: {exhibition_code}", flush=True)
        
        # 显示CPU核心数和智能线程配置
        cpu_count = multiprocessing.cpu_count()
        print(f"💻 检测到CPU核心数: {cpu_count}", flush=True)
        
        # 创建临时爬虫实例以获取实际线程数
        temp_crawler = MultiThreadedDataCrawler(exhibition_code, config_path, page_workers, company_workers)
        print(f"⚙️  线程配置：页面获取线程={temp_crawler.page_workers}, 公司处理线程={temp_crawler.company_workers}", flush=True)
        print(f"📊 实际总线程数: {temp_crawler.page_workers + temp_crawler.company_workers + 1} (含后台保存线程)", flush=True)
        
        # 创建并运行多线程爬虫
        crawler = MultiThreadedDataCrawler(
            exhibition_code, 
            config_path, 
            page_workers=page_workers,
            company_workers=company_workers
        )
        crawler.run()
        
    except Exception as e:
        import traceback
        print(f"An error occurred: {e}", flush=True)
        print(f"详细错误信息: {traceback.format_exc()}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
