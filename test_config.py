"""
配置测试工具

用于测试Excel配置是否正确，验证API接口是否能正常访问和解析数据。
不会保存完整数据，只显示测试结果。

使用方法:
    python test_config.py <exhibition_code>
    
示例:
    python test_config.py 无人机展
    python test_config.py 农产品展
"""

import sys
import urllib3
from typing import Any, Dict, List, Tuple

from crawler_lib.detail_fetcher import DetailFetcher
from crawler_lib.base_crawler import BaseCrawler

# 在导入 unified_logger 之前，设置环境变量避免UI回调
import os
os.environ['TEST_CONFIG_MODE'] = '1'


class ConfigTester(BaseCrawler):
    """配置测试器 - 继承自BaseCrawler，使用相同的底层逻辑"""
    
    def __init__(self, exhibition_code: str):
        """
        初始化配置测试器
        
        Args:
            exhibition_code: 展会代码
        """
        super().__init__(exhibition_code, max_workers=2, start_page=1)
        
        # 如果是二次请求模式，初始化DetailFetcher
        # self.config在父类中已经验证不为None
        if self.config and self.config.request_mode == "double":
            self.detail_fetcher = DetailFetcher(self.config, max_workers=2)

    def print_separator(self, title: str = "", char: str = "="):
        """打印分隔线"""
        if title:
            print(f"\n{char * 20} {title} {char * 20}")
        else:
            print(f"{char * 60}")

    def test_basic_config(self):
        """测试基本配置"""
        # 类型断言：self.config在父类中已验证不为None
        assert self.config is not None, "配置不能为None"
        
        self.print_separator("基本配置信息")
        
        print(f"展会代码: {self.exhibition_code}")
        print(f"请求模式: {self.config.request_mode}")
        print(f"URL: {self.config.url}")
        print(f"请求方法: {self.config.request_method}")
        print(f"Items Key: {self.config.items_key}")
        
        print(f"\n字段映射 ({len(self.config.company_info_keys)} 个字段):")
        for i, (output_key, input_key) in enumerate(self.config.company_info_keys.items(), 1):
            print(f"  {i}. {output_key} ← {input_key}")
        
        if self.config.request_mode == "double":
            print(f"\n二次请求配置:")
            print(f"  详情URL: {self.config.url_detail}")
            print(f"  详情请求方法: {self.config.request_method_detail or 'GET'}")
            print(f"  详情Items Key: {self.config.items_key_detail}")
            if self.config.info_key:
                print(f"  联系人字段映射 ({len(self.config.info_key)} 个字段):")
                for i, (output_key, input_key) in enumerate(self.config.info_key.items(), 1):
                    print(f"    {i}. {output_key} ← {input_key}")

    def test_api_request_and_parsing(self) -> Tuple[bool, List[Dict]]:
        """
        测试API请求和数据解析（使用crawler.py相同的方法）
        
        Returns:
            Tuple[bool, List[Dict]]: (请求是否成功, 解析后的数据列表)
        """
        # 类型断言：self.config在父类中已验证不为None
        assert self.config is not None, "配置不能为None"
        
        self.print_separator("测试API请求和数据解析")
        
        try:
            print(f"正在请求第1页数据...")
            print(f"URL: {self.config.url}")
            
            # 使用BaseCrawler的crawl_page方法（这会调用_make_request和_extract_and_parse）
            # 这与实际爬虫使用完全相同的逻辑
            items = self.crawl_page(page=1)
            
            print(f"✅ 请求成功！")
            
            if items:
                print(f"\n✅ 成功解析数据")
                print(f"数据条数: {len(items)}")
                
                # 显示第一条数据的示例
                if items:
                    print(f"\n第一条数据示例:")
                    sample_item = items[0]
                    for i, (key, value) in enumerate(sample_item.items(), 1):
                        if i <= 5:  # 只显示前5个字段
                            value_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                            print(f"  {key}: {value_str}")
                        if i == 5 and len(sample_item) > 5:
                            print(f"  ... (还有{len(sample_item)-5}个字段)")
                            break
            else:
                print(f"\n⚠️  未能解析到数据")
            
            return True, items
            
        except Exception as e:
            print(f"❌ 请求或解析失败: {e}")
            import traceback
            print(f"\n详细错误:")
            traceback.print_exc()
            return False, []

    def test_field_mapping(self, items: List[Dict]) -> bool:
        """
        测试字段映射是否正确
        
        Args:
            items: 已解析的数据列表
        
        Returns:
            bool: 字段映射是否成功（至少能提取到一个有效字段）
        """
        # 类型断言：self.config在父类中已验证不为None
        assert self.config is not None, "配置不能为None"
        
        if not items:
            print(f"\n⚠️  没有数据可供测试字段映射")
            return False
        
        self.print_separator("测试字段映射")
        
        print(f"使用第一条数据测试字段映射...")
        
        test_item = items[0]
        results = {}
        success_count = 0
        total_fields = len(self.config.company_info_keys)
        
        for output_field, source_path in self.config.company_info_keys.items():
            # 这里测试的是解析后的结果，所以直接检查字段是否存在且有值
            value = test_item[output_field]
            results[output_field] = value
            
            if value is not None and str(value).strip():  # 有有效值
                success_count += 1
                status = "✅"
            else:
                status = "❌"  # 字段不存在或值为空都视为配置错误
            
            value_str = str(value)[:50] if value else "(未找到或为空)"
            print(f"{status} {output_field} ← {source_path}: {value_str}")
        
        # 判断字段映射是否成功
        mapping_success = success_count > 0
        
        print(f"\n字段映射结果: {success_count}/{total_fields} 个字段成功提取")
        
        if not mapping_success:
            print(f"❌ 字段映射失败！所有配置的字段都无法从响应数据中提取到值")
            print(f"   请检查：")
            print(f"   1. company_info_keys 配置的字段路径是否正确")
            print(f"   2. API返回的数据结构是否发生了变化")
            print(f"   3. 字段路径中的key名称是否与实际数据匹配")
        else:
            print(f"✅ 字段映射成功！至少能提取到有效数据")
        
        return mapping_success

    def test_pagination(self) -> bool:
        """
        测试翻页功能（使用crawler.py相同的方法）
        
        Returns:
            bool: 翻页功能是否正常
        """
        # 类型断言：self.config在父类中已验证不为None
        assert self.config is not None, "配置不能为None"
        
        self.print_separator("测试翻页功能")
        
        try:
            print(f"正在测试第1页和第2页数据...")
            
            # 请求第1页（使用相同的crawl_page方法）
            print(f"\n📄 请求第1页...")
            page1_items = self.crawl_page(page=1)
            
            # 请求第2页
            print(f"📄 请求第2页...")
            page2_items = self.crawl_page(page=2)
            
            page1_count = len(page1_items) if page1_items else 0
            page2_count = len(page2_items) if page2_items else 0
            
            print(f"\n翻页测试结果:")
            print(f"  第1页数据条数: {page1_count}")
            print(f"  第2页数据条数: {page2_count}")
            
            # 使用BaseCrawler的_is_same_data方法检测重复数据
            if page1_count == 0:
                print(f"❌ 翻页测试失败：第1页没有数据，无法验证翻页功能")
                return False
            
            # 检查第2页是否有数据（某些情况下第2页可能没有数据）
            if page2_count > 0:
                # 检查数据是否重复（使用crawler.py相同的方法）
                is_same = page1_items == page2_items
                
                if is_same:
                    print(f"⚠️  警告：第1页和第2页的数据相同，可能存在翻页问题")
                    print(f"   这通常意味着API不支持翻页，或者翻页参数配置错误")
                    return False
                else:
                    print(f"✅ 翻页功能正常：第1页和第2页数据不同")
                    return True
            else:
                print(f"⚠️  第2页没有数据")
                print(f"   这可能是正常的（如果总共只有一页数据）")
                print(f"   也可能是翻页参数配置有问题")
                
                # 检查是否有翻页相关的配置参数
                url_str = str(self.config.url or "")
                params_str = str(self.config.params or "")
                data_str = str(self.config.data or "")
                
                has_page_placeholder = "{page}" in url_str or "{page}" in params_str or "{page}" in data_str
                
                if has_page_placeholder:
                    print(f"   检测到翻页占位符{{page}}配置，但第2页无数据，可能是：")
                    print(f"   1. 数据确实只有一页")
                    print(f"   2. 翻页参数名称或位置配置错误")
                    print(f"   3. API翻页逻辑有变化")
                    return False  # 有翻页配置但第2页无数据，可能有问题
                else:
                    print(f"   未检测到翻页占位符{{page}}配置")
                    return True  # 没有翻页配置，第2页无数据是正常的
            
        except Exception as e:
            print(f"❌ 翻页测试失败: {e}")
            import traceback
            print(f"\n详细错误:")
            traceback.print_exc()
            return False

    def test_detail_request(self, items: List[Dict]) -> bool:
        """
        测试详情请求（二次请求模式）- 使用与crawler.py相同的DetailFetcher
        
        Args:
            items: 已解析的公司数据列表
        
        Returns:
            bool: 测试是否成功
        """
        # 类型断言：self.config在父类中已验证不为None
        assert self.config is not None, "配置不能为None"
        
        if self.config.request_mode != "double":
            return True  # 单次请求模式不需要测试详情
        
        if not items:
            print("\n⚠️  没有公司数据，跳过详情测试")
            return False
        
        self.print_separator("测试详情API请求")
        
        test_company = items[0]
        company_name = test_company.get('Company', '未知公司')
        
        print(f"测试公司: {company_name}")
        print(f"详情URL模板: {self.config.url_detail}")
        print(f"请求方法: {self.config.request_method_detail or 'GET'}")
        
        try:
            # 使用DetailFetcher获取联系人（与DoubleFetchCrawler使用相同的方法）
            print(f"\n🔄 使用DetailFetcher.fetch_company_contacts()方法...")
            contacts = self.detail_fetcher.fetch_company_contacts(test_company)
            
            if not contacts:
                print(f"❌ 未获取到联系人数据")
                return False
            
            print(f"✅ 详情请求成功！")
            print(f"✅ 获取到 {len(contacts)} 条联系人")
            
            # 显示第一个联系人的字段映射结果
            has_valid_data = False
            if contacts and self.config.info_key:
                print(f"\n第一个联系人的字段映射:")
                for output_key, input_key in self.config.info_key.items():
                    value = contacts[0].get(output_key)
                    if value:  # 有至少一个字段有值
                        has_valid_data = True
                    status = "✅" if value else "⚠️"
                    value_str = str(value)[:100] if value else "(空)"
                    print(f"{status} {output_key} ← {input_key}: {value_str}")
                
                # 检查是否所有字段都为空
                if not has_valid_data:
                    print(f"\n❌ 警告：所有联系人字段都为空！")
                    print(f"   这通常意味着：")
                    print(f"   1. 字段路径配置错误（info_key）")
                    print(f"   2. 详情API请求参数配置错误")
                    print(f"   3. items_key_detail路径不正确")
                    return False  # 字段全空视为测试失败
                else:
                    print(f"✅ 联系人字段映射成功！")
            
            return has_valid_data  # 只有当有有效数据时才返回True
                
        except Exception as e:
            print(f"❌ 详情请求失败: {e}")
            import traceback
            print(f"\n详细错误:")
            traceback.print_exc()
            return False

    def test_all(self) -> bool:
        """
        执行完整测试
        
        Returns:
            bool: 所有测试是否通过
        """
        # 类型断言：self.config在父类中已验证不为None
        assert self.config is not None, "配置不能为None"
        
        print(f"\n{'='*60}")
        print(f"配置测试工具 - {self.exhibition_code}")
        print(f"{'='*60}")
        
        # 1. 测试基本配置
        self.test_basic_config()
        
        # 2. 测试API请求和数据解析
        request_success, items = self.test_api_request_and_parsing()
        
        if not request_success:
            print(f"\n❌ API请求失败，测试终止")
            return False
        
        # 3. 测试字段映射
        field_mapping_success = False
        if items:
            field_mapping_success = self.test_field_mapping(items)
        
        # 4. 测试翻页功能
        pagination_success = True
        if items:  # 只有当有数据时才测试翻页
            pagination_success = self.test_pagination()
        
        # 5. 测试详情请求（如果是二次请求模式）
        detail_success = True
        if self.config.request_mode == "double":
            detail_success = self.test_detail_request(items)
        
        # 总结
        self.print_separator("测试总结")
        
        # 计算总体成功状态
        if self.config.request_mode == "single":
            # 单次请求模式：请求成功 + 字段映射成功 + 翻页功能正常（翻页失败不算致命错误）
            all_success = request_success and field_mapping_success
        else:
            # 二次请求模式：请求成功 + 字段映射成功 + 详情请求成功 + 翻页功能正常（翻页失败不算致命错误）
            all_success = request_success and field_mapping_success and detail_success
        
        if all_success:
            print(f"✅ 配置测试完成 - 所有测试通过！")
        else:
            print(f"❌ 配置测试完成 - 部分测试失败！")
        
        print(f"\n测试结果:")
        print(f"  - 基本配置: ✅ 正常")
        print(f"  - API请求: {'✅ 成功' if request_success else '❌ 失败'}")
        print(f"  - 数据解析: {'✅ 成功' if items else '⚠️  无数据'}")
        print(f"  - 字段映射: {'✅ 成功' if field_mapping_success else '❌ 失败'}")
        print(f"  - 翻页功能: {'✅ 正常' if pagination_success else '⚠️  可能有问题'}")
        
        if self.config.request_mode == "double":
            print(f"  - 详情请求: {'✅ 成功' if detail_success else '❌ 失败'}")
        
        return all_success


