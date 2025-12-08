"""
JSON键值对编辑器模块

提供JSON数据的图形化编辑功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from typing import Optional, Dict, Any, List


class JSONEditor:
    """JSON键值对编辑器"""
    
    def __init__(self, parent, title="JSON编辑器", height=200):
        self.parent = parent
        self.title = title
        self.height = height
        self.data = {}
        
        # 创建主框架
        self.frame = ttk.LabelFrame(parent, text=title, padding="5")
        
        # 创建工具栏
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar, text="添加键值对", command=self.add_pair).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="删除选中", command=self.delete_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="清空全部", command=self.clear_all).pack(side=tk.LEFT, padx=(0, 5))
        
        # 创建Treeview用于显示键值对
        columns = ('key', 'value', 'type')
        self.tree = ttk.Treeview(self.frame, columns=columns, show='tree headings', height=8)
        
        # 设置列标题
        self.tree.heading('#0', text='序号')
        self.tree.heading('key', text='Key')
        self.tree.heading('value', text='Value')
        self.tree.heading('type', text='类型')
        
        # 设置列宽
        self.tree.column('#0', width=50)
        self.tree.column('key', width=150)
        self.tree.column('value', width=200)
        self.tree.column('type', width=80)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定双击事件用于编辑
        self.tree.bind('<Double-1>', self.on_double_click)
        
        # 创建编辑对话框的变量
        self.edit_dialog = None
    
    def add_pair(self):
        """添加新的键值对"""
        def on_dialog_close(result):
            if result:
                key, value, value_type = result
                self.add_key_value(key, value, value_type)
        
        # 获取顶层窗口以确保对话框正确居中
        root_window = self.parent.winfo_toplevel()
        dialog = KeyValueDialog(root_window, "添加键值对", callback=on_dialog_close)
        # 不使用wait_window避免阻塞
    
    def add_key_value(self, key, value, value_type='string'):
        """添加键值对到列表"""
        # 检查key是否已存在
        for item in self.tree.get_children():
            if self.tree.item(item)['values'][0] == key:
                messagebox.showwarning("警告", f"Key '{key}' 已存在")
                return
        
        # 对于string类型，直接保存原始字符串，不进行类型转换
        if value_type != 'string':
            # 类型转换
            if value_type == 'number':
                try:
                    value = float(value) if '.' in value else int(value)
                except ValueError.showerror("错误:
                    messagebox", f"'{value}' 不是有效的数字")
                    return
            elif value_type == 'boolean':
                value = value.lower() in ('true', '1', 'yes', 'on')
            elif value_type == 'json' or value_type == 'dict':
                try:
                    parsed_value = json.loads(value)
                    # dict类型只接受字典，json类型可以接受字典或数组
                    if value_type == 'dict' and not isinstance(parsed_value, dict):
                        messagebox.showerror("错误", "dict类型必须是对象格式")
                        return
                except json.JSONDecodeError as e:
                    messagebox.showerror("错误", f"JSON格式错误: {e}")
                    return
        
        # 修复：对于复杂数据类型（列表、字典），将其转换为JSON字符串显示
        if isinstance(value, (list, dict)):
            display_value = json.dumps(value, ensure_ascii=False, indent=None)
        else:
            display_value = str(value)
        
        # 添加到树形控件
        item_id = self.tree.insert('', 'end', text=str(len(self.tree.get_children()) + 1),
                                   values=(key, display_value, value_type))
        
        # 更新数据 - 如果是string类型，直接保存字符串，否则进行类型转换
        if value_type == 'string':
            self.data[key] = value
        else:
            self.data[key] = self._convert_value(value, value_type)
    
    def delete_selected(self):
        """删除选中的键值对"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的项")
            return
        
        for item in selection:
            key = self.tree.item(item)['values'][0]
            # 安全删除，避免KeyError
            if key in self.data:
                del self.data[key]
            self.tree.delete(item)
        
        # 重新编号
        self._renumber()
    
    def clear_all(self):
        """清空所有键值对"""
        if messagebox.askyesno("确认", "确定要清空所有键值对吗？"):
            self.tree.delete(*self.tree.get_children())
            self.data.clear()
    
    def on_double_click(self, event):
        """双击编辑"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        key, value, value_type = self.tree.item(item)['values']
        
        # 获取顶层窗口以确保对话框正确居中
        root_window = self.parent.winfo_toplevel()
        dialog = KeyValueDialog(root_window, "编辑键值对", key, value, value_type)
        root_window.wait_window(dialog.dialog)
        
        if dialog.result:
            new_key, new_value, new_type = dialog.result
            
            # 如果key改变了，删除旧的
            if new_key != key:
                del self.data[key]
            
            # 修复：对于复杂数据类型，重新格式化显示
            if isinstance(new_value, (list, dict)):
                display_value = json.dumps(new_value, ensure_ascii=False, indent=None)
            else:
                display_value = str(new_value)
            
            # 更新树形控件
            self.tree.item(item, values=(new_key, display_value, new_type))
            
            # 更新数据
            self.data[new_key] = self._convert_value(new_value, new_type)
    
    def _convert_value(self, value, value_type):
        """根据类型转换值"""
        if value_type == 'number':
            try:
                # 如果value已经是数字类型，直接返回
                if isinstance(value, (int, float)):
                    return value
                # 如果是字符串，检查是否包含小数点
                if isinstance(value, str) and '.' in value:
                    return float(value)
                else:
                    return int(value)
            except (ValueError, TypeError):
                return value
        elif value_type == 'boolean':
            if isinstance(value, bool):
                return value
            return str(value).lower() in ('true', '1', 'yes', 'on')
        elif value_type == 'json' or value_type == 'dict':
            if isinstance(value, (dict, list)):
                return value
            try:
                return json.loads(str(value))
            except (json.JSONDecodeError, TypeError):
                return value
        else:
            return value
    
    def _renumber(self):
        """重新编号"""
        for i, item in enumerate(self.tree.get_children(), 1):
            self.tree.item(item, text=str(i))
    
    def get_json_string(self):
        """获取JSON字符串"""
        # 确保数据同步：从tree重新构建data
        self.data = {}
        for item in self.tree.get_children():
            key, value, value_type = self.tree.item(item)['values']
            # 如果类型是string，直接保存为字符串，不要进行类型转换
            if value_type == 'string':
                self.data[key] = str(value)  # 确保是字符串
            else:
                self.data[key] = self._convert_value(value, value_type)
        
        if not self.data:
            return ""
        
        # 直接使用json.dumps，确保字符串被正确序列化
        result = json.dumps(self.data, ensure_ascii=False, indent=2)
        print(f"JSON输出: {result}")  # 调试输出
        return result
    
    def set_json_string(self, json_str):
        """从JSON字符串设置数据"""
        self.tree.delete(*self.tree.get_children())
        self.data.clear()
        
        if not json_str.strip():
            return
        
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                for key, value in data.items():
                    value_type = self._get_value_type(value)
                    # 修复：对于复杂数据类型，直接传递原始值而不是转换为字符串
                    self.add_key_value(key, value, value_type)
            else:
                messagebox.showerror("错误", "JSON必须是对象格式")
        except json.JSONDecodeError as e:
            messagebox.showerror("错误", f"JSON格式错误: {e}")
    
    def _get_value_type(self, value):
        """获取值的类型"""
        if isinstance(value, bool):
            return 'boolean'
        elif isinstance(value, (int, float)):
            return 'number'
        elif isinstance(value, (dict, list)):
            return 'json'
        else:
            return 'string'
    
    def pack(self, **kwargs):
        """包装pack方法"""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """包装grid方法"""
        self.frame.grid(**kwargs)


class KeyValueDialog:
    """键值对编辑对话框"""
    
    def __init__(self, parent, title, key="", value="", value_type="string", callback=None):
        self.result = None
        self.callback = callback
        self.dict_value = {}  # 存储字典类型的值
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        # 移除grab_set()避免阻塞主界面
        # self.dialog.grab_set()
        
        # 保存parent引用，用于后续居中定位
        self.parent = parent
        
        # 创建界面
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Key下拉选择（预定义字段）
        ttk.Label(main_frame, text="Key:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        self.key_var = tk.StringVar(value=key)
        key_combo = ttk.Combobox(main_frame, textvariable=self.key_var, width=37)
        key_combo['values'] = ('Company', 'Contacts', 'Job', 'Telephone', 'Phone', 
                                'Email', 'BoothArea', 'BoothNumber', 'WebSite', 'Mobile')
        key_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 10))
        self.key_entry = key_combo  # 保持变量名一致，方便后续代码使用
        
        # Value类型选择
        ttk.Label(main_frame, text="类型:").grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        self.type_var = tk.StringVar(value=value_type)
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, 
                                  values=['string', 'number', 'boolean', 'json', 'dict'], 
                                  state='readonly', width=37)
        type_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 10))
        type_combo.bind('<<ComboboxSelected>>', self.on_type_changed)
        
        # Value输入框架
        self.value_frame = ttk.Frame(main_frame)
        self.value_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Value标签和快速插入按钮在同一行
        value_label_frame = ttk.Frame(self.value_frame)
        value_label_frame.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        ttk.Label(value_label_frame, text="Value:").pack(side=tk.LEFT)
        ttk.Label(value_label_frame, text="快速插入:", font=('Arial', 9)).pack(side=tk.LEFT, padx=(10, 5))
        ttk.Button(value_label_frame, text="{page}", 
                  command=lambda: self.insert_text("{page}")).pack(side=tk.LEFT, padx=2)
        ttk.Button(value_label_frame, text="#company_id", 
                  command=lambda: self.insert_text("#company_id")).pack(side=tk.LEFT, padx=2)
        
        # Value输入文本框
        self.value_text = scrolledtext.ScrolledText(self.value_frame, width=40, height=6)
        self.value_text.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.value_text.insert('1.0', value)
        
        # 字典编辑按钮（初始隐藏）
        self.dict_button_frame = ttk.Frame(self.value_frame)
        
        # 帮助文本
        self.help_label = ttk.Label(main_frame, text="", font=('Arial', 8), foreground='gray')
        self.help_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(button_frame, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=self.on_cancel).pack(side=tk.LEFT)
        
        # 配置网格权重
        main_frame.columnconfigure(1, weight=1)
        self.value_frame.columnconfigure(0, weight=1)
        
        # 更新帮助文本
        self.on_type_changed()
        
        # 绑定回车键
        self.dialog.bind('<Return>', lambda e: self.on_ok())
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())
        
        # 绑定窗口关闭事件
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        # 立即更新窗口并居中显示
        self.dialog.update_idletasks()
        # 设置合适的窗口大小
        self.dialog.geometry("400x300")
        # 居中显示
        self._center_dialog()
        
        # 聚焦到key输入框
        if not key:
            self.key_entry.focus()
        else:
            self.value_text.focus()
    
    def _center_dialog(self):
        """相对于父窗口居中显示对话框"""
        # 确保窗口已经更新
        self.dialog.update_idletasks()
        
        # 获取对话框的尺寸
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        
        # 获取父窗口的位置和大小
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # 计算相对于父窗口的居中位置
        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)
        
        # 设置对话框位置
        self.dialog.geometry(f"+{x}+{y}")
    
    def insert_text(self, text):
        """在文本框中插入文本"""
        self.value_text.insert(tk.INSERT, text)
        self.value_text.focus_set()
    
    def on_type_changed(self, event=None):
        """类型改变时的处理"""
        value_type = self.type_var.get()
        help_texts = {
            'string': '输入字符串值',
            'number': '输入数字（整数或小数）',
            'boolean': '输入 true/false, 1/0, yes/no, on/off',
            'json': '输入有效的JSON格式数据',
            'dict': '点击编辑按钮打开字典编辑器创建嵌套对象'
        }
        self.help_label.config(text=help_texts.get(value_type, ''))
        
        # 如果是字典类型，显示编辑按钮
        if value_type == 'dict':
            self.show_dict_editor_button()
        else:
            self.hide_dict_editor_button()
    
    def show_dict_editor_button(self):
        """显示字典编辑按钮"""
        # 隐藏文本输入框
        self.value_text.grid_remove()
        
        # 显示字典编辑按钮
        self.dict_button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 清空并重新创建按钮
        for widget in self.dict_button_frame.winfo_children():
            widget.destroy()
        
        ttk.Button(self.dict_button_frame, text="编辑字典内容", 
                  command=self.open_dict_editor).pack(side=tk.LEFT, padx=(0, 5))
        
        # 显示当前字典内容的预览
        if self.dict_value:
            preview = json.dumps(self.dict_value, ensure_ascii=False, indent=2)
            preview_label = ttk.Label(self.dict_button_frame, 
                                    text=f"当前内容: {preview[:50]}..." if len(preview) > 50 else f"当前内容: {preview}",
                                    font=('Arial', 8), foreground='blue')
            preview_label.pack(side=tk.LEFT, padx=(10, 0))
    
    def hide_dict_editor_button(self):
        """隐藏字典编辑按钮"""
        # 显示文本输入框
        self.value_text.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 隐藏字典编辑按钮
        self.dict_button_frame.grid_remove()
    
    def open_dict_editor(self):
        """打开字典编辑器"""
        # 创建一个嵌套的JSON编辑器对话框
        dict_dialog = tk.Toplevel(self.dialog)
        dict_dialog.title("字典内容编辑器")
        dict_dialog.geometry("500x400")
        dict_dialog.resizable(True, True)
        dict_dialog.transient(self.dialog)
        dict_dialog.grab_set()
        
        # 创建编辑器
        editor_frame = ttk.Frame(dict_dialog, padding="10")
        editor_frame.pack(fill=tk.BOTH, expand=True)
        
        # 使用JSONEditor来编辑字典内容
        dict_editor = JSONEditor(editor_frame, "字典内容", height=15)
        dict_editor.pack(fill=tk.BOTH, expand=True)
        
        # 如果已有字典内容，加载到编辑器
        if self.dict_value:
            dict_editor.set_json_string(json.dumps(self.dict_value, ensure_ascii=False, indent=2))
        
        # 按钮框架
        button_frame = ttk.Frame(dict_dialog)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def on_save():
            """保存字典内容"""
            json_str = dict_editor.get_json_string()
            if json_str.strip():
                try:
                    self.dict_value = json.loads(json_str)
                    messagebox.showinfo("成功", "字典内容已保存")
                    dict_dialog.destroy()
                    # 更新按钮显示
                    self.show_dict_editor_button()
                except json.JSONDecodeError as e:
                    messagebox.showerror("错误", f"JSON格式错误: {e}")
            else:
                self.dict_value = {}
                messagebox.showinfo("成功", "字典内容已清空")
                dict_dialog.destroy()
                self.show_dict_editor_button()
        
        def on_cancel():
            """取消编辑"""
            dict_dialog.destroy()
        
        ttk.Button(button_frame, text="保存", command=on_save).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.RIGHT)
        
        # 相对于主对话框居中显示
        dict_dialog.update_idletasks()
        width = dict_dialog.winfo_width()
        height = dict_dialog.winfo_height()
        
        # 获取主对话框的位置和大小
        main_x = self.dialog.winfo_x()
        main_y = self.dialog.winfo_y()
        main_width = self.dialog.winfo_width()
        main_height = self.dialog.winfo_height()
        
        # 计算相对于主对话框的居中位置
        x = main_x + (main_width // 2) - (width // 2)
        y = main_y + (main_height // 2) - (height // 2)
        
        dict_dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    def on_ok(self):
        """确定按钮处理"""
        key = self.key_entry.get().strip()
        value_type = self.type_var.get()
        
        if not key:
            messagebox.showerror("错误", "Key不能为空")
            return
        
        # 根据类型获取值
        if value_type == 'dict':
            # 字典类型使用dict_value
            if not self.dict_value:
                messagebox.showerror("错误", "请点击编辑按钮设置字典内容")
                return
            value = json.dumps(self.dict_value, ensure_ascii=False, indent=2)
        else:
            # 其他类型使用文本框内容
            value = self.value_text.get('1.0', tk.END).strip()
            # 允许值为空，只需要key不为空即可
            # if not value:
            #     messagebox.showerror("错误", "Value不能为空")
            #     return
        
        # 验证值格式
        if value_type == 'number':
            try:
                float(value) if '.' in value else int(value)
            except ValueError:
                messagebox.showerror("错误", f"'{value}' 不是有效的数字")
                return
        elif value_type == 'boolean':
            if value.lower() not in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
                messagebox.showerror("错误", "布尔值必须是: true/false, 1/0, yes/no, on/off")
                return
        elif value_type == 'json':
            try:
                json.loads(value)
            except json.JSONDecodeError as e:
                messagebox.showerror("错误", f"JSON格式错误: {e}")
                return
        
        self.result = (key, value, value_type)
        if self.callback:
            self.callback(self.result)
        self.dialog.destroy()
    
    def on_cancel(self):
        """取消按钮处理"""
        self.dialog.destroy()
