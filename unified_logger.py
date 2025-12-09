"""
统一日志模块 - 简化版

满足以下需求：
1. 控制台输出：简洁明了
2. 请求日志文件：记录所有请求参数和响应体 (request_history.log)
3. 错误日志文件：记录系统错误 (app_error.log)
"""

import logging
import json
import os
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler


class UnifiedLogger:
    """统一日志记录器"""
    
    def __init__(self):
        self._loggers = {}
        self._setup_loggers()
    
    def _setup_loggers(self):
        """设置日志记录器"""
        # 确保日志目录存在
        os.makedirs("logs", exist_ok=True)
        
        # 1. 控制台日志记录器 - 简洁输出
        console_logger = logging.getLogger('console')
        if not console_logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter('%(message)s'))
            console_logger.addHandler(console_handler)
            console_logger.setLevel(logging.INFO)
            console_logger.propagate = False
        self._loggers['console'] = console_logger
        
        # 2. 请求日志记录器 - 记录所有请求参数和响应体
        # 注意：增大文件大小限制以减少多线程环境下的文件轮转冲突
        request_logger = logging.getLogger('request')
        if not request_logger.handlers:
            request_handler = RotatingFileHandler(
                'logs/request_history.log',
                maxBytes=50*1024*1024,  # 增大到50MB，减少轮转频率
                backupCount=3,
                encoding='utf-8',
                delay=True  # 延迟打开文件，减少文件锁冲突
            )
            request_handler.setLevel(logging.DEBUG)
            request_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            request_logger.addHandler(request_handler)
            request_logger.setLevel(logging.DEBUG)
            request_logger.propagate = False
        self._loggers['request'] = request_logger
        
        # 3. 错误日志记录器 - 记录系统错误
        error_logger = logging.getLogger('error')
        if not error_logger.handlers:
            error_handler = RotatingFileHandler(
                'logs/app_error.log',
                maxBytes=5*1024*1024,  # 5MB
                backupCount=5,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            error_logger.addHandler(error_handler)
            error_logger.setLevel(logging.ERROR)
            error_logger.propagate = False
        self._loggers['error'] = error_logger
    
    # ========== 控制台输出 ==========
    def console(self, message: str) -> None:
        """控制台输出 - 简洁信息"""
        self._loggers['console'].info(message)
    
    # ========== 请求日志 ==========
    def log_request(self, url: str, method: str = 'GET', 
                   params: Optional[Dict[str, Any]] = None,
                   data: Any = None, 
                   response: Any = None) -> None:
        """记录请求参数和响应体到请求日志文件"""
        # 构建请求信息
        request_info = f"[{method}] {url}"
        
        if params:
            params_str = self._safe_json(params)
            request_info += f"\n参数: {params_str}"
        
        if data:
            data_str = self._safe_json(data)
            request_info += f"\n请求体: {data_str}"
        
        # 记录请求
        self._loggers['request'].debug(request_info)
        
        # 记录响应
        if response is not None:
            response_str = self._safe_json(response, max_length=5000)
            self._loggers['request'].debug(f"响应体: {response_str}\n{'-'*80}")
    
    # ========== 错误日志 ==========
    def log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """记录错误到错误日志文件，同时在控制台显示简化信息"""
        # 控制台显示简化错误
        self.console(f"❌ 错误: {message}")
        
        # 文件记录详细错误
        if exception:
            error_detail = f"{message} | 异常: {type(exception).__name__}: {str(exception)}"
            self._loggers['error'].error(error_detail)
        else:
            self._loggers['error'].error(message)
    
    def log_exception(self, message: str) -> None:
        """记录异常（包含堆栈信息）"""
        import traceback
        # 控制台显示简化信息
        self.console(f"❌ 异常: {message}")
        
        # 文件记录完整堆栈
        error_detail = f"{message}\n{traceback.format_exc()}"
        self._loggers['error'].error(error_detail)
    
    # ========== 辅助方法 ==========
    def _safe_json(self, obj: Any, max_length: int = 2000) -> str:
        """安全的JSON序列化"""
        try:
            json_str = json.dumps(obj, ensure_ascii=False, indent=2)
            if len(json_str) > max_length:
                return json_str[:max_length] + "\n...[截断]"
            return json_str
        except (TypeError, ValueError):
            result = str(obj)
            if len(result) > max_length:
                return result[:max_length] + "...[截断]"
            return result


# 全局单例
_logger = None

def get_logger() -> UnifiedLogger:
    """获取日志记录器实例"""
    global _logger
    if _logger is None:
        _logger = UnifiedLogger()
    return _logger


# ========== 便捷函数 ==========

def console(message: str) -> None:
    """控制台输出"""
    get_logger().console(message)


def log_request(url: str, method: str = 'GET',
               params: Optional[Dict[str, Any]] = None,
               data: Any = None,
               response: Any = None) -> None:
    """记录请求"""
    get_logger().log_request(url, method, params, data, response)


def log_error(message: str, exception: Optional[Exception] = None) -> None:
    """记录错误"""
    get_logger().log_error(message, exception)


def log_exception(message: str) -> None:
    """记录异常"""
    get_logger().log_exception(message)


# ========== 兼容旧代码的函数 ==========

def log_info(message: str) -> None:
    """兼容：记录信息（仅控制台）"""
    console(message)


def log_warning(message: str) -> None:
    """兼容：记录警告（控制台+错误日志）"""
    console(f"⚠️  警告: {message}")
    get_logger()._loggers['error'].warning(message)


def log_startup_info(app_name: str, version: Optional[str] = None) -> None:
    """兼容：记录启动信息"""
    message = f"🚀 启动 {app_name}"
    if version:
        message += f" {version}"
    console(message)


def log_shutdown_info(app_name: str, runtime: Optional[str] = None) -> None:
    """兼容：记录关闭信息"""
    message = f"👋 关闭 {app_name}"
    if runtime:
        message += f" (运行时间: {runtime})"
    console(message)


def log_import_error(module_name: str, solution: Optional[str] = None) -> None:
    """兼容：记录导入错误"""
    message = f"导入模块失败: {module_name}"
    if solution:
        message += f" - {solution}"
    log_error(message)


# ========== 爬虫专用函数 ==========

def log_page_progress(page: int, count: int) -> None:
    """爬虫：记录页面进度"""
    console(f"📄 第{page}页完成，获取到{count}条数据")


def log_list_progress(page: int, company_count: int) -> None:
    """爬虫：记录公司列表获取进度"""
    console(f"📄 第{page}页 - 获取公司列表：{company_count}个")


def log_contacts_saved(page: int, contact_count: int) -> None:
    """爬虫：记录联系人保存进度"""
    console(f"💾 第{page}页 - 已保存{contact_count}条联系人")


# ========== UI相关函数 ==========

def log_config_error(config_file: str, error_detail: str) -> None:
    """UI：记录配置错误"""
    log_error(f"配置文件错误 [{config_file}]: {error_detail}")


def log_file_operation(operation: str, file_path: str, 
                      success: bool = True, error: Optional[str] = None) -> None:
    """UI：记录文件操作"""
    if success:
        console(f"✅ {operation}: {file_path}")
    else:
        log_error(f"{operation}失败: {file_path} - {error}")


if __name__ == "__main__":
    # 测试统一日志系统
    print("=" * 50)
    print("测试统一日志系统")
    print("=" * 50)
    
    # 测试控制台输出
    console("这是一条控制台消息")
    log_info("这是一条信息日志")
    log_warning("这是一条警告日志")
    
    # 测试启动和关闭
    log_startup_info("测试程序", "v1.0")
    log_shutdown_info("测试程序", "00:01:30")
    
    # 测试请求日志
    log_request(
        url="https://api.example.com/data",
        method="POST",
        params={"page": 1, "size": 10},
        data={"keyword": "测试"},
        response={"status": "success", "data": [{"id": 1, "name": "测试数据"}]}
    )
    
    # 测试错误日志
    log_error("这是一个测试错误", Exception("测试异常"))
    
    # 测试异常日志
    try:
        result = 1 / 0
    except Exception:
        log_exception("除零错误")
    
    # 测试爬虫函数
    log_page_progress(1, 50)
    log_list_progress(2, 30)
    log_contacts_saved(2, 25)
    
    # 测试UI函数
    log_config_error("config.xlsx", "文件不存在")
    log_file_operation("保存文件", "test.xlsx", success=True)
    log_file_operation("读取文件", "missing.xlsx", success=False, error="文件不存在")
    
    print("\n" + "=" * 50)
    print("✅ 日志测试完成！")
    print("请检查以下文件：")
    print("  - logs/request_history.log (请求日志)")
    print("  - logs/app_error.log (错误日志)")
    print("=" * 50)
