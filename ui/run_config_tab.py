"""
运行配置标签页模块

提供运行配置和日志显示的界面组件
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import datetime
import pandas as pd


class RunConfigTab:
    """运行配置标签页"""
    
    def __init__(self, parent, config_editor):
        self.parent = parent
        self.config_editor = config_editor
        self.is_running = False
        self.current_process = None
        self.create_tab()
    
    def create_tab(self):
        """创建运行配置页面"""
        run_frame = ttk.Frame(self.parent)
        self.parent.add(run_frame, text="运行配置")
        
        # 运行参数字段
        self.run_fields = {}
        
        # 当前展会代码显示
        current_frame = ttk.LabelFrame(run_frame, text="当前选中展会", padding="10")
        current_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=10, pady=10)
        
        ttk.Label(current_frame, text="展会代码:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.current_exhibition_label = ttk.Label(current_frame, text="未选择", font=('Arial', 10, 'bold'))
        self.current_exhibition_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(current_frame, text="请求模式:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.current_mode_label = ttk.Label(current_frame, text="未选择", font=('Arial', 10, 'bold'))
        self.current_mode_label.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        # 运行参数配置
        params_frame = ttk.LabelFrame(run_frame, text="运行参数", padding="10")
        params_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=10, pady=10)
        
        # 线程数配置
        ttk.Label(params_frame, text="并发线程数:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.workers_var = tk.StringVar(value="4")
        workers_spinbox = ttk.Spinbox(params_frame, from_=1, to=20, textvariable=self.workers_var, width=10)
        workers_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
        ttk.Label(params_frame, text="(默认: 4)", font=('Arial', 8), foreground='gray').grid(row=0, column=2, sticky=tk.W)
        
        # 起始页码配置
        ttk.Label(params_frame, text="起始页码:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(10, 0))
        self.start_page_var = tk.StringVar(value="1")
        start_page_spinbox = ttk.Spinbox(params_frame, from_=1, to=1000, textvariable=self.start_page_var, width=10)
        start_page_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        ttk.Label(params_frame, text="(默认: 1)", font=('Arial', 8), foreground='gray').grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        
        # 运行按钮
        button_frame = ttk.Frame(run_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="测试配置", command=self.test_config).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="运行爬虫", command=self.run_crawler, style='Accent.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="停止运行", command=self.stop_crawler).grid(row=0, column=2, padx=5)
        
        # 运行日志
        log_frame = ttk.LabelFrame(run_frame, text="运行日志", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        run_frame.columnconfigure(0, weight=1)
        run_frame.rowconfigure(3, weight=1)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, width=80, height=20)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清空日志按钮
        ttk.Button(log_frame, text="清空日志", command=self.clear_log).grid(row=1, column=0, pady=(5, 0))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
    
    def update_current_exhibition(self):
        """更新当前选中的展会信息"""
        current_row = self.config_editor.current_row
        df = self.config_editor.df
        
        if current_row is not None and df is not None:
            if current_row < len(df):
                row = df.iloc[current_row]
                exhibition_code = row.get('exhibition_code', '')
                request_mode = row.get('request_mode', 'single')
                
                self.current_exhibition_label.config(text=exhibition_code)
                self.current_mode_label.config(text=request_mode)
            else:
                self.current_exhibition_label.config(text="未选择")
                self.current_mode_label.config(text="未选择")
        else:
            self.current_exhibition_label.config(text="未选择")
            self.current_mode_label.config(text="未选择")
    
    def log_message(self, message):
        """添加日志消息 - 同时输出到UI和终端"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        
        # 输出到GUI日志窗口
        self.log_text.insert(tk.END, f"{log_line}\n")
        self.log_text.see(tk.END)
        self.config_editor.root.update_idletasks()
        
        # 同时输出到终端控制台
        print(log_line)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', tk.END)
    
    def run_crawler(self):
        """运行爬虫"""
        if self.is_running:
            self.config_editor.show_warning("爬虫正在运行中，请先停止当前运行")
            return
        
        current_row = self.config_editor.current_row
        df = self.config_editor.df
        
        if current_row is None or df is None:
            self.config_editor.show_warning("请先选择要运行的展会配置")
            return
        
        exhibition_code = df.iloc[current_row]['exhibition_code']
        
        # 验证参数
        try:
            workers = int(self.workers_var.get())
            if workers < 1 or workers > 20:
                self.config_editor.show_error("线程数必须在1-20之间")
                return
        except ValueError:
            self.config_editor.show_error("请输入有效的线程数")
            return
        
        try:
            start_page = int(self.start_page_var.get())
            if start_page < 1:
                self.config_editor.show_error("起始页码必须大于0")
                return
        except ValueError:
            self.config_editor.show_error("请输入有效的起始页码")
            return
        
        # 确认运行
        if not self.config_editor.ask_yesno("确认运行", 
                                           f"确定要运行展会 '{exhibition_code}' 的爬虫吗？\n"
                                           f"线程数: {workers}\n"
                                           f"起始页码: {start_page}"):
            return
        
        # 清空日志并初始化
        self.clear_log()
        self.log_message(f"正在初始化爬虫运行...")
        self.log_message(f"目标展会: {exhibition_code}")
        
        # 启动爬虫
        self.is_running = True
        self.log_message(f"开始运行爬虫: {exhibition_code}")
        self.log_message(f"线程数: {workers}, 起始页码: {start_page}")
        
        # 在新线程中运行爬虫
        def run_in_thread():
            try:
                # 构建命令
                cmd = [
                    'python', 'run_crawler.py', exhibition_code,
                    '--workers', str(workers),
                    '--start-page', str(start_page)
                ]
                
                self.log_message(f"执行命令: {' '.join(cmd)}")
                
                # 运行进程 - 修复编码问题
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,  # 单独捕获stderr，不合并到stdout
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                # 实时读取输出，过滤掉日志系统的内部错误
                in_logging_error = False
                while True:
                    if self.current_process and self.current_process.stdout:
                        output = self.current_process.stdout.readline()
                        if output == '' and self.current_process.poll() is not None:
                            break
                        if output:
                            line = output.strip()
                            
                            # 过滤日志系统错误（不显示在UI上）
                            if '--- Logging error ---' in line:
                                in_logging_error = True
                                continue
                            elif in_logging_error:
                                # 跳过日志错误的详细内容，直到遇到正常日志
                                if line.startswith('[') or line.startswith('🚀') or line.startswith('📄') or line.startswith('💾') or line.startswith('✅') or line.startswith('⚠️') or line.startswith('❌'):
                                    in_logging_error = False
                                    self.log_message(line)
                                continue
                            else:
                                self.log_message(line)
                    else:
                        break
                
                # 等待进程结束
                return_code = self.current_process.poll()
                
                if return_code == 0:
                    self.log_message("爬虫运行完成！")
                    self.config_editor.show_info(f"展会 '{exhibition_code}' 爬虫运行完成")
                else:
                    self.log_message(f"爬虫运行失败，返回码: {return_code}")
                    self.config_editor.show_error(f"展会 '{exhibition_code}' 爬虫运行失败")
                    
            except Exception as e:
                self.log_message(f"运行出错: {e}")
                self.config_editor.show_error(f"运行爬虫时出错: {e}")
            finally:
                self.is_running = False
                self.current_process = None
        
        # 启动线程
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
    
    def stop_crawler(self):
        """停止爬虫"""
        if not self.is_running:
            self.config_editor.show_info("当前没有运行的爬虫")
            return
        
        if self.current_process:
            try:
                self.current_process.terminate()
                self.log_message("正在停止爬虫...")
                
                # 等待进程结束
                try:
                    self.current_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.current_process.kill()
                    self.log_message("强制停止爬虫")
                
                self.log_message("爬虫已停止")
                self.config_editor.show_info("爬虫已停止")
                
            except Exception as e:
                self.log_message(f"停止爬虫时出错: {e}")
                self.config_editor.show_error(f"停止爬虫时出错: {e}")
            finally:
                self.is_running = False
                self.current_process = None
    
    def test_config(self):
        """测试配置"""
        if self.is_running:
            self.config_editor.show_warning("爬虫正在运行中，请先停止当前运行")
            return
        
        current_row = self.config_editor.current_row
        df = self.config_editor.df
        
        if current_row is None or df is None:
            self.config_editor.show_warning("请先选择要测试的展会配置")
            return
        
        exhibition_code = df.iloc[current_row]['exhibition_code']
        
        # 确认测试
        if not self.config_editor.ask_yesno("确认测试", 
                                           f"确定要测试展会 '{exhibition_code}' 的配置吗？"):
            return
        
        # 清空日志并初始化
        self.clear_log()
        self.log_message(f"正在初始化配置测试...")
        self.log_message(f"目标展会: {exhibition_code}")
        
        # 启动测试
        self.is_running = True
        self.log_message(f"开始测试配置: {exhibition_code}")
        self.log_message("=" * 60)
        
        # 在新线程中运行测试
        def test_in_thread():
            try:
                # 构建命令
                cmd = ['python', 'test_config.py', exhibition_code]
                
                self.log_message(f"执行命令: {' '.join(cmd)}")
                self.log_message("")
                
                # 运行进程
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,  # 单独捕获stderr，过滤日志错误
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                # 实时读取输出，过滤掉日志系统的内部错误
                in_logging_error = False
                while True:
                    if self.current_process and self.current_process.stdout:
                        output = self.current_process.stdout.readline()
                        if output == '' and self.current_process.poll() is not None:
                            break
                        if output:
                            line = output.rstrip()
                            
                            # 过滤日志系统错误（不显示在UI上）
                            if '--- Logging error ---' in line:
                                in_logging_error = True
                                continue
                            elif in_logging_error:
                                # 跳过日志错误的详细内容，直到遇到正常日志
                                if line.startswith('=') or line.startswith('✅') or line.startswith('❌') or line.startswith('测试') or line.startswith('配置'):
                                    in_logging_error = False
                                    self.log_message(line)
                                continue
                            else:
                                self.log_message(line)
                    else:
                        break
                
                # 等待进程结束
                return_code = self.current_process.poll()
                
                self.log_message("")
                self.log_message("=" * 60)
                
                if return_code == 0:
                    self.log_message("✅ 配置测试通过！")
                    self.config_editor.show_info(f"展会 '{exhibition_code}' 配置测试通过！\n可以开始运行爬虫了。")
                else:
                    self.log_message(f"❌ 配置测试失败，返回码: {return_code}")
                    self.config_editor.show_error(f"展会 '{exhibition_code}' 配置测试失败！\n请检查配置或API接口。")
                    
            except Exception as e:
                self.log_message(f"测试出错: {e}")
                self.config_editor.show_error(f"测试配置时出错: {e}")
            finally:
                self.is_running = False
                self.current_process = None
        
        # 启动线程
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
