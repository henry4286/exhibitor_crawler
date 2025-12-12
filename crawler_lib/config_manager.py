"""
配置管理模块

负责从JSON配置文件中加载和管理爬虫配置
"""

import json
import os
import glob
from dataclasses import dataclass, field
from typing import Any, Optional

from unified_logger import log_info, log_warning, log_exception


@dataclass
class CrawlerConfig:
    """爬虫配置数据类"""
    
    exhibition_code: str = field(metadata={'description': '展会代码'})
    miniprogram_name: str 
    
    # 基本配置
    url: str
    request_method: str
    headers: dict
    params: str
    data: str
    items_key: str
    company_info_keys: dict
    
    # 请求模式（single 或 double）
    request_mode: str = "single"
    
    # 二次请求配置（仅在 double 模式下使用）
    url_detail: Optional[str] = None
    request_method_detail: Optional[str] = None
    headers_detail: Optional[dict] = None
    params_detail: Optional[str] = None
    data_detail: Optional[str] = None
    items_key_detail: Optional[str] = None
    info_key: Optional[dict] = None


class ConfigManager:
    """
    配置管理器类
    
    负责从JSON配置文件中加载并管理各展会的爬虫配置。
    使用单例模式确保配置只加载一次。
    """
    
    _instance: Optional['ConfigManager'] = None
    _configs: dict[str, CrawlerConfig] = {}
    _initialized: bool = False
    _config_dir: str = 'config'
    
    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not ConfigManager._initialized:
            self._load_configurations()
            ConfigManager._initialized = True
    
    def _load_configurations(self) -> None:
        """从JSON文件加载配置"""
        if not os.path.exists(self._config_dir):
            raise FileNotFoundError(f"配置目录不存在: {self._config_dir}")
        
        # 获取所有JSON配置文件
        json_files = glob.glob(os.path.join(self._config_dir, "*.json"))
        
        if not json_files:
            log_warning(f"配置目录 {self._config_dir} 中没有找到JSON配置文件")
            return
        
        config_count = 0
        for json_file in json_files:
            try:
                # 跳过索引文件
                if os.path.basename(json_file) == 'index.json':
                    continue
                
                with open(json_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                exhibition_code = config_data.get('exhibition_code')
                if not exhibition_code:
                    log_warning(f"配置文件 {json_file} 缺少 exhibition_code 字段，跳过")
                    continue
                
                # 基本配置
                config = CrawlerConfig(
                    exhibition_code=exhibition_code,
                    miniprogram_name=config_data.get('miniprogram_name', ''),
                    url=config_data.get('url', ''),
                    request_method=config_data.get('request_method', 'POST'),
                    headers=config_data.get('headers', {}),
                    params=config_data.get('params', ''),
                    data=config_data.get('data', ''),
                    items_key=config_data.get('items_key', ''),
                    company_info_keys=config_data.get('company_info_keys', {}),
                    request_mode=config_data.get('request_mode', 'single')
                )
                
                # 二次请求配置
                if config.request_mode == "double":
                    config.url_detail = config_data.get('url_detail')
                    config.request_method_detail = config_data.get('request_method_detail', 'GET')
                    config.headers_detail = config_data.get('headers_detail', {})
                    config.params_detail = config_data.get('params_detail', '')
                    config.data_detail = config_data.get('data_detail', '')
                    config.items_key_detail = config_data.get('items_key_detail', '')
                    config.info_key = config_data.get('info_key', {})
                
                self._configs[exhibition_code] = config
                config_count += 1
                
            except Exception as e:
                log_exception(f"加载配置文件失败 {json_file}: {e}")
                continue
        
        log_info(f"成功加载 {config_count} 个配置文件")
    
    def get_config(self, exhibition_code: str) -> Optional[CrawlerConfig]:
        """
        获取指定展会的配置
        
        Args:
            exhibition_code: 展会代码
        
        Returns:
            配置对象，如果不存在则返回None
        """
        return self._configs.get(exhibition_code)
    
    def get_all_codes(self) -> list[str]:
        """
        获取所有展会代码
        
        Returns:
            展会代码列表
        """
        return list(self._configs.keys())
    
    def reload_configs(self) -> None:
        """重新加载所有配置"""
        self._configs.clear()
        self._load_configurations()
    
    def _safe_json_load(self, json_data: Any) -> dict:
        """安全地加载JSON数据"""
        try:
            if json_data is None or json_data == '':
                return {}
            if isinstance(json_data, dict):
                return json_data
            elif isinstance(json_data, str):
                return json.loads(json_data)
            else:
                return {}
        except (json.JSONDecodeError, TypeError):
            return {}
