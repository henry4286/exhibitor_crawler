"""
基本配置标签页模块

提供基本配置的界面组件
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from .json_editor import JSONEditor


class BasicConfigTab:
    """基本配置标签页"""
    
    def __init__(self, parent):
        self.parent = parent
        self.basic_fields = {}
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
        
        # 基本配置字段
        fields = [
            ('exhibition_code', '展会代码', '必需'),
            ('miniprogram_name', '小程序名称', '可选'),
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
