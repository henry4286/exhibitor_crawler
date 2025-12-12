"""
Gitee配置文件同步模块 - 专门用于JSON格式配置文件的同步

功能：
- 启动时从Gitee仓库拉取最新的config目录
- 关闭时将本地的config目录推送到Gitee仓库
- 支持JSON格式的独立配置文件管理
- 利用Git原生版本控制，支持差异合并
"""

import os
import shutil
import tempfile
import hashlib
import json
import glob
from datetime import datetime
from typing import Tuple, List, Dict, Optional

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

from unified_logger import log_info, log_error, log_warning, log_exception


class GiteeProgress(RemoteProgress):
    """Gitee操作进度显示"""
    def update(self, op_code, cur_count, max_count=None, message=''):
        if message:
            log_info(f"Gitee进度: {message}")


class GiteeSync:
    """Gitee配置文件同步管理器"""
    
    def __init__(self):
        """初始化同步管理器"""
        self.repo_url = "https://gitee.com/comeon_i/crawler.git"
        self.config_dir = "config"
        self.index_file = "index.json"
        self.username = os.getenv('GITEE_USERNAME')
        self.token = os.getenv('GITEE_TOKEN')
        
        # Gitee使用不同的认证方式，先尝试无认证URL
        self.authenticated_url = self.repo_url
        if self.token:
            # Gitee使用Personal Access Token，格式为：https://oauth2:{token}@gitee.com/user/repo.git
            self.authenticated_url = self.repo_url.replace('https://', f'https://oauth2:{self.token}@')
        elif self.username and self.token:
            self.authenticated_url = self.repo_url.replace('https://', f'https://{self.username}:{self.token}@')
        
        # 使用绝对路径
        self.local_config_path = os.path.abspath(self.config_dir)
        self.local_index_path = os.path.join(self.local_config_path, self.index_file)
        self.original_dir = os.getcwd()
        
        # 确保本地配置目录存在
        self._ensure_config_dir()
    
    def _run_command(self, cmd: str, cwd: str = None) -> Tuple[bool, str]:
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
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)
    
    def _ensure_config_dir(self):
        """确保本地配置目录存在"""
        if not os.path.exists(self.local_config_path):
            os.makedirs(self.local_config_path, exist_ok=True)
            log_info(f"创建配置目录: {self.local_config_path}")
    
    def _clone_repo(self) -> Tuple[bool, str, Optional[object]]:
        """克隆仓库到临时目录"""
        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="gitee_sync_")
            repo_dir = os.path.join(temp_dir, "repo")
            os.makedirs(repo_dir, exist_ok=True)
            
            log_info(f"正在克隆Gitee仓库到: {repo_dir}")
            
            # 使用subprocess克隆仓库，避免GitPython认证问题
            import subprocess
            success, output = self._run_command(
                f'git clone "{self.authenticated_url}" "{repo_dir}" --depth 1',
                repo_dir
            )
            
            if not success:
                return False, output, None
            
            # 如果GitPython可用，创建Repo对象
            if GITPYTHON_AVAILABLE:
                try:
                    repo = git.Repo(repo_dir)
                    # 设置Git用户信息
                    with repo.config_writer() as config:
                        config.set_value('user', 'name', 'exhibitor_crawler_bot')
                        config.set_value('user', 'email', 'bot@example.com')
                except Exception as e:
                    log_warning(f"GitPython初始化失败: {e}")
                    repo = None
            else:
                repo = None
            
            return True, temp_dir, repo
            
        except Exception as e:
            log_exception(f"克隆Gitee仓库失败: {e}")
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
    
    def _backup_local_configs(self) -> str:
        """备份本地配置目录，返回备份路径"""
        if not os.path.exists(self.local_config_path):
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(self.local_config_path), "config_backups")
        backup_path = os.path.join(backup_dir, f"config_backup_{timestamp}")
        
        try:
            shutil.copytree(self.local_config_path, backup_path)
            log_info(f"本地配置已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            log_exception(f"备份配置目录失败: {e}")
            return ""
    
    def _get_config_files(self) -> List[str]:
        """获取所有配置文件列表"""
        config_files = []
        if os.path.exists(self.local_config_path):
            for file_path in glob.glob(os.path.join(self.local_config_path, "*.json")):
                filename = os.path.basename(file_path)
                if filename != self.index_file:  # 排除索引文件
                    config_files.append(filename)
        return config_files
    
    def _update_index_file(self):
        """更新索引文件"""
        try:
            config_files = self._get_config_files()
            
            index_data = {
                "total_configs": len(config_files),
                "config_files": [],
                "last_updated": datetime.now().isoformat()
            }
            
            for filename in config_files:
                file_path = os.path.join(self.local_config_path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    index_data["config_files"].append({
                        "filename": filename,
                        "exhibition_code": config.get("exhibition_code", ""),
                        "miniprogram_name": config.get("miniprogram_name", ""),
                        "request_mode": config.get("request_mode", ""),
                        "file_size": os.path.getsize(file_path),
                        "last_modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
                except Exception as e:
                    log_warning(f"读取配置文件失败 {filename}: {e}")
                    index_data["config_files"].append({
                        "filename": filename,
                        "error": str(e)
                    })
            
            # 保存索引文件
            with open(self.local_index_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            
            log_info(f"索引文件已更新，共{len(config_files)}个配置文件")
            
        except Exception as e:
            log_exception(f"更新索引文件失败: {e}")
    
    def pull_configs(self) -> Tuple[bool, str]:
        """从Gitee仓库拉取最新的配置目录"""
        log_info("开始从Gitee拉取配置文件")
        
        # 备份本地配置
        backup_path = self._backup_local_configs()
        if backup_path:
            log_info(f"本地配置已备份: {backup_path}")
        
        # 克隆仓库
        success, temp_dir, repo = self._clone_repo()
        if not success:
            return False, temp_dir  # temp_dir此时是错误信息
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_dir = os.path.join(repo_dir, self.config_dir)
            
            if os.path.exists(remote_config_dir):
                # 复制远程配置目录到本地
                if os.path.exists(self.local_config_path):
                    shutil.rmtree(self.local_config_path)
                shutil.copytree(remote_config_dir, self.local_config_path)
                
                # 更新索引文件
                self._update_index_file()
                
                log_info(f"配置目录已更新: {self.local_config_path}")
                
                # 统计文件数量
                config_files = self._get_config_files()
                success_msg = f"配置文件拉取成功，共{len(config_files)}个配置"
                if backup_path:
                    success_msg += f"，备份保存至: {backup_path}"
                
                return True, success_msg
            else:
                # 远程没有配置目录，创建空的索引文件
                empty_index = {
                    "total_configs": 0,
                    "config_files": [],
                    "last_updated": datetime.now().isoformat(),
                    "message": "远程仓库为空，创建空的配置目录"
                }
                
                with open(self.local_index_path, 'w', encoding='utf-8') as f:
                    json.dump(empty_index, f, ensure_ascii=False, indent=2)
                
                log_info("创建了空的配置目录")
                return True, "创建了新的配置目录"
                
        except Exception as e:
            log_exception(f"拉取配置失败: {e}")
            
            # 如果拉取失败且创建了备份，尝试恢复备份
            if backup_path and os.path.exists(backup_path):
                try:
                    if os.path.exists(self.local_config_path):
                        shutil.rmtree(self.local_config_path)
                    shutil.copytree(backup_path, self.local_config_path)
                    log_info("已从备份恢复本地配置")
                except Exception as restore_e:
                    log_exception(f"恢复备份失败: {restore_e}")
            
            return False, f"拉取失败: {str(e)}"
        
        finally:
            self._cleanup(temp_dir)
    
    def push_configs(self) -> Tuple[bool, str]:
        """将本地的配置目录推送到Gitee仓库"""
        log_info("开始推送配置文件到Gitee")
        
        if not os.path.exists(self.local_config_path):
            return False, "本地配置目录不存在"
        
        # 更新索引文件
        self._update_index_file()
        
        # 克隆仓库
        success, temp_dir, repo = self._clone_repo()
        if not success:
            return False, temp_dir  # temp_dir此时是错误信息
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_dir = os.path.join(repo_dir, self.config_dir)
            
            # 切换到仓库目录
            os.chdir(repo_dir)
            
            # 获取本地配置文件列表
            local_config_files = set(self._get_config_files())
            
            # 获取远程配置文件列表（如果存在）
            remote_config_files = set()
            if os.path.exists(remote_config_dir):
                for file_path in glob.glob(os.path.join(remote_config_dir, "*.json")):
                    filename = os.path.basename(file_path)
                    if filename != self.index_file:  # 排除索引文件
                        remote_config_files.add(filename)
            
            # 删除远程存在但本地不存在的文件
            files_to_delete = remote_config_files - local_config_files
            if files_to_delete:
                log_info(f"需要删除的远程文件: {files_to_delete}")
                for filename in files_to_delete:
                    remote_file_path = os.path.join(remote_config_dir, filename)
                    if os.path.exists(remote_file_path):
                        os.remove(remote_file_path)
                        log_info(f"删除远程文件: {filename}")
                        # 从Git索引中删除
                        repo.index.remove([os.path.join(self.config_dir, filename)])
            
            # 复制本地配置目录到仓库
            if os.path.exists(remote_config_dir):
                shutil.rmtree(remote_config_dir)
            shutil.copytree(self.local_config_path, remote_config_dir)
            
            # 添加所有文件（包括新增和修改的）
            repo.index.add([self.config_dir])
            
            # 检查是否有变更
            if repo and hasattr(repo, 'is_dirty') and not repo.is_dirty(untracked_files=True):
                log_info("没有变更需要推送")
                return True, "没有变更需要推送"
            
            # 提交变更
            config_files = self._get_config_files()
            deleted_count = len(files_to_delete)
            commit_message = f"Update config directory - {len(config_files)} configs"
            if deleted_count > 0:
                commit_message += f", deleted {deleted_count} files"
            commit_message += f" - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            repo.index.commit(commit_message)
            
            # 推送到远程
            origin = repo.remotes.origin
            push_result = origin.push(progress=GiteeProgress())
            
            if push_result and len(push_result) > 0:
                push_info = push_result[0]
                if push_info.flags & push_info.ERROR:
                    return False, f"推送失败: {push_info.summary or '未知错误'}"
                else:
                    log_info("配置目录推送成功")
                    success_msg = f"配置目录推送成功，共{len(config_files)}个配置文件"
                    if deleted_count > 0:
                        success_msg += f"，删除了{deleted_count}个文件"
                    return True, success_msg
            else:
                return False, "推送结果为空"
                
        except Exception as e:
            log_exception(f"推送配置失败: {e}")
            return False, f"推送失败: {str(e)}"
        
        finally:
            self._cleanup(temp_dir)
    
    def pull_single_config(self, config_name: str) -> Tuple[bool, str]:
        """拉取单个配置文件"""
        log_info(f"拉取单个配置文件: {config_name}")
        
        # 克隆仓库
        success, temp_dir, repo = self._clone_repo()
        if not success:
            return False, temp_dir
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_path = os.path.join(repo_dir, self.config_dir, f"{config_name}.json")
            
            if os.path.exists(remote_config_path):
                # 复制单个文件
                local_config_path = os.path.join(self.local_config_path, f"{config_name}.json")
                shutil.copy2(remote_config_path, local_config_path)
                
                # 更新索引文件
                self._update_index_file()
                
                log_info(f"配置文件 {config_name} 拉取成功")
                return True, f"配置文件 {config_name} 拉取成功"
            else:
                return False, f"远程不存在配置文件: {config_name}"
                
        except Exception as e:
            log_exception(f"拉取单个配置失败: {e}")
            return False, f"拉取失败: {str(e)}"
        
        finally:
            self._cleanup(temp_dir)
    
    def push_single_config(self, config_name: str) -> Tuple[bool, str]:
        """推送单个配置文件"""
        log_info(f"推送单个配置文件: {config_name}")
        
        local_config_path = os.path.join(self.local_config_path, f"{config_name}.json")
        if not os.path.exists(local_config_path):
            return False, f"本地不存在配置文件: {config_name}"
        
        # 克隆仓库
        success, temp_dir, repo = self._clone_repo()
        if not success:
            return False, temp_dir
        
        try:
            repo_dir = os.path.join(temp_dir, "repo")
            remote_config_dir = os.path.join(repo_dir, self.config_dir)
            
            # 确保远程配置目录存在
            os.makedirs(remote_config_dir, exist_ok=True)
            
            # 复制单个文件
            remote_config_path = os.path.join(remote_config_dir, f"{config_name}.json")
            shutil.copy2(local_config_path, remote_config_path)
            
            # 切换到仓库目录
            os.chdir(repo_dir)
            
            # 添加并提交文件
            repo.index.add([os.path.join(self.config_dir, f"{config_name}.json")])
            commit_message = f"Update {config_name}.json - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            repo.index.commit(commit_message)
            
            # 推送到远程
            origin = repo.remotes.origin
            push_result = origin.push(progress=GiteeProgress())
            
            if push_result and len(push_result) > 0:
                push_info = push_result[0]
                if push_info.flags & push_info.ERROR:
                    return False, f"推送失败: {push_info.summary or '未知错误'}"
                else:
                    log_info(f"配置文件 {config_name} 推送成功")
                    return True, f"配置文件 {config_name} 推送成功"
            else:
                return False, "推送结果为空"
                
        except Exception as e:
            log_exception(f"推送单个配置失败: {e}")
            return False, f"推送失败: {str(e)}"
        
        finally:
            self._cleanup(temp_dir)
    
    def has_changes(self) -> bool:
        """检查本地配置是否有变更"""
        try:
            # 克隆仓库到临时目录
            success, temp_dir, repo = self._clone_repo()
            if not success:
                log_warning(f"无法检查远程变更: {temp_dir}")
                return True  # 出错时假设有变更，确保数据安全
            
            try:
                repo_dir = os.path.join(temp_dir, "repo")
                remote_config_dir = os.path.join(repo_dir, self.config_dir)
                
                # 如果远程没有配置目录，认为有变更
                if not os.path.exists(remote_config_dir):
                    self._cleanup(temp_dir)
                    return True
                
                # 比较本地和远程的索引文件
                local_index_path = os.path.join(self.local_config_path, self.index_file)
                remote_index_path = os.path.join(remote_config_dir, self.index_file)
                
                if not os.path.exists(local_index_path):
                    self._cleanup(temp_dir)
                    return True
                
                if not os.path.exists(remote_index_path):
                    self._cleanup(temp_dir)
                    return True
                
                # 计算哈希值比较
                local_hash = self._get_file_hash(local_index_path)
                remote_hash = self._get_file_hash(remote_index_path)
                
                return local_hash != remote_hash
                
            finally:
                self._cleanup(temp_dir)
                
        except Exception as e:
            log_exception(f"检查变更时发生错误: {e}")
            return True  # 出错时假设有变更，确保数据安全
    
    def _get_file_hash(self, file_path: str) -> str:
        """获取文件的MD5哈希值"""
        if not os.path.exists(file_path):
            return ""
        
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            log_exception(f"计算文件哈希失败: {e}")
            return ""
    
    def get_status(self) -> Dict:
        """获取同步状态"""
        config_files = self._get_config_files()
        
        return {
            "gitpython_available": GITPYTHON_AVAILABLE,
            "local_config_exists": os.path.exists(self.local_config_path),
            "local_config_count": len(config_files),
            "auth_configured": bool(self.username or self.token),
            "repo_url": self.repo_url.replace(self.token, '***') if self.token else self.repo_url,
            "last_check": datetime.now().isoformat()
        }


def test_gitee_sync():
    """测试Gitee同步功能"""
    print("=== 测试Gitee同步功能 ===")
    
    sync = GiteeSync()
    status = sync.get_status()
    print(f"状态: {status}")
    
    if not status["gitpython_available"]:
        print("❌ GitPython未安装，请运行: pip install GitPython")
        return
    
    if not status["auth_configured"]:
        print("❌ 未配置Gitee认证信息，请检查.env文件")
        print("   需要设置: GITEE_USERNAME 和 GITEE_TOKEN")
        return
    
    # 测试拉取
    print("\n测试拉取...")
    success, message = sync.pull_configs()
    print(f"拉取结果: {success}, {message}")
    
    # 测试推送
    if success:
        print("\n测试推送...")
        success, message = sync.push_configs()
        print(f"推送结果: {success}, {message}")
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    test_gitee_sync()
