"""
配置文件图形化编辑器

使用tkinter创建的GUI界面，用于编辑config.xlsx配置文件
支持增删改查功能，提供直观的操作界面

重构后的版本 - 将代码拆分为多个模块以提高可读性和可维护性
"""

import sys
import traceback
from ui import ConfigUIEditor


def main():
    """主函数"""
    try:
        print("正在启动配置文件图形化编辑器...")
        # 创建并运行配置编辑器
        app = ConfigUIEditor()
        print("配置编辑器初始化完成，启动GUI界面...")
        app.run()
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保所有依赖模块都已正确安装:")
        print("- tkinter (通常随Python安装)")
        print("- pandas")
        print("- openpyxl")
        input("按回车键退出...")
        sys.exit(1)
    except Exception as e:
        print(f"程序运行时发生错误:")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        print("\n详细错误堆栈:")
        traceback.print_exc()
        print("\n请检查上述错误信息并修复问题。")
        input("按回车键退出...")
        sys.exit(1)


if __name__ == "__main__":
    main()
