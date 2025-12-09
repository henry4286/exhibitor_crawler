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
import json
import urllib3
from typing import Any, Dict, List

from crawler_lib import (
    ConfigManager,
    HttpClient,
    DataParser,
    get_nested_value
)
from crawler_lib.detail_fetcher import DetailFetcher


class ConfigTester:
    """配置测试器"""
    
    def __init__(self, exhibition_code: str):
        self.exhibition_code = exhibition_code
        
        # 加载配置
        config_manager = ConfigManager()
        self.config = config_manager.get_config(exhibition_code)
        
        if self.config is None:
            raise ValueError(f"未找到展会 '{exhibition_code}' 的配置")
        
        self.http_client = HttpClient()
        self.data_parser = DataParser()
        self.detail_fetcher = DetailFetcher(self.config, max_workers=1)
    
    def print_separator(self, title: str = "", char: str = "="):
        """打印分隔线"""
        if title:
            print(f"\n{char * 20} {title} {char * 20}")
        else:
            print(f"{char * 60}")
    
    def print_json(self, data: Any, max_depth: int = 3, current_depth: int = 0):
        """美化打印JSON数据（限制深度）"""
        if current_depth >= max_depth:
            print("  " * current_depth + "...")
            return
        
        if isinstance(data, dict):
            for key, value in list(data.items())[:10]:  # 最多显示10个键
                if isinstance(value, (dict, list)):
                    print("  " * current_depth + f"{key}:")
                    self.print_json(value, max_depth, current_depth + 1)
                else:
                    value_str = str(value)[:100]  # 限制值的长度
                    print("  " * current_depth + f"{key}: {value_str}")
            if len(data) > 10:
                print("  " * current_depth + f"... 还有 {len(data) - 10} 个字段")
        elif isinstance(data, list):
            print("  " * current_depth + f"[列表，共 {len(data)} 项]")
            if data and current_depth < max_depth - 1:
                print("  " * current_depth + "第一项:")
                self.print_json(data[0], max_depth, current_depth + 1)
        else:
            print("  " * current_depth + str(data)[:200])
    
    def test_basic_config(self):
        """测试基本配置"""
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
            print(f"  详情Items Key: {self.config.items_key_detail}")
            if self.config.info_key:
                print(f"  联系人字段映射 ({len(self.config.info_key)} 个字段):")
                for i, (output_key, input_key) in enumerate(self.config.info_key.items(), 1):
                    print(f"    {i}. {output_key} ← {input_key}")
            
            # 显示基本配置中的ID和Company字段映射
            id_field = self.config.company_info_keys.get('ID')
            company_field = self.config.company_info_keys.get('Company')
            if id_field and company_field:
                print(f"  参数传递配置:")
                print(f"    ID字段映射: {id_field}")
                print(f"    Company字段映射: {company_field}")
    
    def test_list_request(self) -> tuple[bool, Any, List[Dict]]:
        """测试列表请求"""
        self.print_separator("测试列表API请求")
        
        try:
            print(f"正在请求第1页数据...")
            print(f"URL: {self.config.url}")
            
            # 发送请求
            response_data = self.http_client.send_request(self.config, page=1)
            
            print(f"✅ 请求成功！")
            
            # 提取公司列表
            items = self.data_parser.extract_items(response_data, self.config.items_key)
            
            if items:
                print(f"\n✅ 成功提取数据列表")
                print(f"数据条数: {len(items)}")
                
            else:
                print(f"\n⚠️  未能提取到数据列表")
                print(f"Items Key: {self.config.items_key}")
                print(f"请检查items_key配置是否正确")
            
            return True, response_data, items
            
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            import traceback
            print(f"\n详细错误:")
            traceback.print_exc()
            return False, None, []
    
    def test_field_mapping(self, items: List[Dict]) -> bool:
        """测试字段映射
        
        Returns:
            bool: 字段映射是否成功（至少能提取到一个有效字段）
        """
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
            value = get_nested_value(test_item, source_path)
            results[output_field] = value
            
            if value is not None and str(value).strip():  # 有有效值
                success_count += 1
                status = "✅"
            else:
                status = "❌"  # 找不到key或值为空都视为配置错误
            
            value_str = str(value)[:100] if value else "(未找到或为空)"
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
        """测试翻页功能
        
        Returns:
            bool: 翻页功能是否正常
        """
        self.print_separator("测试翻页功能")
        
        try:
            print(f"正在测试第1页和第2页数据...")
            
            # 请求第1页
            print(f"\n📄 请求第1页...")
            page1_data = self.http_client.send_request(self.config, page=1)
            page1_items = self.data_parser.extract_items(page1_data, self.config.items_key)
            
            # 请求第2页
            print(f"📄 请求第2页...")
            page2_data = self.http_client.send_request(self.config, page=2)
            page2_items = self.data_parser.extract_items(page2_data, self.config.items_key)
            
            page1_count = len(page1_items) if page1_items else 0
            page2_count = len(page2_items) if page2_items else 0
            
            print(f"\n翻页测试结果:")
            print(f"  第1页数据条数: {page1_count}")
            print(f"  第2页数据条数: {page2_count}")
            
            # 判断翻页是否成功
            if page1_count == 0:
                print(f"❌ 翻页测试失败：第1页没有数据，无法验证翻页功能")
                return False
            
            # 检查第2页是否有数据（某些情况下第2页可能没有数据）
            if page2_count > 0:
                print(f"✅ 翻页功能正常：成功获取到第2页数据")
                
                # 检查数据是否重复（比较第一条数据）
                if page1_items and page2_items:
                    if page1_items[0] == page2_items[0]:
                        print(f"⚠️  警告：第1页和第2页的第一条数据相同，可能存在翻页问题")
                    else:
                        print(f"✅ 数据无重复（第1页和第2页的第一条数据不相同）")
                
                return True
            else:
                print(f"⚠️  第2页没有数据")
                print(f"   这可能是正常的（如果总共只有一页数据）")
                print(f"   也可能是翻页参数配置有问题")
                
                # 检查是否有翻页相关的配置参数（检查url、params和data中是否包含{page}占位符）
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
        """测试详情请求（二次请求模式）- 使用与run_crawler相同的DetailFetcher
        
        Returns:
            bool: 测试是否成功
        """
        if self.config.request_mode != "double":
            return True  # 单次请求模式不需要测试详情
        
        if not items:
            print("\n⚠️  没有公司数据，跳过详情测试")
            return False
        
        self.print_separator("测试详情API请求")
        
        test_company = items[0]
        
        # 从基本配置的字段映射中获取ID和Company字段
        id_field = self.config.company_info_keys.get('ID', 'id')
        company_field = self.config.company_info_keys.get('Company', 'name')
        
        company_id = get_nested_value(test_company, id_field)
        company_name = get_nested_value(test_company, company_field)
        
        if not company_id:
            print(f"❌ 无法获取公司ID")
            print(f"ID字段路径: {id_field}")
            print(f"请检查基本配置的字段映射中是否包含ID字段")
            return False
        
        print(f"测试公司: {company_name or '(无名称)'}")
        print(f"公司ID: {company_id}")
        print(f"详情URL模板: {self.config.url_detail}")
        print(f"请求方法: {self.config.request_method_detail or 'GET'}")
        
        try:
            # 使用DetailFetcher获取联系人（与run_crawler.py使用相同的方法）
            print(f"\n🔄 使用DetailFetcher.fetch_company_contacts()方法...")
            contacts = self.detail_fetcher.fetch_company_contacts(test_company)
            
            if not contacts:
                print(f"❌ 未获取到联系人数据")
                return False
            
            print(f"✅ 详情请求成功！")
            print(f"✅ 获取到 {len(contacts)} 条联系人")
            
            # 调试：显示原始响应数据结构
            print(f"\n🔍 调试信息 - 详情API原始响应:")
            try:
                import requests
                url = str(self.config.url_detail or "").replace("#company_id", str(company_id))
                params_str = str(self.config.params_detail or "")
                data_str = str(self.config.data_detail or "")
                
                if params_str:
                    params_str = params_str.replace("#company_id", str(company_id))
                if data_str:
                    data_str = data_str.replace("#company_id", str(company_id))
                
                if params_str and params_str not in ("nan", "{}", ""):
                    params = json.loads(params_str)
                else:
                    params = {}
                
                if data_str and data_str not in ("nan", "{}", ""):
                    data = json.loads(data_str)
                else:
                    data = {}
                
                headers = self.config.headers_detail or {}
                request_method = (self.config.request_method_detail or 'GET').upper()
                content_type = headers.get('Content-Type', '').lower()
                
                print(f"请求详情 - Content-Type: {content_type}")
                print(f"请求详情 - URL: {url}")
                print(f"请求详情 - params: {params}")
                print(f"请求详情 - data: {data}")
                
                if request_method == 'POST':
                    if 'application/json' in content_type:
                        # JSON格式
                        response = requests.post(url, json=data, params=params, headers=headers, verify=False, timeout=30)
                    else:
                        # 表单格式
                        response = requests.post(url, data=data, params=params, headers=headers, verify=False, timeout=30)
                else:
                    response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
                
                response_data = response.json()
                
                if self.config.items_key_detail:
                    contact_data = get_nested_value(response_data, self.config.items_key_detail)
                    print(f"items_key_detail路径: {self.config.items_key_detail}")
                    print(f"提取数据类型(解析前): {type(contact_data).__name__}")
                    
                    # 如果是字符串，尝试解析为JSON
                    if isinstance(contact_data, str) and contact_data:
                        print(f"字符串内容前200字符: {contact_data[:200]}")
                        try:
                            parsed = json.loads(contact_data)
                            print(f"✅ JSON解析成功！解析后类型: {type(parsed).__name__}")
                            if isinstance(parsed, dict):
                                print(f"字段: {list(parsed.keys())[:15]}")
                            elif isinstance(parsed, list):
                                print(f"列表长度: {len(parsed)}")
                                if parsed and isinstance(parsed[0], dict):
                                    print(f"第一项字段: {list(parsed[0].keys())[:15]}")
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON解析失败: {e}")
                    elif isinstance(contact_data, dict):
                        print(f"字段: {list(contact_data.keys())[:15]}")
                    elif isinstance(contact_data, list):
                        print(f"列表长度: {len(contact_data)}")
                        if contact_data and isinstance(contact_data[0], dict):
                            print(f"第一项字段: {list(contact_data[0].keys())[:15]}")
            except Exception as e:
                print(f"调试信息获取失败: {e}")
            
            # 显示第一个联系人的字段映射
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
                    print(f"   请检查上面的调试信息，查看API返回的实际数据结构！")
                    return False  # 字段全空视为测试失败
            
            return has_valid_data  # 只有当有有效数据时才返回True
                
        except Exception as e:
            print(f"❌ 详情请求失败: {e}")
            import traceback
            print(f"\n详细错误:")
            traceback.print_exc()
            return False
    
    def test_all(self):
        """执行完整测试"""
        print(f"\n{'='*60}")
        print(f"配置测试工具 - {self.exhibition_code}")
        print(f"{'='*60}")
        
        # 1. 测试基本配置
        self.test_basic_config()
        
        # 2. 测试列表请求
        list_success, response_data, items = self.test_list_request()
        
        if not list_success:
            print(f"\n❌ 列表请求失败，测试终止")
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
        
        # 计算总体成功状态 - 根据用户要求，字段映射成功是关键判断标准
        if self.config.request_mode == "single":
            # 单次请求模式：列表请求成功 + 字段映射成功 + 翻页功能正常（翻页失败不算致命错误）
            all_success = list_success and field_mapping_success
        else:
            # 二次请求模式：列表请求成功 + 字段映射成功 + 详情请求成功 + 翻页功能正常（翻页失败不算致命错误）
            all_success = list_success and field_mapping_success and detail_success
        
        if all_success:
            print(f"✅ 配置测试完成 - 所有测试通过！")
        else:
            print(f"❌ 配置测试完成 - 部分测试失败！")
        
        print(f"\n测试结果:")
        print(f"  - 基本配置: ✅ 正常")
        print(f"  - API连接: {'✅ 正常' if list_success else '❌ 失败'}")
        print(f"  - 数据提取: {'✅ 正常' if items else '⚠️  无数据'}")
        print(f"  - 字段映射: {'✅ 成功' if field_mapping_success else '❌ 失败'}")
        print(f"  - 翻页功能: {'✅ 正常' if pagination_success else '⚠️  可能有问题'}")
        
        if self.config.request_mode == "double":
            print(f"  - 详情请求: {'✅ 成功' if detail_success else '❌ 失败'}")
        
        
        return all_success


def main():
    """主函数"""
    # 设置UTF-8编码，避免Windows控制台编码问题
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
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
        print("  5. 测试翻页功能（新增）")
        print("  6. 测试二次请求（如适用）")
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
