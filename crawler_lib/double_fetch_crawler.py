"""
二次请求爬虫模块

适用于需要先获取列表，再获取详情的场景
"""

from .base_crawler import BaseCrawler
from unified_logger import log_error, log_list_progress, log_contacts_saved, console


class DoubleFetchCrawler(BaseCrawler):
    """
    二次请求爬虫（逐页处理版）
    
    适用于需要先获取列表，再获取详情的场景。
    
    工作流程：
    1. 获取一页公司列表
    2. 立即抓取这页所有公司的联系人
    3. 保存这一页的联系人数据到Excel
    4. 继续下一页
    
    """
    
    def __init__(self, exhibition_code: str, max_workers: int = 4, start_page: int = 1):
        """
        初始化二次请求爬虫
        
        Args:
            exhibition_code: 展会代码
            max_workers: 最大线程数
            start_page: 起始页码
        """
        super().__init__(exhibition_code, max_workers, start_page)
        
        # 使用DetailFetcher来获取联系人
        # 注意：此时 self.config 已经在父类初始化时验证过，不会为 None
        from .detail_fetcher import DetailFetcher
        if self.config is None:
            raise ValueError("配置不能为空")
        self.detail_fetcher = DetailFetcher(self.config, max_workers=self.max_workers)
        
        # 二次请求模式的额外统计
        self._total_contacts = 0
    
    def _print_double_summary(self):
        """
        打印二次请求爬取汇总信息
        """
        console("\n" + "="*60)
        console("📊 爬取汇总")
        console("="*60)
        console(f"展会代码: {self.exhibition_code}")
        console(f"总页数: {self._total_pages}")
        console(f"总公司数: {self._total_companies}")
        console(f"总联系人数: {self._total_contacts}")
        console("="*60 + "\n")
    
    def crawl(self) -> bool:
        """
        执行爬取流程（二次请求模式 - 逐页处理）
        
        每获取一页公司列表，就立即抓取联系人并保存，避免数据丢失。
        
        Returns:
            是否成功获取到数据
        """

        # 确定表头 - 基本配置的字段映射 + 联系人字段映射
        if self.config is None:
            raise ValueError("配置不能为空")
        
        if self.config.info_key:
            headers = list(self.config.company_info_keys.keys()) + list(self.config.info_key.keys())
        else:
            headers = list(self.config.company_info_keys.keys())

        # 回调：逐页处理（抓取联系人并保存）
        def _process_page(page: int, items: list):
            log_list_progress(page, len(items))

            # 抓取联系人
            all_contacts = self.detail_fetcher.fetch_batch_contacts_with_basic_info(
                companies_basic_info=items
            )

            if all_contacts:
                try:
                    self.exporter.save(all_contacts, self.exhibition_code, headers)
                    self._total_contacts += len(all_contacts)
                    log_contacts_saved(page, len(all_contacts))
                except Exception as e:
                    log_error(f"保存第{page}页联系人数据失败", e)

            # 更新公司数统计（保持原行为）
            self._total_companies += len(items)
            self._total_pages += 1

            # 继续分页默认
            return True

        try:
            # 删除旧文件（如果从第一页开始）
            self._delete_old_file_if_needed()
            
            # 重置统计信息
            self._reset_stats()

            has_data = self.paginate_sequential(
                start_page=self.start_page,
                process_page_callback=_process_page
            )
            
            # 显示汇总信息
            if has_data:
                self._print_double_summary()

            return has_data

        except KeyboardInterrupt:
            log_error("用户中断，已保存的数据不会丢失")
        except Exception as e:
            log_error("爬取过程出错", e)

        return False
