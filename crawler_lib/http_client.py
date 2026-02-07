"""
HTTP请求客户端模块

负责构建和发送HTTP请求，包含统一的重试机制
"""


import ast
import json
import time
import random
from typing import Any, Dict, Optional
from urllib.parse import urlencode, unquote

import requests

from .config_manager import CrawlerConfig
# 导入新的简化日志系统
from unified_logger import log_request, log_error


# 限流检测关键词
RATE_LIMIT_KEYWORDS = [
    '频繁', '限流', '访问受限', '请稍后', '请求过快' ,'超时',
    'rate limit', 'too many', 'forbidden', 'throttle', 
    'slow down', 'try again later','time-out'
]

class HttpClient:
    """
    HTTP请求客户端
    
    封装HTTP请求的构建和发送逻辑。
    """
    
    @staticmethod
    def _process_dict_placeholders(data_dict: Any, page: int, skip_count: int) -> Any:
        """
        递归处理字典中的占位符
        
        Args:
            data_dict: 要处理的数据（可能是字典、列表或其他类型）
            page: 当前页码
            skip_count: 跳过的记录数
        
        Returns:
            处理后的数据
        """
        if isinstance(data_dict, dict):
            processed_dict = {}
            for key, value in data_dict.items():
                if isinstance(value, str):
                    # 检查是否包含#page占位符
                    if "#page" in value:
                        # 如果是纯#page占位符，替换为数字
                        if value.strip() == "#page":
                            processed_dict[key] = page  # 直接使用数字类型
                        else:
                            # 如果是包含#page的复合字符串，替换为字符串
                            processed_dict[key] = value.replace("#page", str(page)).replace("#skipCount", str(skip_count))
                    else:
                        # 不包含占位符，普通字符串处理
                        processed_dict[key] = value.replace("#page", str(page)).replace("#skipCount", str(skip_count))
                else:
                    # 递归处理嵌套结构
                    processed_dict[key] = HttpClient._process_dict_placeholders(value, page, skip_count)
            return processed_dict
        elif isinstance(data_dict, list):
            # 处理列表中的每个元素
            return [HttpClient._process_dict_placeholders(item, page, skip_count) for item in data_dict]
        else:
            # 其他类型直接返回
            return data_dict
    
    @staticmethod
    def build_request_params(config: CrawlerConfig, page: int, page_size: int = 20) -> tuple[str, str]:
        """
        构建列表页请求参数，替换分页占位符
        
        Args:
            config: 爬虫配置
            page: 当前页码
            page_size: 每页记录数，默认20
        
        Returns:
            处理后的(params, data)元组
        """
        # 计算跳过的记录数
        skip_count = (page - 1) * page_size
        
        # 替换分页占位符
        replacements = {
            "#page": str(page),
            "#skipCount": str(skip_count)
        }
        
        # 处理params字段（简化逻辑：统一转字符串处理）
        params_str = json.dumps(config.params) if isinstance(config.params, dict) else str(config.params or "")
        if "#page" in params_str or "#skipCount" in params_str:
            for placeholder, value in replacements.items():
                params_str = params_str.replace(placeholder, value)
        
        # 处理data字段（支持字典和字符串类型）
        if isinstance(config.data, dict):
            # 使用递归处理嵌套结构中的占位符
            data = HttpClient._process_dict_placeholders(config.data, page, skip_count)
            data_str = json.dumps(data)
        elif isinstance(config.data, str):
            # 如果是字符串（如GraphQL查询），直接替换占位符
            data_str = config.data
            for placeholder, value in replacements.items():
                data_str = data_str.replace(placeholder, value)
        else:
            # 其他情况，转换为字符串处理
            data_str = str(config.data or "")
            for placeholder, value in replacements.items():
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
    def parse_response(response: requests.Response) -> dict | list:
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
            解析后的或列表数据
        
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
                    # 所有方法都失败，返回重试标记而不是抛出异常
                    return {
                        "__needs_retry__": True,
                        "error": "响应非JSON格式，所有解析方法均失败",
                        "original_text": response.text[:500],
                        "error_details": (
                            f"1. response.json(): {error_msg_1}\n"
                            f"2. json.loads(): {error_msg_2}\n"
                            f"3. ast.literal_eval(): {str(e3)}"
                        )
                    }
    
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
    def is_rate_limit(response_data: dict | list) ->tuple[bool,str]:
        """
        检查业务层面是否成功
        
        常见的失败响应格式：
        1. {"code": 1000, "message": "请求过于频繁", "success": false}
        2. {"success": false, "msg": "限流"}
        3. {"status": false, "message": "失败"}
        4. {"error": "...", "data": null}
        
        Args:
            response_data: API响应数据
        
        Returns:
            True表示业务成功，False表示业务失败
        """
        if not isinstance(response_data, dict) and not isinstance(response_data, list):
            return False, "请求失败，响应非字典或列表类型"  
        
        if isinstance(response_data, dict):
            for msg_key in ['message', 'msg', 'error_msg', 'errmsg', 'error_message']:
                if msg_key in response_data:
                    msg = str(response_data[msg_key]).lower()
                    for keyword in RATE_LIMIT_KEYWORDS:
                        if keyword.lower() in msg:
                            return False, f"{msg_key}字段包含限流关键词: {msg}"
        
        # 都没有检测到失败标识，认为成功
        return True, ""
    
    @staticmethod
    def send_request_with_retry(
        url: str,
        method: str = 'GET',
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: int = 30,
        context: str = ""
    ) -> dict | list:
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
        
        Returns:
            响应JSON数据
        """
        
        #print("url",url)
        #print("method",method)
        #print("params",params)
        #print("data",data)
        
        attempt = 0
        headers = headers or {}
        headers["User-Agent"]="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541518) XWEB/17071"
        
        while True:
            attempt += 1
            
            try:
                # 对 params 中可能已经被百分号编码的值进行一次解码，
                # 防止 requests 在构建查询字符串时把 '%' 再次编码成 '%25'
                if params and isinstance(params, dict):
                    try:
                        decoded_params = {}
                        for k, v in params.items():
                            if isinstance(v, str) and '%' in v:
                                decoded_params[k] = unquote(v)
                            else:
                                decoded_params[k] = v
                        params = decoded_params
                    except Exception:
                        # 解码失败时保持原样
                        pass
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
                
                response_data = HttpClient.parse_response(response)
                
                # 检查是否需要重试（非JSON格式响应）
                if isinstance(response_data, dict) and response_data.get("__needs_retry__"):
                    is_success = False
                    reason = f"响应非JSON格式需要重试: {response_data.get('error', '未知错误')}"
                else:
                    is_success, reason = HttpClient.is_rate_limit(response_data)
                
                if not is_success: 
                    wait_time = HttpClient.calculate_retry_delay(attempt)
                    print(f"❌ {context} 请求失败触发限流重试机制,触发原因：{reason}: ", flush=True)
                    print(f"⚠️ {context} - 第{attempt}次重试，等待{wait_time:.0f}秒...", flush=True)
                    time.sleep(wait_time)
                    
                    log_request(
                            url=url,
                            params=params,
                            data=data,
                            response=response_data,
                            method=method
                        )
                    print(f"📝 已记录第{attempt}次重试请求日志", flush=True)
                    
                else:
                    # 成功，如果之前有重试，打印恢复信息
                    if attempt > 1:
                        print(f"✅ {context} 第{attempt}次重试成功", flush=True)
                    
                    return response_data
                
            except Exception as e:
                # 尝试安全获取响应体文本（可能在异常前未定义 response）
                resp_text = None
                status_code = None
                response = None  # 确保变量被定义
                try:
                    # 检查是否有 response 对象可用
                    if 'response' in locals():
                        status_code = getattr(response, 'status_code', None)
                        # 有些响应可能非常大，截取前2000字符保存
                        resp_text = getattr(response, 'text', None)
                        if resp_text is not None:
                            resp_text = resp_text[:500]
                except Exception:
                    resp_text = None

                # 记录到请求历史，保存响应预览以便排查
                try:
                    log_request(
                        url=url,
                        method=method,
                        params=params,
                        data=data,
                        response={
                            "error": str(e),
                            "exception_type": type(e).__name__,
                            "status_code": status_code,
                            "response_text_preview": resp_text
                        }
                    )
                except Exception:
                    pass

                # 也写入错误日志（app_error.log），便于通过错误日志直接查看
                try:
                    preview = resp_text if resp_text is not None else ''
                    log_error(f"请求异常: {str(e)} | status_code={status_code} | 响应前500字符: {preview}", exception=e, ui=False)
                except Exception:
                    pass

                raise RuntimeWarning(f"请求异常: {str(e)}")
