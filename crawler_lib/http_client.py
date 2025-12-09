"""
HTTP请求客户端模块

负责构建和发送HTTP请求，包含统一的重试机制
"""


import ast
import json
import time
import random
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .config_manager import CrawlerConfig
# 导入新的简化日志系统
try:
    from unified_logger import log_request, log_error
except ImportError:
    # 如果日志模块不可用，提供空函数
    def log_request(*args, **kwargs):
        pass
    def log_error(*args, **kwargs):
        pass


# 限流检测关键词
RATE_LIMIT_KEYWORDS = [
    '频繁', '限流', '访问受限', '请稍后', '请求过快',
    'rate limit', 'too many', 'forbidden', 'throttle', 
    'slow down', 'try again later'
]

class HttpClient:
    """
    HTTP请求客户端
    
    封装HTTP请求的构建和发送逻辑。
    """
    
    @staticmethod
    def build_request_params(config: CrawlerConfig, page: int, page_size: int = 20) -> tuple[str, str]:
        """
        构建请求参数，替换分页占位符
        
        Args:
            config: 爬虫配置
            page: 当前页码
            page_size: 每页记录数，默认20
        
        Returns:
            处理后的(params, data)元组
        """
        params_str = str(config.params)
        data_str = str(config.data)
        
        # 计算跳过的记录数
        skip_count = (page - 1) * page_size
        
        # 替换分页占位符
        replacements = {
            "{page}": str(page),
            "{skipCount}": str(skip_count),
            "{pageSize}": str(page_size),
        }
        
        for placeholder, value in replacements.items():
            params_str = params_str.replace(placeholder, value)
            data_str = data_str.replace(placeholder, value)
        
        return params_str, data_str
    
    @staticmethod
    def prepare_request_data(data_str: str, headers: dict) -> Any:
        """
        根据Content-Type准备请求数据
        
        Args:
            data_str: 原始数据字符串
            headers: 请求头
        
        Returns:
            处理后的请求数据
        """
        if data_str in ("nan", "", "None"):
            return None
            
        content_type = headers.get("Content-Type", "")
        
        try:
            data_dict = json.loads(data_str)
            if "urlencoded" in content_type:
                return urlencode(data_dict)
            return data_dict
        except (json.JSONDecodeError, ValueError):
            return data_str
    
    @staticmethod
    def send_request(config: CrawlerConfig, page: int, timeout: int = 30) -> dict:
        """
        发送HTTP请求并返回响应数据
        
        Args:
            config: 爬虫配置
            page: 当前页码
            timeout: 请求超时时间（秒）
        
        Returns:
            响应的JSON数据
        
        Raises:
            requests.RequestException: 请求失败时抛出
        """
        params_str, data_str = HttpClient.build_request_params(config, page)
        
        # 处理URL中的分页占位符
        url = str(config.url)
        skip_count = (page - 1) * 20  # 默认每页20条
        url_replacements = {
            "{page}": str(page),
            "{skipCount}": str(skip_count),
            "{pageSize}": "20",
        }
        
        for placeholder, value in url_replacements.items():
            url = url.replace(placeholder, value)
        
        # 准备请求参数
        request_params = None
        if params_str not in ("nan", "{}", "", "None"):
            try:
                params_dict = json.loads(params_str)
                request_params = params_dict
            except (json.JSONDecodeError, ValueError):
                pass
        
        # 准备请求数据
        request_data = HttpClient.prepare_request_data(data_str, config.headers)
        
        # 根据请求方法发送请求
        if config.request_method.upper() == "POST":
            # POST 请求
            if isinstance(request_data, dict):
                # JSON 格式
                response = requests.post(
                    url=url,
                    headers=config.headers,
                    json=request_data,
                    params=request_params,
                    verify=False,
                    timeout=timeout
                )
            elif isinstance(request_data, str):
                # URL encoded 或纯文本
                response = requests.post(
                    url=url,
                    headers=config.headers,
                    data=request_data,
                    params=request_params,
                    verify=False,
                    timeout=timeout
                )
            else:
                # 无数据的 POST
                response = requests.post(
                    url=url,
                    headers=config.headers,
                    params=request_params,
                    verify=False,
                    timeout=timeout
                )
        else:
            # GET 请求
            response = requests.get(
                url=url,
                headers=config.headers,
                params=request_params,
                verify=False,
                timeout=timeout
            )
        
        response.raise_for_status()
        response_data = HttpClient.parse_response(response)
        
        # 记录请求日志（使用新的简化日志系统）
        try:
            log_request(
                url=url,
                params=request_params,
                data=request_data if isinstance(request_data, dict) else None,
                response=response_data,
                method=config.request_method.upper()
            )
        except Exception as e:
            # 请求日志记录失败不应该影响主要功能
            pass
        
        return response_data
    
    @staticmethod
    def parse_response(response: requests.Response) -> dict:
        """
        智能解析响应体，支持多种格式
        
        尝试顺序：
        1. response.json() - 标准JSON解析
        2. json.loads(response.text) - 处理一些特殊编码
        3. ast.literal_eval(response.text) - 处理Python字面量格式
        4. ast.literal_eval + json.loads - 处理双重编码
        
        Args:
            response: requests响应对象
        
        Returns:
            解析后的字典数据
        
        Raises:
            ValueError: 所有解析方法均失败时抛出
        """
        # 方法1: 尝试使用标准的 response.json()
        try:
            result = response.json()
            if isinstance(result, dict):
                return result
            # 如果返回的是字符串，尝试继续解析
            elif isinstance(result, str):
                try:
                    return json.loads(result)
                except:
                    pass
            return result
        except (json.JSONDecodeError, ValueError) as e1:
            error_msg_1 = str(e1)
            
            # 方法2: 尝试使用 json.loads(response.text)
            try:
                result = json.loads(response.text)
                if isinstance(result, dict):
                    return result
                elif isinstance(result, str):
                    # 可能是双重编码的JSON字符串
                    try:
                        return json.loads(result)
                    except:
                        pass
                return result
            except (json.JSONDecodeError, ValueError) as e2:
                error_msg_2 = str(e2)
                
                # 方法3: 尝试使用 ast.literal_eval (适用于Python字面量格式)
                try:
                    result = ast.literal_eval(response.text)
                    # 确保返回的是字典类型
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, str):
                        # ast.literal_eval返回了字符串，尝试再次JSON解析
                        try:
                            return json.loads(result)
                        except:
                            pass
                    raise ValueError(f"ast.literal_eval返回了非字典类型: {type(result)}")
                except (ValueError, SyntaxError) as e3:
                    # 所有方法都失败，抛出详细错误信息
                    error_details = (
                        f"无法解析响应体，尝试了以下方法均失败:\n"
                        f"1. response.json(): {error_msg_1}\n"
                        f"2. json.loads(): {error_msg_2}\n"
                        f"3. ast.literal_eval(): {str(e3)}\n"
                        f"响应内容前500字符: {response.text[:500]}"
                    )
                    raise ValueError(error_details)
    
    @staticmethod
    def calculate_retry_delay(attempt: int, max_delay: int = 600) -> float:
        """
        计算重试延迟时间（指数退避算法）
        
        公式: min(3^attempt + random(0, 10), max_delay)
        延迟序列: 3秒 → 9秒 → 27秒 → 81秒 → 243秒 → 600秒(封顶)
        
        Args:
            attempt: 当前重试次数（从1开始）
            max_delay: 最大延迟时间（秒），默认600秒（10分钟）
        
        Returns:
            延迟时间（秒）
        """
        base_delay = 3 ** attempt
        jitter = random.uniform(0, 10)
        return min(base_delay + jitter, max_delay)
    
    @staticmethod
    def is_rate_limit(data: Any) -> bool:
        """
        检测异常是否为限流相关错误
        
        Args:
            data: 待监测的数据
        
        Returns:
            True表示被限流，False表示正常
        """
        error_str = str(data).lower()
        for keyword in RATE_LIMIT_KEYWORDS:
            if keyword.lower() in error_str:
                return True
        return False
    
    @staticmethod
    def send_request_with_retry(
        url: str,
        method: str = 'GET',
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: int = 30,
        context: str = "",
        validate_non_empty: bool = False,
        items_key: Optional[str] = None
    ) -> Dict:
        """
        发送HTTP请求，带无限重试机制
        
        策略：
        - 正常请求：无延迟
        - 限流/失败：指数退避重试，直到成功
        - 延迟序列: 3秒 → 9秒 → 27秒 → 81秒 → 243秒 → 600秒(封顶)
        - **新增**：空数据检测与重试（用于联系人获取场景）
        
        Args:
            url: 请求URL
            method: GET/POST
            headers: 请求头
            params: URL参数
            data: POST数据（字典格式）
            timeout: 超时时间
            context: 上下文描述（用于日志输出）
            validate_non_empty: 是否验证返回数据非空（用于联系人获取）
            items_key: 数据项的键路径（用于提取数据列表）
        
        Returns:
            响应JSON数据（必定成功才返回）
        """
        attempt = 0
        headers = headers or {}
        
        while True:
            attempt += 1
            
            try:
                # 发送请求
                if method.upper() == 'POST':
                    content_type = headers.get('Content-Type', '').lower()
                    if 'application/json' in content_type:
                        response = requests.post(
                            url, json=data, params=params, 
                            headers=headers, verify=False, timeout=timeout
                        )
                    else:
                        response = requests.post(
                            url, data=data, params=params, 
                            headers=headers, verify=False, timeout=timeout
                        )
                else:
                    response = requests.get(
                        url, params=params, headers=headers, 
                        verify=False, timeout=timeout
                    )
                
                response.raise_for_status()
                response_data = HttpClient.parse_response(response)
                
                # 检测业务层限流
                if HttpClient.is_rate_limit(response_data):
                    raise Exception(response_data)
                
             
                # 成功，如果之前有重试，打印恢复信息
                if attempt > 1:
                    print(f"✅ {context} 第{attempt}次重试成功", flush=True)
                
                return response_data
                
            except Exception as e:
                
                is_rate_limit = HttpClient.is_rate_limit(e)
                
                if not is_rate_limit and not validate_non_empty:
                    # 非限流且不验证空数据，直接抛出异常
                    raise
                
            
                wait_time = HttpClient.calculate_retry_delay(attempt)
                
                # 控制台只显示简化的错误信息
                error_msg = str(e)
                if len(error_msg) > 100:
                    error_msg = error_msg[:100] + "..."
                
                print(f"⚠️ {context} ，第{attempt}次重试，"
                      f"等待{wait_time:.0f}秒... ({error_msg})", flush=True)
                
                # 将详细错误信息记录到日志文件
                try:
                    log_request(
                        url=url,
                        params=params,
                        data=data,
                        response={"error": str(e), "attempt": attempt},
                        method=f"{method}_RETRY"
                    )
                except Exception:
                    # 如果日志记录失败，忽略错误
                    pass
                
                time.sleep(wait_time)
                # 继续重试
