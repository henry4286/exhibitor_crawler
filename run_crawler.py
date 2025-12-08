"""
统一爬虫程序 - 支持单次请求和二次请求两种模式

使用方法:
    python unified_crawler.py <exhibition_code> [options]
    
示例:
    # 单次请求模式（自动根据配置判断）
    python unified_crawler.py 无人机展
    
    # 指定线程数
    python unified_crawler.py 无人机展 --workers 8
    
    # 二次请求模式会自动识别（根据config.xlsx中的request_mode字段）
    python unified_crawler.py 农产品
"""

import sys
import time
import urllib3
from typing import List, Dict, Any

# 设置UTF-8编码
import locale
import io

# 重设标准输出为UTF-8编码
if sys.platform == 'win32':
    # Windows系统特殊处理
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from crawler_lib import (
    ConfigManager,
    CompanyCrawler,
    DoubleFetchCrawler,
    write_status_file
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
            raise ValueError(f"未找到展会 '{exhibition_code}' 的配置")
        
        # 根据请求模式选择爬虫
        self.request_mode = self.config.request_mode
        
        print(f"📋 检测到请求模式: {self.request_mode}", flush=True)
        
        if self.request_mode == "double":
            # 二次请求模式
            print("🔄 使用二次请求模式（先获取列表，再获取详情）", flush=True)
            self.crawler = DoubleFetchCrawler(exhibition_code, max_workers, start_page)
        else:
            # 单次请求模式（默认）
            print("✨ 使用单次请求模式（直接获取完整数据）", flush=True)
            self.crawler = CompanyCrawler(exhibition_code, max_workers, start_page)
    
    def crawl(self) -> bool:
        """执行爬取"""
        return self.crawler.crawl()



def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python unified_crawler.py <exhibition_code> [options]")
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
        print("  python unified_crawler.py 无人机展")
        print("  python unified_crawler.py 无人机展 --workers 8")
        print("  python unified_crawler.py 无人机展 --start-page 50")
        print("  python unified_crawler.py 无人机展 --workers 8 --start-page 50")
        sys.exit(1)
    
    # 禁用SSL警告
    urllib3.disable_warnings()
    
    # 清空状态文件
    write_status_file("errorlog.txt", "")
    write_status_file("python_excute_status.txt", "")
    
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
    
    print(f"\n{'='*60}")
    print(f"统一爬虫程序 v3.1")
    print(f"{'='*60}")
    print(f"展会代码: {exhibition_code}")
    print(f"线程数: {max_workers}")
    print(f"起始页: {start_page}")
    print(f"{'='*60}\n", flush=True)
    
    try:
        crawler = UnifiedCrawler(exhibition_code, max_workers=max_workers, start_page=start_page)
        success = crawler.crawl()
        
        if success:
            print("\n✓ 爬取成功！", flush=True)
        else:
            print("\n✗ 爬取失败", flush=True)
            sys.exit(1)
            
    except ValueError as e:
        print(f"\n错误: {e}", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n爬取过程中发生错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