def main():
    """主函数"""
    # 设置UTF-8编码，避免Windows控制台编码问题
    # 尝试将 stdout/stderr 包装为 UTF-8，确保子进程输出为 UTF-8 编码（安全回退）
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        # 在某些环境下（例如没有 buffer 属性）跳过包装，保留默认行为
        pass
    
    if len(sys.argv) < 2:
        print("=" * 60)
        print("配置测试工具")
        print("=" * 60)
        print("\n用法: python test_config.py <exhibition_code>")
        print("\n功能:")
        print("  1. 验证配置文件是否正确")
        print("  2. 测试API接口是否可访问")
        print("  3. 检查数据提取路径是否正确")
        print("  4. 验证字段映射是否有效")
        print("  5. 测试翻页功能")
        print("  6. 测试二次请求（如适用）")
        print("\n特点:")
        print("  - 使用与run_crawler.py相同的底层逻辑")
        print("  - 测试结果与实际爬虫运行结果一致")
        print("  - 支持单次请求和二次请求两种模式")
        print("\n示例:")
        print("  python test_config.py 无人机展")
        print("  python test_config.py 农产品展")
        print("\n" + "=" * 60)
        sys.exit(1)
    
    # 禁用SSL警告
    urllib3.disable_warnings()
    
    exhibition_code = sys.argv[1]
    
    try:
        tester = ConfigTester(exhibition_code)
        success = tester.test_all()
        
        sys.exit(0 if success else 1)
        
    except ValueError as e:
        print(f"\n❌ 错误: {e}")
        print(f"提示: 请检查展会代码是否在config.xlsx中存在")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
