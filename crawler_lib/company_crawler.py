"""
单次请求爬虫模块

适用于API一次性返回完整数据的场景
"""

from typing import Dict, List

from .base_crawler import BaseCrawler
from unified_logger import log_error


class CompanyCrawler(BaseCrawler):
    """
    单次请求爬虫
    
    适用于API一次性返回完整数据的场景。
    
    核心改进：
    - 动态翻页机制，不预先检测总页数
    - 并行模式：批量爬取+动态扩展，自动探测数据边界
    """
    
    def crawl_parallel(self) -> bool:
        """
        并行爬取模式
        
        使用动态扩展策略：
        1. 批量爬取一定数量的页面
        2. 根据结果判断是否需要继续
        
        Returns:
            是否成功获取到数据
        """
        if self.config is None:
            return False

        headers = list(self.config.company_info_keys.keys())

        def _process_page(page: int, items: list):
            company_list = items or []
            if company_list:
                try:
                    self.exporter.save(company_list, self.exhibition_code, headers)
                    with self._stats_lock:
                        self._total_companies += len(company_list)
                        self._total_pages += 1
                    from unified_logger import log_page_progress
                    log_page_progress(page, len(company_list))
                except Exception as e:
                    log_error(f"保存第{page}页数据出错", e)

            return True

        return self.paginate_streaming(
            start_page=self.start_page,
            process_page_callback=_process_page,
            max_workers=self.max_workers
        )
    
    def crawl(self) -> bool:
        """
        执行完整爬取流程（单次请求模式）
        
        Returns:
            是否成功获取到数据
        """
        try:
           
            # 删除旧文件（如果从第一页开始）
            self._delete_old_file_if_needed()
            
            # 重置统计信息
            self._reset_stats()
            
            # 执行爬取
            has_data = self.crawl_parallel()
            
            # 显示汇总信息
            if has_data:
                self._print_summary()
            
            return has_data
            
        except Exception as e:
            from unified_logger import log_error
            log_error("爬取过程中发生错误", e)
            return False
