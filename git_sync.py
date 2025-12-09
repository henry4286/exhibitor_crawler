"""
简洁的Git同步模块 - 专门用于config.xlsx文件的同步

功能：
- 启动时从远程仓库下载最新的config.xlsx
- 关闭时将本地的config.xlsx上传到远程仓库
"""

import os
import shutil
import tempfile
import hashlib
from datetime import datetime
from typing import Tuple

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import git
    from git import RemoteProgress
    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False

from unified_logger import log_info, log_error, log_warning


class GitProgress(RemoteProgress):
    """Git操作进度显示"""
    def update(self, op_code, cur_count, max_count=None, message=''):
        if message:
            log_info(f"Git进度: {message}")


class SimpleGitSync:
    """简洁的Git同步管理器"""
    
    def __init__(self):
        """初始化同步管理器"""
        self.repo_url = "https://github.com/henry4286/exhibitor_crawler"
        self.config_file = "config.xlsx"
        self.username = os.getenv('GIT_USERNAME')
        self.token = os.getenv('GIT_TOKEN')
        
        # 构建带认证的URL
        if self.username and self.token:
            self.repo_url = self.repo_url.replace('https://', f'https://{self.username}:{self.token}@')
        elif self.token:
            self.repo_url = self.repo_url.replace('https://', f'https://{self.token}@')
        
        # 使用绝对路径
        self.local_config_path = os.path.abspath(self.config_file)
        self.original_dir = os.getcwd()
    
    def _clone_repo(self) -> Tuple[bool, str, any]:
        """克隆仓库到临时目录"""
        if not GITPYTHON_AVAILABLE:
            return False, "GitPython库未安装", None
        
        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="git_sync_")
            repo_dir = os.path.join(temp_dir, "repo")
            
            log_info(f"正在克隆仓库到: {repo_dir}")
            
            # 克隆仓库
            progress = GitProgress()
            repo = git.Repo.clone_from(
                self.repo_url,
                repo_dir,
                depth=1,
                progress=progress
            )
            
            # 设置Git用户信息
            with repo.config_writer() as config:
                config.set_value('user', 'name', 'exhibitor_crawler_bot')
                config.set_value('user', 'email', 'bot@example.com')
            
            return True, temp_dir, repo
            
        except Exception as e:
            log_error(f"克隆仓库失败", exception=e)
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir, ignore_errors=True)
            return False, f"克隆失败: {str(e)}", None
    
    def _cleanup(self, temp_dir):
        """清理临时目录"""
        try:
            if temp_dir and os.path.exists(temp_dir):
                os.chdir(self.original_dir)
                shutil.rmtree(temp_dir, ignore_errors=True)
                log_info("临时文件清理完成")
        except Exception as e:
            log_warning(f"清理临时文件失败: {e}")
    
    def _backup_local_config(self) -> str:
        """备份本地配置文件，返回备份文件路径"""
        if not os.path.exists(self.local_config_path):
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(self.local_config_path), "config_backups")
        
        # 创建备份目录
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_name = f"config_backup_{timestamp}.xlsx"
        backup_path = os.path.join(backup_dir, backup_name)
        
        try:
            shutil.copy2(self.local_config_path, backup_path)
            log_info(f"本地配置已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            log_error(f"备份配置文件失败", exception=e)
            return ""
    
    def pull_config(self) -> Tuple[bool, str]:
        """从远程仓库拉取最新的config.xlsx"""
        log_info("开始拉取配置文件")
        
        # 备份本地配置文件
        backup_path = self._backup_local_config()
        if backup_path:
            log_info(f"本地配置已备份: {backup_path}")
        
        # 克隆仓库
        success, temp_dir, repo = self._clone_repo()
        if not success:
            return False, temp_dir  # temp_dir此时是错误信息
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_path = os.path.join(repo_dir, self.config_file)
            
            # 检查远程是否有config.xlsx
            if os.path.exists(remote_config_path):
                # 复制远程文件到本地
                shutil.copy2(remote_config_path, self.local_config_path)
                log_info(f"配置文件已更新: {self.local_config_path}")
                return True, f"配置文件拉取成功，备份保存至: {backup_path}" if backup_path else "配置文件拉取成功"
            else:
                # 远程没有文件，创建空的配置文件
                import pandas as pd
                empty_df = pd.DataFrame(columns=[
                    'exhibition_code', 'miniprogram_name', 'url', 'request_mode', 
                    'request_method', 'items_key', 'headers', 'params', 'data', 
                    'company_info_keys', 'url_detail', 'company_name_key', 'id_key', 
                    'headers_detail', 'params_detail', 'data_detail', 'info_key'
                ])
                empty_df.to_excel(self.local_config_path, index=False)
                log_info("创建了空的配置文件")
                return True, f"创建了新的配置文件，本地备份保存至: {backup_path}" if backup_path else "创建了新的配置文件"
                
        except Exception as e:
            log_error(f"拉取配置失败", exception=e)
            
            # 如果拉取失败且创建了备份，尝试恢复备份
            if backup_path and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, self.local_config_path)
                    log_info("已从备份恢复本地配置文件")
                except Exception as restore_e:
                    log_error(f"恢复备份失败", exception=restore_e)
            
            return False, f"拉取失败: {str(e)}"
        
        finally:
            self._cleanup(temp_dir)
    
    def push_config(self) -> Tuple[bool, str]:
        """将本地的config.xlsx推送到远程仓库"""
        log_info("开始推送配置文件")
        
        if not os.path.exists(self.local_config_path):
            return False, "本地配置文件不存在"
        
        # 克隆仓库
        success, temp_dir, repo = self._clone_repo()
        if not success:
            return False, temp_dir  # temp_dir此时是错误信息
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_path = os.path.join(repo_dir, self.config_file)
            
            # 复制本地文件到仓库
            shutil.copy2(self.local_config_path, remote_config_path)
            
            # 切换到仓库目录
            os.chdir(repo_dir)
            
            # 检查是否有变更
            if not repo.is_dirty(path=self.config_file):
                log_info("没有变更需要推送")
                return True, "没有变更需要推送"
            
            # 添加并提交文件
            repo.index.add([self.config_file])
            commit_message = f"Update config.xlsx - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            repo.index.commit(commit_message)
            
            # 推送到远程
            origin = repo.remotes.origin
            push_result = origin.push(progress=GitProgress())
            
            if push_result and len(push_result) > 0:
                push_info = push_result[0]
                if push_info.flags & push_info.ERROR:
                    return False, f"推送失败: {push_info.summary or '未知错误'}"
                else:
                    log_info("配置文件推送成功")
                    return True, "配置文件推送成功"
            else:
                return False, "推送结果为空"
                
        except Exception as e:
            log_error(f"推送配置失败", exception=e)
            return False, f"推送失败: {str(e)}"
        
        finally:
            self._cleanup(temp_dir)
    
    def _get_file_hash(self, file_path: str) -> str:
        """获取文件的MD5哈希值"""
        if not os.path.exists(file_path):
            return ""
        
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            log_error(f"计算文件哈希失败", exception=e)
            return ""
    
    def has_config_changed(self, original_hash: str = None) -> bool:
        """检查配置文件是否发生变更"""
        if not os.path.exists(self.local_config_path):
            return False
        
        current_hash = self._get_file_hash(self.local_config_path)
        
        if original_hash is None:
            # 如果没有提供原始哈希，则检查与远程是否有差异
            return self._has_remote_changes()
        
        return current_hash != original_hash
    
    def _has_remote_changes(self) -> bool:
        """检查本地配置文件与远程是否有差异"""
        if not GITPYTHON_AVAILABLE:
            log_warning("GitPython未安装，无法检查远程变更")
            return True  # 假设有变更，强制推送
        
        try:
            # 克隆仓库到临时目录
            success, temp_dir, repo = self._clone_repo()
            if not success:
                log_warning(f"无法检查远程变更: {temp_dir}")
                return True
            
            try:
                repo_dir = os.path.join(temp_dir, "repo")
                remote_config_path = os.path.join(repo_dir, self.config_file)
                
                # 如果远程没有文件，认为有变更
                if not os.path.exists(remote_config_path):
                    return True
                
                # 比较本地和远程文件的哈希值
                local_hash = self._get_file_hash(self.local_config_path)
                remote_hash = self._get_file_hash(remote_config_path)
                
                return local_hash != remote_hash
                
            finally:
                self._cleanup(temp_dir)
                
        except Exception as e:
            log_error(f"检查远程变更时发生错误", exception=e)
            return True  # 出错时假设有变更，确保数据安全
    
    def get_status(self) -> dict:
        """获取同步状态"""
        return {
            "gitpython_available": GITPYTHON_AVAILABLE,
            "local_config_exists": os.path.exists(self.local_config_path),
            "auth_configured": bool(self.username or self.token),
            "repo_url": self.repo_url.replace(self.token, '***') if self.token else self.repo_url
        }


def test_sync():
    """测试同步功能"""
    print("=== 测试Git同步功能 ===")
    
    sync = SimpleGitSync()
    status = sync.get_status()
    print(f"状态: {status}")
    
    if not status["gitpython_available"]:
        print("❌ GitPython未安装，请运行: pip install GitPython")
        return
    
    if not status["auth_configured"]:
        print("❌ 未配置Git认证信息，请检查.env文件")
        return
    
    # 测试拉取
    print("\n测试拉取...")
    success, message = sync.pull_config()
    print(f"拉取结果: {success}, {message}")
    
    # 测试推送
    if success:
        print("\n测试推送...")
        success, message = sync.push_config()
        print(f"推送结果: {success}, {message}")
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    test_sync()
