import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from urllib.parse import urlencode  # 修复 requests.utils.urlencode 的问题
import warnings
import json # 用于美化输出，方便调试

# 忽略 SSL 证书验证警告
warnings.filterwarnings("ignore")

# --- 全局配置 ---
BASE_URL = "https://qpz.sinomachint.com/CommonJson/GetCZJson"
DETAIL_URL ="https://qpz.sinomachint.com/CommonJson/GetCZXQJson"
TOTAL_PAGES = 342  # 总页数
MAX_WORKERS = 4   # 并发线程数
EXCEL_FILE = "公司及联系人信息.xlsx"
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded"
}

# 用于保存公司ID列表，避免重复抓取
company_ids_set = set()


# ==============================================================================
# 0. 验证与保存功能
# ==============================================================================

def validate_response(response_json: dict, request_type: str) -> bool:
    """
    验证响应体中的 'success' 键值是否为 True。
    """
    if response_json.get("success") is True:
        return True
    else:
        # 如果 success 不为 True，打印详细错误信息
        print(f"--- ⚠️ {request_type} 响应体验证失败 ---")
        try:
            print(f"响应内容（前200字符）: {str(response_json)[:200]}")
        except Exception:
            pass
        return False

def append_to_excel(data_list: list, filename: str):
    """
    将新数据追加保存到 Excel 文件中。
    """
    if not data_list:
        return

    new_df = pd.DataFrame(data_list)
    
    # 检查文件是否存在
    if os.path.exists(filename):
        try:
            # 尝试追加模式
            with pd.ExcelWriter(filename, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                 # 获取现有数据的行数，从下一行开始写入，不带表头
                 start_row = writer.sheets['公司信息'].max_row
                 new_df.to_excel(writer, sheet_name='公司信息', startrow=start_row, header=False, index=False)
            
        except Exception:
            # 如果追加失败（如文件被占用或首次写入），则使用覆盖模式写入
            print(f"追加写入 Excel 失败，尝试使用覆盖模式写入。")
            new_df.to_excel(filename, sheet_name='公司信息', index=False)
            
    else:
        # 文件不存在，直接创建并写入，包含表头
        new_df.to_excel(filename, sheet_name='公司信息', index=False)


# ==============================================================================
# I. 公司列表信息获取与解析
# ==============================================================================

def get_company_list_response(page_num: int) -> dict:
    """
    发送请求获取公司列表信息，并验证响应体。
    """
    url = BASE_URL
    data = {
        "TName": "MTZH",
        "CurrentPage": page_num
    }
    
    # 使用 urlencode 转换数据
    request_data = urlencode(data)
    
    response = requests.post(url, data=request_data, headers=HEADERS, verify=False) # 禁用 SSL 验证
    response.raise_for_status() # 检查 HTTP 状态码
    
    response_json = response.json()
    
    # 验证 'success' 字段
    if not validate_response(response_json, f"第 {page_num} 页列表请求"):
        raise ValueError(f"响应体验证失败，Page {page_num}。")
        
    return response_json


def parse_company_ids(response_json: dict) -> list:
    """
    从公司列表响应体中解析出所有公司 ID。
    """
    ids = []
    try:
        table_keys = response_json.get("jsonData", {}).get("TableKeys", [])
        if table_keys:
            ids = [int(key) for key in table_keys]
    except Exception as e:
        print(f"解析公司ID时发生错误: {e}")
        return []
        
    return ids


# ==============================================================================
# II. 单个公司详情信息获取与解析
# ==============================================================================

def get_company_details_response(company_id: int) -> dict:
    """
    发送请求获取单个公司及联系人信息，并验证响应体。
    """
    url = DETAIL_URL
    data = {
        "ID": str(company_id),
        "tablename": "MTZH",
        "zk": "CZSZC",
        "col": "ID,DWBH,MTZHGSMC,gsbzvalue,MTZHGSDZ,MTZHWZ,MTZHEMAIL,gsjjvalue,MTZHGSJJ,MTZHCPFL,MTZHCPJJ1,cp1value,MTZHCPJJ2,cp2value,MTZHCPJJ3,cp3value,MTZHCPJJ4,cp4value,MTZHCPJJ5,cp5value,MTZHGJZ,MTZHGSJJEN,MTZHCPJJEN1,MTZHCPJJEN2,gsjjvalue,MTZHCPJJEN3,MTZHCPJJEN4,MTZHCPJJEN5"
    }
    
    # 使用 urlencode 转换数据
    request_data = urlencode(data)
    
    response = requests.post(url, data=request_data, headers=HEADERS, verify=False) # 禁用 SSL 验证
    response.raise_for_status() # 检查 HTTP 状态码
    
    response_json = response.json()
    
    # 验证 'success' 字段
    if not validate_response(response_json, f"公司ID {company_id} 详情请求"):
        raise ValueError(f"响应体验证失败，ID {company_id}。")

    return response_json


def parse_company_details(response_json: dict) -> dict:
    """
    从公司详情响应体中解析出公司名称、展位号、电话和邮箱。
    """
    company_info = {
        "公司ID": "N/A",
        "公司名称": "N/A",
        "展位号": "N/A",
        "电话": "N/A",
        "邮箱": "N/A"
    }
    
    try:
        # 解析 jsonData.RowValues
        row_values = response_json.get("jsonData", {}).get("RowValues", [])
        if len(row_values) >= 7:
            company_info["公司ID"] = row_values[0] # ID
            company_info["公司名称"] = row_values[2] # MTZHGSMC
            company_info["邮箱"] = row_values[6] # MTZHEMAIL
        
        # 解析 row 列表获取其他信息
        dh1, dh2, dh3 = None, None, None
        
        for item in response_json.get("row", []):
            name = item.get("Name")
            value = item.get("Value", "").strip()
            
            if name == "ZWH":
                company_info["展位号"] = value
            elif name == "DH1": 
                dh1 = value
            elif name == "DH2": 
                dh2 = value
            elif name == "DH3": 
                dh3 = value

        # 组合电话号码
        # 尝试将电话组合成 +86 0563 6987688 格式
        if dh1 and dh2 and dh3 and dh1 != " " and dh2 != " " and dh3 != " ":
            # 如果地区码（DH2）不是0开头，尝试在前面加0
            formatted_dh2 = f"0{dh2}" if len(dh2) > 0 and dh2[0] != '0' else dh2
            company_info["电话"] = f"+{dh1} {formatted_dh2} {dh3}"
        
    except Exception as e:
        print(f"解析公司详情时发生错误: {e}，原始数据: {response_json}")
        return company_info

    return company_info


# ==============================================================================
# III. 并发执行与主程序
# ==============================================================================

def fetch_company_details(company_id: int):
    """
    获取单个公司详情并返回解析后的数据。
    """
    try:
        detail_json = get_company_details_response(company_id)
        return parse_company_details(detail_json)
    except (requests.exceptions.RequestException, ValueError) as e:
        # 捕获网络错误和验证失败
        print(f"公司ID {company_id} 详情请求失败: {e}")
    except Exception as e:
        print(f"公司ID {company_id} 详情处理失败: {e}")
    return None

def process_page(page_num: int):
    """
    处理单个页面的逻辑：获取公司ID，然后并发获取公司详情，最后保存。
    """
    print(f"--- 🚀 正在处理第 {page_num}/{TOTAL_PAGES} 页 ---")
    
    try:
        # 1. 获取列表响应体并验证
        list_json = get_company_list_response(page_num)
        
        # 2. 解析公司 ID 列表
        new_company_ids = parse_company_ids(list_json)
        
        if not new_company_ids:
            print(f"第 {page_num} 页未解析到公司 ID 或列表为空，跳过。")
            return
            
        ids_to_fetch = [id for id in new_company_ids if id not in company_ids_set]
        
        # 3. 并发获取公司详情
        page_results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_id = {executor.submit(fetch_company_details, id): id for id in ids_to_fetch}
            
            for future in as_completed(future_to_id):
                company_id = future_to_id[future]
                result = future.result()
                if result:
                    page_results.append(result)
                    company_ids_set.add(company_id) # 标记为已完成
        
        # 4. 实时保存数据到 Excel
        if page_results:
            append_to_excel(page_results, EXCEL_FILE)
            print(f"--- ✅ 第 {page_num} 页处理完成，成功抓取 {len(page_results)} 条记录并保存到 Excel。 ---")
        else:
            print(f"--- ⚠️ 第 {page_num} 页处理完成，但未成功抓取到新记录。 ---")
            
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"--- ❌ 第 {page_num} 页列表请求失败或验证失败: {e} ---")
    except Exception as e:
        print(f"--- ❌ 第 {page_num} 页处理时发生未知错误: {e} ---")


def main_scraper():
    """
    主程序入口，使用线程池并发处理所有页面。
    """
    print(f"--- 🌐 启动数据抓取程序 ---")
    print(f"目标总页数: {TOTAL_PAGES}")
    print(f"并发线程数: {MAX_WORKERS}")
    print(f"保存文件路径: {EXCEL_FILE}")
    
    # 确定要处理的页码范围
    page_numbers = range(1, TOTAL_PAGES + 1)

    # 使用多线程来并发处理每一页
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_page, page) for page in page_numbers]
        
        # 等待所有任务完成
        for future in as_completed(futures):
            # 简单迭代以确保所有任务执行完毕
            pass

    print("\n--- 🎉 所有页面数据抓取和保存工作完成！ ---")


# ==============================================================================
# V. 执行主程序
# ==============================================================================
if __name__ == "__main__":

    main_scraper()