"""
运行配置标签页模块

提供运行配置和日志显示的界面组件
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import datetime

# 导入日志系统
from unified_logger import get_logger


class RunConfigTab:
    """运行配置标签页"""
    
    def __init__(self, parent, config_editor):
        self.parent = parent
        self.config_editor = config_editor
        self.is_running = False
        self.current_process = None
        self._line_buffer = ''  # 初始化行缓冲区
        self.log_text = None  # 先初始化为None，在create_tab中赋值
        self.create_tab()
        
        # 创建日志显示后，初始化日志系统的UI回调
        self._init_logger_ui_callback()
    
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
        ttk.Button(button_frame, text="测试全部", command=self.test_all_configs, style='Success.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="运行爬虫", command=self.run_crawler, style='Accent.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="停止运行", command=self.stop_crawler).grid(row=0, column=3, padx=5)
        
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
    
    def _init_logger_ui_callback(self):
        """初始化日志系统的UI回调，将日志输出到UI窗口"""
        def log_callback(message: str):
            """日志回调函数"""
            try:
                if self.log_text and self.log_text.winfo_exists():
                    self.log_text.insert('end', f"{message}\n")
                    self.log_text.see('end')  # 自动滚动到底部
                    self.config_editor.root.update_idletasks()  # 实时更新UI
            except tk.TclError:
                # UI控件已被销毁，静默忽略
                pass
        
        # 重新初始化日志系统，传入UI回调
        get_logger(ui_log_callback=log_callback)
    
    def update_current_exhibition(self):
        """更新当前选中的展会信息"""
        current_file = self.config_editor.current_file
        config_files = self.config_editor.config_files
        
        if current_file is not None and current_file in config_files:
            config_data = config_files[current_file]
            exhibition_code = config_data.get('exhibition_code', '')
            request_mode = config_data.get('request_mode', 'single')
            
            self.current_exhibition_label.config(text=exhibition_code)
            self.current_mode_label.config(text=request_mode)
        else:
            self.current_exhibition_label.config(text="未选择")
            self.current_mode_label.config(text="未选择")
    
    def log_message(self, message):
        """添加日志消息 - 保持与终端完全一致的显示"""
        # 直接输出原始消息，不添加额外时间戳
        log_line = message

        # 统一通过日志系统输出：StreamHandler 输出终端，UILogHandler 负责把消息回调到 UI
        from unified_logger import console
        console(log_line)
    
    def clear_log(self):
        """清空日志"""
        if self.log_text and self.log_text.winfo_exists():
            self.log_text.delete('1.0', tk.END)
    
    def run_crawler(self):
        """运行爬虫"""
        if self.is_running:
            self.config_editor.show_warning("爬虫正在运行中，请先停止当前运行")
            return
        
        current_file = self.config_editor.current_file
        config_files = self.config_editor.config_files
        
        if current_file is None or current_file not in config_files:
            self.config_editor.show_warning("请先选择要运行的展会配置")
            return
        
        exhibition_code = config_files[current_file]['exhibition_code']
        
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
            if start_page < 0:
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
                # 构建命令 - 兼容开发与打包环境
                import sys
                import os

                if getattr(sys, 'frozen', False):
                    # 打包后的环境 - 通过 exe 的 --subproc 标志执行内部 run_crawler
                    meipass = getattr(sys, '_MEIPASS', None)
                    app_dir = meipass or os.path.dirname(sys.executable)
                    cmd = [sys.executable, '--subproc=run_crawler', exhibition_code,
                           '--workers', str(workers),
                           '--start-page', str(start_page)]
                else:
                    cmd = ['python', 'run_crawler.py', exhibition_code,
                           '--workers', str(workers),
                           '--start-page', str(start_page)]
                
                self.log_message(f"执行命令: {' '.join(cmd)}")
                
                # 运行进程 - 修复编码问题和缓冲
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # 将stderr合并到stdout，确保日志(默认写stderr)被捕获
                    text=True,
                    bufsize=1,  # 行缓冲，便于逐行读取
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace',
                    env=dict(os.environ, PYTHONIOENCODING='utf-8')
                )
                
                # 实时读取输出，简化处理逻辑
                while True:
                    if self.current_process and self.current_process.stdout:
                        # 使用readline逐行读取，简化处理
                        line = self.current_process.stdout.readline()
                        if line == '' and self.current_process.poll() is not None:
                            break
                        if line:
                            # 直接显示所有输出，不进行过滤
                            self.log_message(line.rstrip('\n'))
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
        
        current_file = self.config_editor.current_file
        config_files = self.config_editor.config_files
        
        if current_file is None or current_file not in config_files:
            self.config_editor.show_warning("请先选择要测试的展会配置")
            return
        
        exhibition_code = config_files[current_file]['exhibition_code']
        
        # 确认测试
        if not self.config_editor.ask_yesno("确认测试", 
                                           f"确定要测试展会 '{exhibition_code}' 的配置吗？"):
            return
        
        # 清空日志并初始化
        self.clear_log()
        self.log_message(f"正在初始化配置测试...")
        
        # 启动测试
        self.is_running = True
        self.log_message(f"开始测试配置: {exhibition_code}")
        self.log_message("=" * 60)
        
        # 在新线程中运行测试
        def test_in_thread():
            try:
                # 构建命令 - 兼容开发和打包环境
                import sys
                import os
                
                if getattr(sys, 'frozen', False):
                    # 打包后的环境 - 通过 exe 的 --subproc 参数调用内部脚本
                    meipass = getattr(sys, '_MEIPASS', None)
                    app_dir = meipass or os.path.dirname(sys.executable)
                    cmd = [sys.executable, '--subproc=test_config', exhibition_code]
                else:
                    # 开发环境
                    cmd = ['python', 'test_config.py', exhibition_code]
                
                self.log_message(f"执行命令: {' '.join(cmd)}")
                self.log_message("")
                
                # 运行进程
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # 合并stderr到stdout，确保日志输出被捕获
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace',
                    env=dict(os.environ, PYTHONIOENCODING='utf-8')  # 确保子进程使用UTF-8编码
                )
                
                # 实时读取输出，简化处理逻辑
                while True:
                    if self.current_process and self.current_process.stdout:
                        # 使用readline逐行读取，简化处理
                        line = self.current_process.stdout.readline()
                        if line == '' and self.current_process.poll() is not None:
                            break
                        if line:
                            # 直接显示所有输出，不进行过滤
                            self.log_message(line.rstrip('\n'))
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
    
    def test_all_configs(self):
        """测试所有配置"""
        if self.is_running:
            self.config_editor.show_warning("正在运行中，请先停止当前运行")
            return
        
        # 获取所有展会代码
        try:
            from crawler_lib.config_manager import ConfigManager
            config_manager = ConfigManager()
            all_codes = config_manager.get_all_codes()
            
            if not all_codes:
                self.config_editor.show_warning("没有找到任何展会配置")
                return
            
        except Exception as e:
            self.config_editor.show_error(f"获取展会配置失败: {e}")
            return
        
        # 验证线程数参数
        try:
            max_workers = int(self.workers_var.get())
            if max_workers < 1 or max_workers > 20:
                self.config_editor.show_error("线程数必须在1-20之间")
                return
        except ValueError:
            self.config_editor.show_error("请输入有效的线程数")
            return
        
        # 确认测试
        total_configs = len(all_codes)
        if not self.config_editor.ask_yesno("确认测试全部", 
                                           f"确定要测试所有 {total_configs} 个展会配置吗？\n"
                                           f"将使用 {max_workers} 个线程并发测试。\n"
                                           f"这可能需要一些时间。"):
            return
        
        # 清空日志并初始化
        self.clear_log()
        self.log_message(f"正在初始化全部配置测试...")
        self.log_message(f"总计: {total_configs} 个展会配置")
        self.log_message(f"并发线程数: {max_workers}")
        
        # 启动测试
        self.is_running = True
        self.log_message(f"开始测试全部配置...")
        self.log_message("=" * 80)
        
        # 测试结果跟踪
        test_results = {}
        results_lock = threading.Lock()
        completed_count = [0]  # 使用列表以便在闭包中修改
        
        def test_single_config(exhibition_code):
            """测试单个展会配置"""
            process = None
            try:
                # 构建命令 - 兼容开发和打包环境
                import sys
                import os
                
                if getattr(sys, 'frozen', False):
                    # 打包后的环境 - 使用 exe 的 --subproc 分发方式
                    meipass = getattr(sys, '_MEIPASS', None)
                    app_dir = meipass or os.path.dirname(sys.executable)
                    cmd = [sys.executable, '--subproc=test_config', exhibition_code]
                else:
                    # 开发环境
                    cmd = ['python', 'test_config.py', exhibition_code]
                
                # 运行进程
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=dict(os.environ, PYTHONIOENCODING='utf-8')  # 确保子进程使用UTF-8编码
                )
                
                stdout, stderr = process.communicate(timeout=60)  # 60秒超时
                
                success = process.returncode == 0
                
                with results_lock:
                    test_results[exhibition_code] = {
                        'success': success,
                        'return_code': process.returncode,
                        'stdout': stdout,
                        'stderr': stderr
                    }
                    completed_count[0] += 1
                    
                    # 实时更新进度
                    progress = completed_count[0] / total_configs * 100
                    status = "✅ 成功" if success else "❌ 失败"
                    self.log_message(f"[{progress:.1f}%] {exhibition_code}: {status}")
                
            except subprocess.TimeoutExpired:
                if process:
                    process.kill()
                with results_lock:
                    test_results[exhibition_code] = {
                        'success': False,
                        'return_code': -1,
                        'stdout': '',
                        'stderr': '测试超时'
                    }
                    completed_count[0] += 1
                    progress = completed_count[0] / total_configs * 100
                    self.log_message(f"[{progress:.1f}%] {exhibition_code}: ❌ 超时")
                    
            except Exception as e:
                with results_lock:
                    test_results[exhibition_code] = {
                        'success': False,
                        'return_code': -1,
                        'stdout': '',
                        'stderr': str(e)
                    }
                    completed_count[0] += 1
                    progress = completed_count[0] / total_configs * 100
                    self.log_message(f"[{progress:.1f}%] {exhibition_code}: ❌ 异常 ({e})")
        
        # 使用线程池并发测试
        def test_all_in_thread():
            try:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                self.log_message(f"开始并发测试，使用 {max_workers} 个线程...")
                self.log_message("")
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有测试任务
                    future_to_code = {
                        executor.submit(test_single_config, code): code 
                        for code in all_codes
                    }
                    
                    # 等待所有任务完成
                    for future in as_completed(future_to_code):
                        pass  # 结果已在test_single_config中处理
                
                # 生成测试报告
                self.log_message("")
                self.log_message("=" * 80)
                self.log_message("测试报告")
                self.log_message("=" * 80)
                
                successful_tests = []
                failed_tests = []
                
                for code, result in test_results.items():
                    if result['success']:
                        successful_tests.append(code)
                    else:
                        failed_tests.append((code, result))
                
                # 统计信息
                success_count = len(successful_tests)
                fail_count = len(failed_tests)
                success_rate = success_count / total_configs * 100
                
                self.log_message(f"总配置数: {total_configs}")
                self.log_message(f"测试成功: {success_count} ({success_rate:.1f}%)")
                self.log_message(f"测试失败: {fail_count} ({100-success_rate:.1f}%)")
                self.log_message("")
                
                # 成功的配置
                if successful_tests:
                    self.log_message("✅ 测试成功的配置:")
                    for code in sorted(successful_tests):
                        self.log_message(f"  - {code}")
                    self.log_message("")
                
                # 失败的配置
                if failed_tests:
                    self.log_message("❌ 测试失败的配置:")
                    for code, result in sorted(failed_tests):
                        error_info = result['stderr'].strip() if result['stderr'] else str(result['return_code'])
                        # 限制错误信息长度
                        if len(error_info) > 100:
                            error_info = error_info[:100] + "..."
                        self.log_message(f"  - {code}")
                    self.log_message("")
                
                # 总结
                if fail_count == 0:
                    self.log_message("🎉 所有配置测试通过！")
                    self.config_editor.show_info(f"全部 {total_configs} 个展会配置测试通过！")
                else:
                    self.log_message(f"⚠️  有 {fail_count} 个配置测试失败，请检查上述失败项。")
                    self.config_editor.show_warning(f"测试完成：{success_count} 个成功，{fail_count} 个失败\n详情请查看日志。")
                
            except Exception as e:
                self.log_message(f"批量测试过程中出错: {e}")
                self.config_editor.show_error(f"批量测试时出错: {e}")
            finally:
                self.is_running = False
        
        # 启动测试线程
        thread = threading.Thread(target=test_all_in_thread, daemon=True)
        thread.start()
