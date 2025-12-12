"""
配置文件图形化编辑器

使用tkinter创建的GUI界面，用于编辑JSON格式配置文件
支持增删改查功能，提供直观的操作界面
集成Gitee云端同步功能

重构后的版本 - 将代码拆分为多个模块以提高可读性和可维护性
集成了统一的日志系统
"""

import sys
import traceback
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading

# 导入统一日志系统
from unified_logger import log_info, log_error, log_exception
from ui import ConfigUIEditor
from gitee_sync import GiteeSync


def ask_sync_confirmation(is_startup=True):
    """询问用户是否同步配置文件
    
    Args:
        is_startup: 是否为启动时的询问，True为启动，False为关闭
    
    Returns:
        str: 用户选择 'sync', 'skip', 或 'cancel'
    """
    # 创建临时窗口用于显示对话框
    temp_root = tk.Tk()
    
    # 根据启动或关闭设置不同的消息
    if is_startup:
        title = "配置文件同步 - 启动"
        message = "是否要从远程仓库同步最新的配置文件？\n\n点击「是」同步，点击「否」跳过"
    else:
        title = "配置文件同步 - 关闭"
        message = "检测到配置文件可能已更改，\n是否要同步到远程仓库？\n\n点击「是」同步，点击「否」跳过"
    
    # 使用标准 messagebox，更简单可靠
    result = messagebox.askyesnocancel(title, message, parent=temp_root)
    
    # 销毁临时窗口
    temp_root.destroy()
    
    # 转换结果
    if result is True:
        return 'sync'
    elif result is False:
        return 'skip'
    else:  # result is None (用户点击取消或关闭窗口)
        return 'cancel'


def main():
    """主函数"""
    app_start_time = datetime.now()
    
    try:
        # 记录程序启动信息
        log_info("🚀 启动 配置文件图形化编辑器 v2.0")
        
        # 创建并运行配置编辑器
        log_info("配置编辑器 - 正在初始化GUI界面...")
        app = ConfigUIEditor()
        log_info("配置编辑器 - 初始化完成，启动GUI界面...",False)
        app.run()
        
    except ImportError as e:
        # 记录导入错误
        missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
        log_error(f"导入模块失败: {missing_module} - 请确保所有依赖模块都已正确安装")
        
        # 显示友好的错误信息
        messagebox.showerror(
            "依赖缺失", 
            f"缺少必要的依赖模块: {missing_module}\n\n"
            f"请安装以下依赖:\n"
            f"- tkinter (通常随Python安装)\n"
            f"- GitPython\n"
            f"- python-dotenv\n\n"
            f"运行命令: pip install GitPython python-dotenv"
        )
        sys.exit(1)
        
    except Exception as e:
        # 记录程序运行时错误
        log_exception(f"程序运行时发生错误: {type(e).__name__}")
        
        # 显示友好的错误信息
        error_msg = (
            f"程序运行时发生错误:\n\n"
            f"错误类型: {type(e).__name__}\n"
            f"错误信息: {e}\n\n"
            f"详细错误信息已记录到日志文件中。\n"
            f"请检查 logs/app_error.log 文件获取更多详情。"
        )
        
        messagebox.showerror("程序错误", error_msg)
        sys.exit(1)
    
    finally:
        # 记录程序关闭信息
        runtime = datetime.now() - app_start_time
        log_info(f"👋 关闭 配置文件图形化编辑器 (运行时间: {runtime})", ui=False)


if __name__ == "__main__":
    main()
