"""
二次请求配置标签页模块

提供二次请求配置的界面组件
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from .json_editor import JSONEditor


class AdvancedConfigTab:
    """二次请求配置标签页"""
    
    def __init__(self, parent):
        self.parent = parent
        self.advanced_fields = {}
        self.create_tab()
    
    def create_tab(self):
        """创建二次请求配置页面"""
        advanced_frame = ttk.Frame(self.parent)
        self.parent.add(advanced_frame, text="二次请求配置")
        
        # 使用Canvas和Frame实现可滚动区域
        canvas = tk.Canvas(advanced_frame)
        scrollbar = ttk.Scrollbar(advanced_frame, orient="vertical", command=canvas.yview)
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
        
        # 提示标签
        tip_label = ttk.Label(scrollable_frame, text="注意：仅在请求模式为 'double' 时需要配置以下字段", 
                              font=('Arial', 10, 'bold'), foreground='blue')
        tip_label.grid(row=0, column=0, columnspan=2, pady=(10, 20), padx=(10, 0))
        
        # 二次请求配置字段
        fields = [
            ('url_detail', '详情API地址', '支持#company_id占位符'),
            ('request_method_detail', '详情请求方法', 'GET/POST'),
            ('headers_detail', '详情请求头', 'JSON格式'),
            ('params_detail', '详情URL参数', 'JSON格式'),
            ('data_detail', '详情请求体', 'JSON格式'),
            ('items_key_detail', '详情数据路径', '例如: data.contacts'),
            ('info_key', '联系人字段映射', 'JSON格式'),
            ('company_name_key', '公司名称字段', '例如: companyName'),
            ('id_key', '公司ID字段', '例如: id')
        ]
        
        for i, (field, label, hint) in enumerate(fields, start=1):
            # 标签
            ttk.Label(scrollable_frame, text=f"{label}:").grid(row=i*2, column=0, sticky=tk.W, pady=(5, 0), padx=(10, 0))
            ttk.Label(scrollable_frame, text=f"({hint})", font=('Arial', 8), foreground='gray').grid(row=i*2+1, column=0, sticky=tk.W, pady=(0, 5), padx=(10, 0))
            
            # 输入框
            if field in ['headers_detail', 'params_detail', 'data_detail', 'info_key']:
                # JSON编辑器
                json_editor = JSONEditor(scrollable_frame, label, height=120)
                json_editor.frame.grid(row=i*2, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 10), pady=5)
                self.advanced_fields[field] = json_editor
            elif field == 'items_key_detail':
                # 单行文本框（详情数据路径是字符串）
                entry = ttk.Entry(scrollable_frame, width=60)
                entry.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.advanced_fields[field] = entry
            elif field == 'request_method_detail':
                # 下拉选择框
                combo = ttk.Combobox(scrollable_frame, values=['GET', 'POST'], state='readonly', width=57)
                combo.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.advanced_fields[field] = combo
            else:
                # 单行文本框
                entry = ttk.Entry(scrollable_frame, width=60)
                entry.grid(row=i*2, column=1, sticky=(tk.W, tk.E), padx=(10, 10), pady=5)
                self.advanced_fields[field] = entry
        
        # 配置网格权重
        scrollable_frame.columnconfigure(1, weight=1)
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        advanced_frame.columnconfigure(0, weight=1)
        advanced_frame.rowconfigure(0, weight=1)
    
    def set_default_values(self):
        """设置默认值"""
        # 设置详情请求方法默认为POST
        self.advanced_fields['request_method_detail'].set('POST')
    
    def get_fields(self):
        """获取字段字典"""
        return self.advanced_fields
