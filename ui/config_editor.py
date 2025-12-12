"""
配置文件图形化编辑器主模块

提供配置文件的主要编辑功能 - JSON版本
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import traceback
import threading
from typing import Optional, Dict, Any, List

from .basic_config_tab import BasicConfigTab
from .advanced_config_tab import AdvancedConfigTab
from .run_config_tab import RunConfigTab

# 导入Gitee同步模块
from gitee_sync import GiteeSync

# 导入新的日志系统
from unified_logger import log_info, log_warning, log_error, log_exception, log_config_error, log_file_operation


class ConfigUIEditor:
    """配置文件图形化编辑器"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("爬虫配置文件编辑器")
        self.root.geometry("1200x800")
        
        # 配置文件目录
        self.config_dir = 'config'
        self.index_file = os.path.join(self.config_dir, 'index.json')
        
        # 数据存储
        self.config_files = {}  # 文件名到配置数据的映射
        self.current_file = None  # 当前编辑的文件名
        
        # 文件修改追踪标志
        self._file_modified = False
        self._local_config_hashes = {}  # 用于追踪文件变化
        
        # 初始化界面
        self.setup_ui()
        self.load_configs()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="wens")
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="爬虫配置文件编辑器", font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # 左侧：配置列表
        left_frame = ttk.LabelFrame(main_frame, text="配置列表", padding="5")
        left_frame.grid(row=1, column=0, sticky="wens", padx=(0, 5))
        
        # 搜索框
        search_frame = ttk.Frame(left_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 5))
        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        ttk.Button(search_frame, text="清除", command=self.clear_search, width=5).pack(side=tk.LEFT, padx=(5, 0))
        
        # 列表框
        self.listbox = tk.Listbox(left_frame, width=25)
        self.listbox.grid(row=1, column=0, sticky="wens", pady=(0, 5))
        self.listbox.bind('<<ListboxSelect>>', self.on_list_select)
        
        # 列表滚动条
        listbox_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.listbox.yview)
        listbox_scrollbar.grid(row=1, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=listbox_scrollbar.set)
        
        # 按钮框架
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="we", pady=(5, 0))
        
        ttk.Button(button_frame, text="新增", command=self.add_config).grid(row=0, column=0, padx=2)
        ttk.Button(button_frame, text="复制", command=self.copy_config).grid(row=0, column=1, padx=2)
        ttk.Button(button_frame, text="删除", command=self.delete_config).grid(row=0, column=2, padx=2)
        ttk.Button(button_frame, text="保存", command=self.save_config).grid(row=0, column=3, padx=2)
        ttk.Button(button_frame, text="同步", command=self.sync_config).grid(row=0, column=4, padx=2)
        
        # 配置左侧框架权重
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)
        
        # 存储过滤后的文件名列表
        self.filtered_files = []
        
        # 右侧：配置详情
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=1, sticky="wens")
        right_frame.columnconfigure(0, weight=1)
        
        # 创建Notebook用于分页
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.grid(row=0, column=0, sticky="wens")
        
        # 创建各个标签页
        self.basic_tab = BasicConfigTab(self.notebook)
        self.advanced_tab = AdvancedConfigTab(self.notebook)
        self.run_tab = RunConfigTab(self.notebook, self)
        
        # 获取字段字典
        self.basic_fields = self.basic_tab.get_fields()
        self.advanced_fields = self.advanced_tab.get_fields()
        
        # 右侧框架权重
        right_frame.rowconfigure(0, weight=1)
    
    def on_search_change(self, *args):
        """搜索框内容变化时触发"""
        self.update_listbox()
    
    def clear_search(self):
        """清除搜索框"""
        self.search_var.set('')
    
    def update_listbox(self, search_text: str = None):
        """更新列表框显示，支持搜索过滤"""
        if search_text is None:
            search_text = self.search_var.get().strip().lower()
        
        self.listbox.delete(0, tk.END)
        self.filtered_files = []
        
        if not self.config_files:
            return
        
        for filename, config_data in self.config_files.items():
            # 获取搜索字段
            exhibition_code = config_data.get('exhibition_code', '').lower()
            miniprogram_name = config_data.get('miniprogram_name', '').lower()
            url = config_data.get('url', '').lower()
            
            # 如果搜索文本为空，显示所有；否则匹配搜索条件
            if not search_text or (search_text in exhibition_code or 
                                    search_text in miniprogram_name or 
                                    search_text in url):
                display_text = f"{config_data['exhibition_code']} ({config_data.get('request_mode', 'single')})"
                self.listbox.insert(tk.END, display_text)
                self.filtered_files.append(filename)
    
    def load_configs(self):
        """加载所有JSON配置文件"""
        try:
            if not os.path.exists(self.config_dir):
                error_msg = f"配置目录不存在: {self.config_dir}"
                log_config_error(self.config_dir, error_msg)
                messagebox.showerror("错误", error_msg)
                return
            
            # 清空现有配置
            self.config_files.clear()
            
            # 加载所有JSON文件（除了index.json）
            for filename in os.listdir(self.config_dir):
                if filename.endswith('.json') and filename != 'index.json':
                    file_path = os.path.join(self.config_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        self.config_files[filename] = config_data
                        # 记录文件哈希
                        self._local_config_hashes[filename] = self._get_file_hash(file_path)
                    except Exception as e:
                        log_warning(f"加载配置文件失败 {filename}: {e}")
                        continue
            
            # 更新列表框
            self.update_listbox()
            
            # 清空输入框
            self.clear_fields()
            
            config_count = len(self.config_files)
            success_msg = f"已加载配置文件，共 {config_count} 个配置"
            log_info(success_msg, False)
            
        except Exception as e:
            error_msg = f"加载配置文件失败: {e}"
            log_exception(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def clear_fields(self):
        """清空所有输入框"""
        # 清空基本配置字段
        for field, widget in self.basic_fields.items():
            self._clear_widget(widget)
        
        # 清空二次请求配置字段
        for field, widget in self.advanced_fields.items():
            self._clear_widget(widget)
        
        self.current_file = None
    
    def _clear_widget(self, widget):
        """清空单个控件"""
        try:
            if hasattr(widget, 'set_json_string'):  # JSONEditor
                widget.set_json_string('')
            elif isinstance(widget, tk.Text) or hasattr(widget, 'tag_add'):  # Text widget
                widget.delete('1.0', tk.END)
            elif hasattr(widget, 'delete') and hasattr(widget, 'insert'):  # Entry widget
                widget.delete(0, tk.END)
            elif hasattr(widget, 'set'):  # Combobox or other settable widget
                widget.set('')
        except Exception as e:
            log_warning(f"清空控件时发生错误: {e}")
    
    def on_list_select(self, event):
        """列表选择事件处理"""
        selection = self.listbox.curselection()
        if not selection:
            return
        
        listbox_index = selection[0]
        if not self.filtered_files or listbox_index >= len(self.filtered_files):
            return
        
        # 获取选中的文件名
        filename = self.filtered_files[listbox_index]
        if filename not in self.config_files:
            return
        
        config_data = self.config_files[filename]
        self.current_file = filename
        
        # 填充基本配置字段
        self._fill_fields(self.basic_fields, config_data)
        
        # 填充二次请求配置字段
        self._fill_fields(self.advanced_fields, config_data)
        
        # 更新运行配置页面的当前展会信息
        self.run_tab.update_current_exhibition()
    
    def _fill_fields(self, fields_dict, config_data):
        """填充字段数据"""
        for field, widget in fields_dict.items():
            value = config_data.get(field, '')
            self._set_widget_value(widget, value)
    
    def _set_widget_value(self, widget, value):
        """设置控件的值"""
        try:
            if hasattr(widget, 'set_json_string'):  # JSONEditor
                if isinstance(value, (dict, list)):
                    # 对于复杂数据类型，使用JSON格式
                    widget.set_json_string(json.dumps(value, ensure_ascii=False, indent=2))
                else:
                    widget.set_json_string(str(value) if value else '')
            elif isinstance(widget, tk.Text) or hasattr(widget, 'tag_add'):  # Text widget
                widget.delete('1.0', tk.END)
                widget.insert('1.0', str(value) if value else '')
            elif isinstance(widget, ttk.Combobox):  # Combobox
                values = widget.cget('values')
                value_str = str(value).strip() if value else ''
                
                if value_str and value_str in values:
                    widget.set(value_str)
                elif values:
                    widget.set(values[0])
                else:
                    widget.set('')
            elif hasattr(widget, 'delete') and hasattr(widget, 'insert'):  # Entry widget
                widget.delete(0, tk.END)
                widget.insert(0, str(value) if value else '')
            elif hasattr(widget, 'set'):  # Other settable widget
                widget.set(str(value) if value else '')
        except Exception as e:
            log_warning(f"设置控件值时发生错误: {e}")
    
    def get_field_value(self, widget):
        """获取字段值"""
        try:
            if hasattr(widget, 'get_json_string'):  # JSONEditor
                value = widget.get_json_string()
                if not value or not value.strip():
                    return {}
                # 尝试解析为JSON，如果失败则返回原始字符串
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            elif isinstance(widget, tk.Text) or hasattr(widget, 'tag_add'):  # Text widget
                value = widget.get('1.0', tk.END).strip()
                return value if value.strip() else None
            elif hasattr(widget, 'get'):  # Entry, Combobox, etc.
                value = widget.get()
                return value if value.strip() else None
            else:
                return None
        except Exception as e:
            log_warning(f"获取控件值时发生错误: {e}")
            return None
    
    def validate_json(self, json_data):
        """验证JSON格式"""
        if not json_data:
            return True, ""
        
        # 如果已经是字典或列表，说明是有效的
        if isinstance(json_data, (dict, list)):
            return True, ""
        
        # 如果是字符串，尝试解析
        if isinstance(json_data, str):
            if not json_data.strip():
                return True, ""
            try:
                json.loads(json_data)
                return True, ""
            except json.JSONDecodeError as e:
                return False, str(e)
        
        # 其他类型认为无效
        return False, f"无效的JSON数据类型: {type(json_data)}"
    
    def validate_config(self):
        """验证配置"""
        # 获取展会代码
        exhibition_code = self.get_field_value(self.basic_fields['exhibition_code'])
        if not exhibition_code:
            return False, "展会代码不能为空"
        
        # 检查展会代码是否重复（新增时）
        filename = f"{exhibition_code}.json"
        if self.current_file is None and filename in self.config_files:
            return False, f"展会代码 '{exhibition_code}' 已存在"
        
        # 获取URL
        url = self.get_field_value(self.basic_fields['url'])
        if not url:
            return False, "API地址不能为空"
        
        # 验证JSON字段
        json_fields = ['headers', 'params', 'data', 'company_info_keys']
        for field in json_fields:
            value = self.get_field_value(self.basic_fields[field])
            if value:
                is_valid, error = self.validate_json(value)
                if not is_valid:
                    return False, f"字段 '{field}' 的JSON格式错误: {error}"
        
        # 如果是double模式，验证二次请求字段
        request_mode = self.get_field_value(self.basic_fields['request_mode'])
        if request_mode == 'double':
            url_detail = self.get_field_value(self.advanced_fields['url_detail'])
            if not url_detail:
                return False, "二次请求模式下，详情API地址不能为空"
            
            company_info_keys_value = self.get_field_value(self.basic_fields['company_info_keys'])
            if company_info_keys_value:
                try:
                    company_info_keys = json.loads(company_info_keys_value)
                    if 'ID' not in company_info_keys:
                        return False, "二次请求模式下，基本配置的字段映射中必须包含'ID'字段"
                    if 'Company' not in company_info_keys:
                        return False, "二次请求模式下，基本配置的字段映射中必须包含'Company'字段"
                except json.JSONDecodeError:
                    return False, "基本配置的字段映射JSON格式错误"
            
            # 验证二次请求的JSON字段
            json_fields = ['headers_detail', 'params_detail', 'data_detail', 'info_key']
            for field in json_fields:
                value = self.get_field_value(self.advanced_fields[field])
                if value:
                    is_valid, error = self.validate_json(value)
                    if not is_valid:
                        return False, f"二次请求字段 '{field}' 的JSON格式错误: {error}"
        
        return True, ""
    
    def add_config(self):
        """新增配置"""
        # 清空输入框
        self.clear_fields()
        
        # 设置默认值
        self.basic_tab.set_default_values()
        self.advanced_tab.set_default_values()
        
        # 设置当前文件为None，表示新增
        self.current_file = None
        
        self.show_info("请填写配置信息，然后点击保存")
    
    def copy_config(self):
        """复制配置"""
        selection = self.listbox.curselection()
        if not selection:
            self.show_warning("请先选择要复制的配置")
            return
        
        listbox_index = selection[0]
        if not self.filtered_files or listbox_index >= len(self.filtered_files):
            return
        
        filename = self.filtered_files[listbox_index]
        if filename not in self.config_files:
            return
        
        # 获取选中的配置数据
        config_data = self.config_files[filename]
        original_code = config_data['exhibition_code']
        
        # 填充所有字段
        self._fill_fields(self.basic_fields, config_data)
        self._fill_fields(self.advanced_fields, config_data)
        
        # 清空展会代码
        exhibition_code_widget = self.basic_fields.get('exhibition_code')
        if exhibition_code_widget:
            self._clear_widget(exhibition_code_widget)
            suggested_code = f"{original_code}_copy"
            if hasattr(exhibition_code_widget, 'insert'):
                exhibition_code_widget.insert(0, suggested_code)
        
        # 设置当前文件为None，表示新增
        self.current_file = None
        
        self.show_info(f"已复制展会 '{original_code}' 的配置，请修改展会代码后保存")
    
    def delete_config(self):
        """删除配置"""
        selection = self.listbox.curselection()
        if not selection:
            self.show_warning("请先选择要删除的配置")
            return
        
        listbox_index = selection[0]
        if not self.filtered_files or listbox_index >= len(self.filtered_files):
            return
        
        filename = self.filtered_files[listbox_index]
        if filename not in self.config_files:
            return
        
        exhibition_code = self.config_files[filename]['exhibition_code']
        
        if self.ask_yesno("确认", f"确定要删除展会 '{exhibition_code}' 的配置吗？"):
            # 删除文件
            file_path = os.path.join(self.config_dir, filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    log_file_operation("删除", file_path, success=True)
                
                # 从内存中删除
                del self.config_files[filename]
                if filename in self._local_config_hashes:
                    del self._local_config_hashes[filename]
                
                # 标记文件已被修改
                self._file_modified = True
                
                # 重新加载配置列表
                self.load_configs()
                self.show_info(f"已删除展会 '{exhibition_code}' 的配置")
                
            except Exception as e:
                error_msg = f"删除配置文件失败: {e}"
                log_file_operation("删除", file_path, success=False, error=error_msg)
                self.show_error(error_msg)
    
    def save_config(self):
        """保存配置"""
        # 验证配置
        is_valid, error = self.validate_config()
        if not is_valid:
            self.show_error(f"验证失败: {error}")
            return
        
        try:
            # 收集基本配置数据
            basic_data = {}
            for field, widget in self.basic_fields.items():
                basic_data[field] = self.get_field_value(widget)
            
            # 收集二次请求数据
            advanced_data = {}
            for field, widget in self.advanced_fields.items():
                advanced_data[field] = self.get_field_value(widget)
            
            # 设置默认值
            if not basic_data.get('request_mode'):
                basic_data['request_mode'] = 'single'
            if not basic_data.get('request_method'):
                basic_data['request_method'] = 'POST'
            
            # 合并数据
            config_data = {**basic_data, **advanced_data}
            
            # 生成文件名
            exhibition_code = config_data['exhibition_code']
            filename = f"{exhibition_code}.json"
            file_path = os.path.join(self.config_dir, filename)
            
            # 检查是否修改了展会代码
            old_filename = self.current_file
            if old_filename and old_filename != filename:
                # 如果展会代码改变了，删除旧文件
                old_file_path = os.path.join(self.config_dir, old_filename)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                    log_file_operation("删除", old_file_path, success=True)
                    # 从内存中删除旧配置
                    if old_filename in self.config_files:
                        del self.config_files[old_filename]
                    if old_filename in self._local_config_hashes:
                        del self._local_config_hashes[old_filename]
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            log_file_operation("保存", file_path, success=True)
            
            # 更新内存中的配置
            self.config_files[filename] = config_data
            self._local_config_hashes[filename] = self._get_file_hash(file_path)
            
            # 更新当前文件
            self.current_file = filename
            
            # 标记文件已被修改
            self._file_modified = True
            
            # 重新加载配置列表
            self.load_configs()
            
            # 重新选择当前编辑的配置
            if filename in self.filtered_files:
                index = self.filtered_files.index(filename)
                self.listbox.selection_set(index)
                self.on_list_select(None)
            
            action = "修改" if old_filename else "新增"
            self.show_info(f"已{action}展会 '{exhibition_code}' 的配置")
            
        except Exception as e:
            error_msg = f"保存配置失败: {e}"
            log_exception(error_msg)
            self.show_error(error_msg)
    
    def sync_config(self):
        """同步配置文件"""
        # 弹出确认对话框
        if not self.ask_yesno("确认同步", "确定要从Gitee仓库同步最新的配置文件吗？\n\n这将覆盖本地的配置文件。"):
            return
        
        # 显示同步提示
        self.show_info("正在同步配置文件，请稍候...")
        
        # 在后台线程中执行同步操作
        def sync_worker():
            try:
                log_info("开始同步配置文件...")
                
                # 创建Gitee同步管理器
                sync_manager = GiteeSync()
                
                # 执行同步
                success, message = sync_manager.pull_configs()
                
                # 在主线程中更新UI
                self.root.after(0, lambda: self._sync_complete(success, message))
                
            except Exception as e:
                log_exception(f"同步时发生错误: {e}")
                # 在主线程中显示错误
                self.root.after(0, lambda: self._sync_error(str(e)))
        
        # 启动后台线程
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
    
    def _sync_complete(self, success: bool, message: str):
        """同步完成后的UI更新"""
        try:
            if success:
                log_info(f"同步成功: {message}")
                self.show_info(f"同步成功！\n{message}")
                # 重新加载配置文件
                self.load_configs()
                # 同步成功后，重置修改标志
                self._file_modified = False
            else:
                log_error(f"同步失败: {message}")
                self.show_error(f"同步失败：\n{message}")
                # 即使同步失败，也要尝试重新加载本地配置
                self.load_configs()
        except Exception as e:
            log_exception(f"更新UI时发生错误: {e}")
            self.show_error(f"更新UI时发生错误：\n{e}")
    
    def _sync_error(self, error_msg: str):
        """同步错误处理"""
        try:
            self.show_error(f"同步时发生错误：\n{error_msg}")
            # 尝试重新加载本地配置
            try:
                self.load_configs()
            except:
                pass
        except Exception as e:
            log_exception(f"处理同步错误时发生异常: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """计算文件的MD5哈希值"""
        try:
            import hashlib
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            log_warning(f"计算文件哈希失败: {e}")
            return ""
    
    def _check_files_modified(self) -> bool:
        """检查配置文件是否有外部修改"""
        try:
            for filename, original_hash in self._local_config_hashes.items():
                file_path = os.path.join(self.config_dir, filename)
                if os.path.exists(file_path):
                    current_hash = self._get_file_hash(file_path)
                    if current_hash != original_hash:
                        return True
            return False
        except Exception as e:
            log_warning(f"检查文件修改状态失败: {e}")
            return False
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 检查是否有未保存的修改或外部文件修改
        has_unsaved = self._file_modified or self._check_files_modified()
        
        if has_unsaved:
            # 弹出对话框询问是否推送
            result = messagebox.askyesnocancel(
                "未保存的修改",
                "检测到配置文件有修改。\n\n是否推送到Gitee仓库？\n（是=推送，否=不推送，取消=取消关闭）"
            )
            
            if result is None:
                # 用户选择取消，不关闭窗口
                return
            elif result is True:
                # 用户选择推送，执行推送操作
                self._push_and_close()
                return
            # 否则直接关闭（不推送）
        
        # 没有修改或用户选择不推送，直接关闭
        self.root.destroy()
    
    def _push_and_close(self):
        """推送配置并关闭应用"""
        # 在后台线程执行推送操作，避免阻塞 UI
        def push_worker():
            try:
                log_info("开始推送配置文件...")
                
                # 创建Gitee同步管理器
                sync_manager = GiteeSync()
                
                # 执行推送
                success, message = sync_manager.push_configs()
                
                # 在主线程中更新 UI 并关闭
                self.root.after(0, lambda: self._push_complete(success, message))
                
            except Exception as e:
                log_exception(f"推送时发生错误: {e}")
                self.root.after(0, lambda: self._push_error(str(e)))
        
        # 启动后台线程
        push_thread = threading.Thread(target=push_worker, daemon=True)
        push_thread.start()
        
        # 显示推送提示
        self.show_info("正在推送配置文件，请稍候...")
    
    def _push_complete(self, success: bool, message: str):
        """推送完成后处理"""
        if success:
            log_info(f"推送成功: {message}")
            messagebox.showinfo("推送成功", f"配置文件已成功推送到Gitee仓库。\n\n{message}")
            # 更新文件哈希，标记为已同步
            for filename in self.config_files:
                file_path = os.path.join(self.config_dir, filename)
                self._local_config_hashes[filename] = self._get_file_hash(file_path)
            self._file_modified = False
        else:
            log_error(f"推送失败: {message}")
            # 推送失败，询问是否仍然关闭
            if messagebox.askyesno("推送失败", f"推送失败：{message}\n\n仍然关闭应用吗？"):
                pass
            else:
                # 用户选择不关闭，返回
                return
        
        # 关闭应用
        self.root.destroy()
    
    def _push_error(self, error_msg: str):
        """推送错误处理"""
        log_error(f"推送时发生错误: {error_msg}")
        if messagebox.askyesno("推送错误", f"推送时发生错误：{error_msg}\n\n仍然关闭应用吗？"):
            pass
        else:
            return
        
        # 关闭应用
        self.root.destroy()
                
    
    # 消息框方法的简化版本（带日志记录）
    def show_info(self, message):
        log_info(f"信息: {message}", False)
        messagebox.showinfo("提示", message)
    
    def show_warning(self, message):
        log_warning(f"警告: {message}", False)
        messagebox.showwarning("警告", message)
    
    def show_error(self, message):
        log_error(f"错误: {message}", ui=False)
        messagebox.showerror("错误", message)
    
    def ask_yesno(self, title, message):
        log_info(f"询问 ({title}): {message}", ui=False)
        return messagebox.askyesno(title, message)
    
    def ask_okcancel(self, title, message):
        log_info(f"询问 ({title}): {message}", ui=False)
        return messagebox.askokcancel(title, message)
    
    def run(self):
        """运行应用"""
        self.root.mainloop()
