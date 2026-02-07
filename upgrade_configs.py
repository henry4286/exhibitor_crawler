"""
配置文件升级脚本

为所有现有的JSON配置文件添加新的字段（city和month），默认值为空字符串
用于升级项目配置结构
"""

import json
import os
import sys
from datetime import datetime


def upgrade_configs(config_dir='config'):
    """
    升级所有配置文件，添加 city 和 month 字段
    
    Args:
        config_dir: 配置文件目录路径
    """
    if not os.path.exists(config_dir):
        print(f"错误: 配置目录不存在: {config_dir}")
        return False
    
    upgraded_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"开始升级配置文件...")
    print(f"配置目录: {config_dir}")
    print("-" * 50)
    
    # 遍历所有JSON文件
    for filename in os.listdir(config_dir):
        if not filename.endswith('.json') or filename == 'index.json':
            continue
        
        file_path = os.path.join(config_dir, filename)
        
        try:
            # 读取现有配置
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 检查是否需要升级
            needs_upgrade = False
            
            # 添加 city 字段（如果不存在）
            if 'city' not in config:
                config['city'] = ''
                needs_upgrade = True
                print(f"  [+] {filename}: 添加 'city' 字段")
            
            # 添加 month 字段（如果不存在）
            if 'month' not in config:
                config['month'] = ''
                needs_upgrade = True
                print(f"  [+] {filename}: 添加 'month' 字段")
            
            if needs_upgrade:
                # 保存升级后的配置
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                upgraded_count += 1
            else:
                skipped_count += 1
                print(f"  [=] {filename}: 已是最新版本，跳过")
                
        except json.JSONDecodeError as e:
            print(f"  [X] {filename}: JSON解析错误 - {e}")
            error_count += 1
        except Exception as e:
            print(f"  [X] {filename}: 处理错误 - {e}")
            error_count += 1
    
    print("-" * 50)
    print(f"升级完成!")
    print(f"  已升级: {upgraded_count} 个文件")
    print(f"  已跳过: {skipped_count} 个文件")
    print(f"  错误: {error_count} 个文件")
    
    return error_count == 0


def backup_configs(config_dir='config'):
    """
    备份所有配置文件到 config_backups 目录
    
    Args:
        config_dir: 配置文件目录路径
    """
    backup_dir = f"config_backups/upgrade_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if not os.path.exists(config_dir):
        print(f"错误: 配置目录不存在: {config_dir}")
        return False
    
    # 创建备份目录
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_count = 0
    
    print(f"\n开始备份配置文件...")
    print(f"备份目录: {backup_dir}")
    
    for filename in os.listdir(config_dir):
        if not filename.endswith('.json') or filename == 'index.json':
            continue
        
        src_path = os.path.join(config_dir, filename)
        dst_path = os.path.join(backup_dir, filename)
        
        try:
            with open(src_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            with open(dst_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            backup_count += 1
        except Exception as e:
            print(f"  [X] 备份 {filename} 失败: {e}")
    
    print(f"备份完成! 共备份 {backup_count} 个文件\n")
    return True


def main():
    """主函数"""
    print("=" * 60)
    print("配置文件升级工具")
    print("=" * 60)
    print()
    print("此工具将为所有配置文件添加以下新字段:")
    print("  - city: 城市（默认空）")
    print("  - month: 月份（默认空）")
    print()
    
    # 询问是否备份
    response = input("是否先备份现有配置? (y/n): ").strip().lower()
    if response in ('y', 'yes', '是'):
        backup_configs()
        print()
    
    # 确认升级
    response = input("确认开始升级? (y/n): ").strip().lower()
    if response not in ('y', 'yes', '是'):
        print("已取消升级")
        return
    
    print()
    
    # 执行升级
    success = upgrade_configs()
    
    print()
    if success:
        print("✅ 升级成功完成!")
    else:
        print("⚠️ 升级完成，但有部分文件出错")
    
    print()
    input("按回车键退出...")


if __name__ == "__main__":
    main()
