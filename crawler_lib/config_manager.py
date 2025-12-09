"""
配置管理模块

负责从Excel配置文件中加载和管理爬虫配置
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd


@dataclass
class CrawlerConfig:
    """爬虫配置数据类"""
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
    
    负责从Excel配置文件中加载并管理各展会的爬虫配置。
    使用单例模式确保配置只加载一次。
    """
    
    _instance: Optional['ConfigManager'] = None
    _configs: dict[str, CrawlerConfig] = {}
    _initialized: bool = False
    
    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not ConfigManager._initialized:
            self._load_configurations()
            ConfigManager._initialized = True
    
    def _load_configurations(self) -> None:
        """从Excel文件加载配置"""
        config_path = 'config.xlsx'
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        # 尝试多种编码方式读取Excel文件
        try:
            # 首先尝试默认方式
            config_df = pd.read_excel(config_path)
        except Exception as e:
            try:
                # 尝试使用openpyxl引擎
                config_df = pd.read_excel(config_path, engine='openpyxl')
            except Exception:
                # 最后尝试xlrd引擎
                try:
                    config_df = pd.read_excel(config_path, engine='xlrd')
                except Exception as e2:
                    raise ValueError(f"无法读取配置文件 {config_path}，请检查文件格式和编码: {e2}")
        
        for _, row in config_df.iterrows():
            exhibition_code = row['exhibition_code']
            
            # 基本配置
            config = CrawlerConfig(
                url=row['url'],
                request_method=row['request_method'],
                headers=json.loads(row['headers']),
                params=row['params'],
                data=row['data'],
                items_key=row['items_key'],
                company_info_keys=json.loads(row['company_info_keys']),
                request_mode=row.get('request_mode', 'single')
            )
            
            # 二次请求配置
            if config.request_mode == "double":
                config.url_detail = row.get('url_detail')
                config.request_method_detail = row.get('request_method_detail', 'GET')
                config.headers_detail = self._safe_json_load(row.get('headers_detail'))
                config.params_detail = row.get('params_detail')
                config.data_detail = row.get('data_detail')
                config.items_key_detail = row.get('items_key_detail')
                config.info_key = self._safe_json_load(row.get('info_key'))
            
            self._configs[exhibition_code] = config
    
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
    
    def _safe_json_load(self, json_str: Any) -> dict:
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
