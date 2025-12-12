"""
统一爬虫程序 - 支持单次请求和二次请求两种模式

使用方法:
    python run_crawler.py <exhibition_code> [options]
    
示例:
    # 单次请求模式（自动根据配置判断）
    python run_crawler.py 无人机展
    
    # 指定线程数
    python run_crawler.py 无人机展 --workers 8
    
    # 二次请求模式会自动识别（根据config.xlsx中的request_mode字段）
    python run_crawler.py 农产品
"""

import sys
import time
import urllib3
from typing import List, Dict, Any
from datetime import datetime

# 设置UTF-8编码
import locale
import io

# 重设标准输出为UTF-8编码，并确保无缓冲
if sys.platform == 'win32':
    # Windows系统特殊处理
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True, errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True, errors='replace')
else:
    # Linux/Mac系统
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True, errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', line_buffering=True, errors='replace')

# 导入统一日志系统
from unified_logger import log_info, log_error, log_exception, log_page_progress

from crawler_lib import (
    ConfigManager,
    CompanyCrawler,
    DoubleFetchCrawler
)


class UnifiedCrawler:
    """
    统一爬虫类
    
    根据配置自动选择单次请求或二次请求模式
    """
    
    def __init__(self, exhibition_code: str, max_workers: int = 4, start_page: int = 1):
        self.exhibition_code = exhibition_code
        self.max_workers = max_workers
        self.start_page = start_page
        
        # 加载配置
        config_manager = ConfigManager()
        self.config = config_manager.get_config(exhibition_code)
        
        if self.config is None:
            error_msg = f"未找到展会 '{exhibition_code}' 的配置"
            log_error(f"配置错误: {error_msg}")
            raise ValueError(error_msg)
        
        # 根据请求模式选择爬虫
        self.request_mode = self.config.request_mode
        
        if self.request_mode == "double":
            # 二次请求模式
            self.crawler = DoubleFetchCrawler(exhibition_code, max_workers, start_page)
        else:
            # 单次请求模式（默认）
            self.crawler = CompanyCrawler(exhibition_code, max_workers, start_page)
    
    def crawl(self) -> bool:
        """执行爬取"""
        try:
            result = self.crawler.crawl()
            return result
            
        except Exception as e:
            log_error(f"爬取过程中发生异常: {self.exhibition_code}", exception=e)
            return False

def main():
    """主函数"""
    program_start_time = datetime.now()
    
    try:
        # 记录程序启动
        log_info("🚀 启动 统一爬虫程序 v3.2")
        
        if len(sys.argv) < 2:
            print("用法: python run_crawler.py <exhibition_code> [options]")
            print("\n选项:")
            print("  --workers N      并发线程数（默认: 2，推荐1-2避免触发防爬）")
            print("  --start-page N   起始页码（默认: 1）")
            print("\n支持两种模式:")
            print("  1. 单次请求模式: 直接从API获取完整数据")
            print("  2. 二次请求模式: 先获取列表，再获取详情")
            print("\n模式由config.xlsx中的request_mode字段决定")
            print("  - request_mode = 'single' (默认)")
            print("  - request_mode = 'double'")
            print("\n示例:")
            print("  python run_crawler.py 无人机展")
            print("  python run_crawler.py 无人机展 --workers 8")
            print("  python run_crawler.py 无人机展 --start-page 50")
            print("  python run_crawler.py 无人机展 --workers 8 --start-page 50")
            sys.exit(1)
        
        # 禁用SSL警告
        urllib3.disable_warnings()
        
        # 解析参数
        exhibition_code = sys.argv[1]
        max_workers = 2  # 默认改为2，避免触发防爬限制
        start_page = 1
        
        if "--workers" in sys.argv:
            idx = sys.argv.index("--workers")
            if idx + 1 < len(sys.argv):
                max_workers = int(sys.argv[idx + 1])
        
        if "--start-page" in sys.argv:
            idx = sys.argv.index("--start-page")
            if idx + 1 < len(sys.argv):
                start_page = int(sys.argv[idx + 1])
        
        try:
            # 测试输出：确保UI中能看到输出
            print("🔄 开始创建爬虫实例...", flush=True)
            crawler = UnifiedCrawler(exhibition_code, max_workers=max_workers, start_page=start_page)
            print("🔄 爬虫实例创建完成，开始爬取...", flush=True)
            success = crawler.crawl()
            print("🔄 爬取完成...", flush=True)
            
            if success:
                print("\n✓ 爬取成功！", flush=True)
            else:
                print("\n✗ 爬取失败", flush=True)
                sys.exit(1)
                
        except ValueError as e:
            print(f"\n错误: {e}", flush=True)
            sys.exit(1)
        except Exception as e:
            log_exception(f"爬取过程中发生错误")
            print(f"\n爬取过程中发生错误: {e}", flush=True)
            sys.exit(1)
            
    except Exception as e:
        log_exception("程序启动失败")
        print(f"\n程序启动失败: {e}", flush=True)
        sys.exit(1)
        
    finally:
        # 记录程序关闭
        runtime = datetime.now() - program_start_time
        log_info(f"👋 关闭 统一爬虫程序 (运行时间: {runtime})")

if __name__ == "__main__":
    main()
