"""
基本配置标签页模块

提供基本配置的界面组件
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import json
from .json_editor import JSONEditor


class BasicConfigTab:
    """基本配置标签页"""
    
    def __init__(self, parent, config_dir='config'):
        self.parent = parent
        self.config_dir = config_dir
        self.basic_fields = {}
        self.city_values = set()
        self.month_values = set()
        self.create_tab()
    
    def create_tab(self):
        """创建基本配置页面"""
        basic_frame = ttk.Frame(self.parent)
        self.parent.add(basic_frame, text="基本配置")
        
        # 使用Canvas和Frame实现可滚动区域
        canvas = tk.Canvas(basic_frame)
        scrollbar = ttk.Scrollbar(basic_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind('<Enter>', _bind_to_mousewheel)
        canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # 加载城市和月份数据
        self._load_city_month_values()
        
        # 基本配置字段
        fields = [
            ('exhibition_code', '展会代码', '必需'),
            ('miniprogram_name', '小程序名称', '可选'),
            ('city', '城市', '可选，支持输入或选择'),
            ('month', '月份', '可选，支持输入或选择'),
            ('request_mode', '请求模式', '默认: single'),
            ('url', 'API地址', '必需'),
            ('request_method', '请求方法', '默认: POST'),
            ('headers', '请求头', '默认: {}'),
            ('params', 'URL参数', '可选'),
            ('data', '请求体', '可选'),
            ('items_key', '数据列表路径', '可选'),
            ('company_info_keys', '字段映射', '必需，JSON格式')
        ]
        
        for i, (field, label, hint) in enumerate(fields):
            # 标签
            ttk.Label(scrollable_frame, text=f"{label}:").grid(row=i*2, column=0, sticky=tk.W, pady=(5, 0), padx=(10, 0))
            ttk.Label(scrollable_frame, text=f"({hint})", font=('Arial', 8), foreground='gray').grid(row=i*2+1, column=0, sticky=tk.W, pady=(0, 5), padx=(10, 0))
            
            # 输入框
            if field in ['headers', 'params', 'data', 'company_info_keys']:
                # JSON编辑器
                json_editor = JSONEditor(scrollable_frame, label, height=120)
                json_editor.frame.grid(row=i*2, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 10), pady=5)
                self.basic_fields[field] = json_editor
            elif field == 'request_mode':
                # 下拉选择框
                combo = ttk.Combobox(scrollable_frame, values=['single', 'double'], state='readonly', width=57)
                combo.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.basic_fields[field] = combo
            elif field == 'request_method':
                # 下拉选择框
                combo = ttk.Combobox(scrollable_frame, values=['GET', 'POST'], state='readonly', width=57)
                combo.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.basic_fields[field] = combo
            elif field == 'city':
                # 城市：可输入可选择
                city_combo = ttk.Combobox(scrollable_frame, values=sorted(list(self.city_values)), width=57)
                city_combo.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.basic_fields[field] = city_combo
            elif field == 'month':
                # 月份：可输入可选择
                month_combo = ttk.Combobox(scrollable_frame, values=sorted(list(self.month_values)), width=57)
                month_combo.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.basic_fields[field] = month_combo
            else:
                # 单行文本框
                entry = ttk.Entry(scrollable_frame, width=60)
                entry.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.basic_fields[field] = entry
        
        # 配置网格权重
        scrollable_frame.columnconfigure(1, weight=1)
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        basic_frame.columnconfigure(0, weight=1)
        basic_frame.rowconfigure(0, weight=1)
    
    def set_default_values(self):
        """设置默认值"""
        self.basic_fields['request_mode'].set('single')
        self.basic_fields['request_method'].set('POST')
        self.basic_fields['headers'].set_json_string('{}')
        self.basic_fields['company_info_keys'].set_json_string('{}')
        
        # 聚焦到展会代码输入框
        self.basic_fields['exhibition_code'].focus()
    
    def get_fields(self):
        """获取字段字典"""
        return self.basic_fields
    
    def _load_city_month_values(self):
        """从所有配置文件中加载城市和月份值"""
        self.city_values = set()
        self.month_values = set()
        
        # 预定义一些常见的月份
        self.month_values.update(['1月', '2月', '3月', '4月', '5月', '6月', 
                                   '7月', '8月', '9月', '10月', '11月', '12月'])
        
        if not os.path.exists(self.config_dir):
            return
        
        try:
            for filename in os.listdir(self.config_dir):
                if filename.endswith('.json') and filename != 'index.json':
                    file_path = os.path.join(self.config_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        
                        # 收集城市
                        city = config.get('city')
                        if city and isinstance(city, str) and city.strip():
                            self.city_values.add(city.strip())
                        
                        # 收集月份
                        month = config.get('month')
                        if month and isinstance(month, str) and month.strip():
                            self.month_values.add(month.strip())
                            
                    except Exception:
                        continue
        except Exception:
            pass
    
    def refresh_city_month_values(self):
        """刷新城市和月份下拉列表的值"""
        self._load_city_month_values()
        
        if 'city' in self.basic_fields:
            self.basic_fields['city'].config(values=sorted(list(self.city_values)))
        if 'month' in self.basic_fields:
            self.basic_fields['month'].config(values=sorted(list(self.month_values)))
