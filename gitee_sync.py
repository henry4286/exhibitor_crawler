"""
Gitee配置文件同步模块 - 简化版本

功能：
- 从Gitee仓库拉取最新的config目录
- 将本地的config目录推送到Gitee仓库
- 支持JSON格式的独立配置文件管理
- 简化的Git版本控制操作
"""

import os
import shutil
import tempfile
import hashlib
import json
import glob
from datetime import datetime
from typing import Tuple, List, Optional

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from unified_logger import log_info, log_error, log_warning, log_exception


def _create_backup_dir() -> str:
    """创建备份目录（带时间戳）
    
    Returns:
        备份目录路径
    """
    backup_base = "config_backups"
    if not os.path.exists(backup_base):
        os.makedirs(backup_base, exist_ok=True)
    
    # 创建带时间戳的备份目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(backup_base, f"config_backup_{timestamp}")
    os.makedirs(backup_dir, exist_ok=True)
    
    return backup_dir


class GiteeSync:
    """Gitee配置文件同步管理器 - 简化版本"""
    
    def __init__(self):
        """初始化同步管理器"""
        self.repo_url = "https://gitee.com/comeon_i/crawler.git"
        self.config_dir = "config"
        self.username = os.getenv('GITEE_USERNAME')
        self.token = os.getenv('GITEE_TOKEN')
        
        # 构建认证URL
        self.authenticated_url = self._build_auth_url()
        
        # 使用绝对路径
        self.local_config_path = os.path.abspath(self.config_dir)
        self.original_dir = os.getcwd()
        
        # 确保本地配置目录存在
        self._ensure_config_dir()
    
    def _build_auth_url(self) -> str:
        """构建认证URL - 保持原始版本的逻辑"""
        # Gitee使用不同的认证方式，先尝试无认证URL
        authenticated_url = self.repo_url
        if self.token:
            # Gitee使用Personal Access Token，格式为：https://oauth2:{token}@gitee.com/user/repo.git
            authenticated_url = self.repo_url.replace('https://', f'https://oauth2:{self.token}@')
        elif self.username and self.token:
            authenticated_url = self.repo_url.replace('https://', f'https://{self.username}:{self.token}@')
        return authenticated_url
    
    def _run_git_command(self, cmd: str, cwd: str = None) -> Tuple[bool, str]:
        """运行Git命令"""
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd or self.original_dir
            )
            return result.returncode == 0, result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except Exception as e:
            return False, str(e)
    
    def _ensure_config_dir(self):
        """确保本地配置目录存在"""
        if not os.path.exists(self.local_config_path):
            os.makedirs(self.local_config_path, exist_ok=True)
            log_info(f"创建配置目录: {self.local_config_path}")
    
    def _clone_repo_to_temp(self) -> Tuple[bool, str, str]:
        """克隆仓库到临时目录，返回(成功状态, 临时目录路径, 错误信息)"""
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="gitee_sync_")
            repo_dir = os.path.join(temp_dir, "repo")
            
            # 尝试使用认证URL克隆
            success, output = self._run_git_command(
                f'git clone "{self.authenticated_url}" "{repo_dir}" --depth 1'
            )
            
            # 如果认证URL失败，尝试无认证URL（fallback机制）
            if not success and self.authenticated_url != self.repo_url:
                log_warning("认证URL克隆失败，尝试无认证URL")
                success, output = self._run_git_command(
                    f'git clone "{self.repo_url}" "{repo_dir}" --depth 1'
                )
            
            if not success:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False, "", f"克隆失败: {output}"
            
            # 设置Git用户信息
            self._run_git_command('git config user.name "exhibitor_crawler_bot"', repo_dir)
            self._run_git_command('git config user.email "bot@example.com"', repo_dir)
            
            return True, temp_dir, ""
            
        except Exception as e:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return False, "", f"克隆失败: {str(e)}"
    
    def _cleanup_temp_dir(self, temp_dir: str):
        """清理临时目录"""
        try:
            if temp_dir and os.path.exists(temp_dir):
                os.chdir(self.original_dir)
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            log_warning(f"清理临时文件失败: {e}")
    
    def _get_config_files(self) -> List[str]:
        """获取所有配置文件列表"""
        config_files = []
        if os.path.exists(self.local_config_path):
            for file_path in glob.glob(os.path.join(self.local_config_path, "*.json")):
                filename = os.path.basename(file_path)
                config_files.append(filename)
        return config_files
    
    def _update_index_file(self):
        """更新索引文件 - 简化版本"""
        try:
            config_files = self._get_config_files()
            
            index_data = {
                "total_configs": len(config_files),
                "config_files": config_files,
                "last_updated": datetime.now().isoformat()
            }
            
            index_path = os.path.join(self.local_config_path, "index.json")
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            
            log_info(f"索引文件已更新，共{len(config_files)}个配置文件")
            
        except Exception as e:
            log_exception(f"更新索引文件失败: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """获取文件的MD5哈希值"""
        if not os.path.exists(file_path):
            return ""
        
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _has_file_changes(self, local_path: str, remote_path: str) -> bool:
        """检查文件是否有变更"""
        if not os.path.exists(local_path) or not os.path.exists(remote_path):
            return True
        
        return self._get_file_hash(local_path) != self._get_file_hash(remote_path)
    
    def _format_sync_message(self, action: str, changed_files: List[str]) -> str:
        """格式化同步消息 - 简化版本"""
        if not changed_files:
            return ""
        
        action_text = "拉取" if action == "pull" else "推送"
        lines = [f"{action_text}了 {len(changed_files)} 个文件:"]
        
        for filename in changed_files[:5]:  # 最多显示5个
            lines.append(f"  • {filename}")
        
        if len(changed_files) > 5:
            lines.append(f"  • ... 还有 {len(changed_files) - 5} 个文件")
        
        return "\n".join(lines)
    
    def pull_configs(self) -> Tuple[bool, str]:
        """从Gitee仓库拉取最新的配置目录"""
        log_info("开始从Gitee拉取配置文件")
        
        success, temp_dir, error_msg = self._clone_repo_to_temp()
        if not success:
            return False, error_msg
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_dir = os.path.join(repo_dir, self.config_dir)
            
            if not os.path.exists(remote_config_dir):
                log_info("远程仓库为空，创建空的配置目录")
                self._update_index_file()
                return True, "创建了新的配置目录"
            
            # 检查是否有变更
            changed_files = []
            local_files = set(self._get_config_files())
            
            for file_path in glob.glob(os.path.join(remote_config_dir, "*.json")):
                filename = os.path.basename(file_path)
                local_file_path = os.path.join(self.local_config_path, filename)
                
                if self._has_file_changes(local_file_path, file_path):
                    changed_files.append(filename)
            
            # 检查本地有但远程没有的文件
            for filename in local_files:
                remote_file_path = os.path.join(remote_config_dir, filename)
                if not os.path.exists(remote_file_path):
                    changed_files.append(f"[删除] {filename}")
            
            if not changed_files:
                log_info("没有文件变更")
                return True, ""
            
            # 备份本地配置
            backup_dir = _create_backup_dir()
            if os.path.exists(self.local_config_path):
                backup_config_dir = os.path.join(backup_dir, "config")
                shutil.copytree(self.local_config_path, backup_config_dir)
                log_info(f"本地配置已备份到: {backup_config_dir}")
            
            # 复制远程配置目录到本地
            if os.path.exists(self.local_config_path):
                shutil.rmtree(self.local_config_path)
            shutil.copytree(remote_config_dir, self.local_config_path)
            
            # 更新索引文件
            self._update_index_file()
            
            log_info("配置目录已更新")
            return True, self._format_sync_message("pull", changed_files)
            
        except Exception as e:
            log_exception(f"拉取配置失败: {e}")
            return False, f"拉取失败: {str(e)}"
        
        finally:
            self._cleanup_temp_dir(temp_dir)
    
    def push_configs(self) -> Tuple[bool, str]:
        """将本地的配置目录推送到Gitee仓库"""
        log_info("开始推送配置文件到Gitee")
        
        if not os.path.exists(self.local_config_path):
            return False, "本地配置目录不存在"
        
        success, temp_dir, error_msg = self._clone_repo_to_temp()
        if not success:
            return False, error_msg
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_dir = os.path.join(repo_dir, self.config_dir)
            
            # 更新索引文件
            self._update_index_file()
            
            # 检查是否有变更
            changed_files = []
            local_files = self._get_config_files()
            
            # 确保远程配置目录存在
            os.makedirs(remote_config_dir, exist_ok=True)
            
            # 比较本地和远程文件
            remote_files = set()
            if os.path.exists(remote_config_dir):
                for file_path in glob.glob(os.path.join(remote_config_dir, "*.json")):
                    filename = os.path.basename(file_path)
                    remote_files.add(filename)
                    
                    local_file_path = os.path.join(self.local_config_path, filename)
                    if self._has_file_changes(local_file_path, file_path):
                        changed_files.append(filename)
            
            # 检查新增的文件
            for filename in local_files:
                if filename not in remote_files:
                    changed_files.append(filename)
            
            # 检查删除的文件
            for filename in remote_files:
                if filename not in local_files:
                    os.remove(os.path.join(remote_config_dir, filename))
                    changed_files.append(f"[删除] {filename}")
            
            if not changed_files:
                log_info("没有文件变更")
                return True, ""
            
            # 复制本地配置目录到仓库
            if os.path.exists(remote_config_dir):
                shutil.rmtree(remote_config_dir)
            shutil.copytree(self.local_config_path, remote_config_dir)
            
            # 添加并提交变更（明确指定仓库目录）
            log_info(f"执行 git add 命令在目录: {repo_dir}")
            success_add, output_add = self._run_git_command(f'git add {self.config_dir}/', repo_dir)
            log_info(f"git add 结果: {success_add}, 输出: {output_add}")
            
            commit_message = f"Update config directory - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            log_info(f"执行 git commit 命令: {commit_message}")
            success_commit, output_commit = self._run_git_command(f'git commit -m "{commit_message}"', repo_dir)
            log_info(f"git commit 结果: {success_commit}, 输出: {output_commit}")
            
            # 推送到 master 分支（使用 HEAD:master 确保推送当前分支到远程 master）
            log_info(f"执行 git push 命令到远程: {self.repo_url}")
            success, output = self._run_git_command(f'git push -u {self.authenticated_url} HEAD:master', repo_dir)
            log_info(f"git push 结果: {success}, 输出: {output}")
            if not success:
                log_error(f"详细错误: {output}")
                return False, f"推送失败: {output}"
            
            log_info("配置目录推送成功")
            return True, self._format_sync_message("push", [f for f in changed_files if not f.startswith("[删除]")])
            
        except Exception as e:
            log_exception(f"推送配置失败: {e}")
            return False, f"推送失败: {str(e)}"
        
        finally:
            self._cleanup_temp_dir(temp_dir)
    
    def has_changes(self) -> bool:
        """检查本地配置是否有变更"""
        success, temp_dir, error_msg = self._clone_repo_to_temp()
        if not success:
            log_warning(f"无法检查远程变更: {error_msg}")
            return True  # 出错时假设有变更，确保数据安全
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_dir = os.path.join(repo_dir, self.config_dir)
            
            # 如果远程没有配置目录，认为有变更
            if not os.path.exists(remote_config_dir):
                return True
            
            # 比较本地和远程的索引文件
            local_index_path = os.path.join(self.local_config_path, "index.json")
            remote_index_path = os.path.join(remote_config_dir, "index.json")
            
            return self._has_file_changes(local_index_path, remote_index_path)
            
        finally:
            self._cleanup_temp_dir(temp_dir)
    
    def get_status(self) -> dict:
        """获取同步状态"""
        config_files = self._get_config_files()
        
        return {
            "local_config_exists": os.path.exists(self.local_config_path),
            "local_config_count": len(config_files),
            "auth_configured": bool(self.username or self.token),
            "repo_url": self.repo_url.replace(self.token, '***') if self.token else self.repo_url,
            "last_check": datetime.now().isoformat()
        }


def test_gitee_sync():
    """测试Gitee同步功能"""
    print("=== 测试简化版Gitee同步功能 ===")
    
    sync = GiteeSync()
    status = sync.get_status()
    print(f"状态: {status}")
    
    if not status["auth_configured"]:
        print("❌ 未配置Gitee认证信息，请检查.env文件")
        print("   需要设置: GITEE_USERNAME 和 GITEE_TOKEN")
        return
    
    # 测试拉取
    print("\n测试拉取...")
    success, message = sync.pull_configs()
    print(f"拉取结果: {success}")
    if message:
        print(f"详细信息: {message}")
    
    # 测试推送
    if success:
        print("\n测试推送...")
        success, message = sync.push_configs()
        print(f"推送结果: {success}")
        if message:
            print(f"详细信息: {message}")
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    test_gitee_sync()
