"""
Qdrant管理器

负责管理Qdrant进程的启动、停止和状态监控
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional

from config import get_config

# 配置日志
logger = logging.getLogger(__name__)


class QdrantManager:
    """
    Qdrant进程管理器
    
    负责启动、停止和监控Qdrant进程
    """
    
    def __init__(self, qdrant_exe_path: str = None):
        """
        初始化Qdrant管理器
        
        Args:
            qdrant_exe_path: qdrant.exe的路径，如果为None则自动查找
        """
        self.config = get_config()
        self.qdrant_exe_path = qdrant_exe_path or self._find_qdrant_exe()
        self.process: Optional[subprocess.Popen] = None
        
        logger.info(f"Qdrant管理器初始化 - exe路径: {self.qdrant_exe_path}")
    
    def _find_qdrant_exe(self) -> str:
        """
        自动查找qdrant.exe路径
        
        Returns:
            str: qdrant.exe的完整路径
            
        Raises:
            FileNotFoundError: 如果找不到qdrant.exe
        """
        # 可能的路径
        possible_paths = [
            # 1. 项目目录下的qdrant.exe
            Path(__file__).parent.parent / "qdrant.exe",
            # 2. 项目目录下的qdrant/qdrant.exe
            Path(__file__).parent.parent / "qdrant" / "qdrant.exe",
            # 3. 系统PATH中的qdrant
            "qdrant",
        ]
        
        for path in possible_paths:
            path = Path(path) if isinstance(path, str) else path
            if path.exists() and path.is_file():
                logger.info(f"找到qdrant.exe: {path}")
                return str(path)
        
        # 检查系统PATH
        try:
            result = subprocess.run(
                ["where", "qdrant"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                qdrant_path = result.stdout.strip().split('\n')[0]
                logger.info(f"在PATH中找到qdrant: {qdrant_path}")
                return qdrant_path
        except Exception as e:
            logger.warning(f"检查PATH中的qdrant失败: {e}")
        
        raise FileNotFoundError(
            f"找不到qdrant.exe，请确保qdrant.exe在项目目录下或已添加到PATH"
        )
    
    def is_running(self, timeout: float = 2.0) -> bool:
        """
        检查Qdrant是否正在运行
        
        Args:
            timeout: 连接超时时间（秒）
            
        Returns:
            bool: 如果Qdrant正在运行返回True
        """
        try:
            from qdrant_client import QdrantClient
            
            host = self.config.QDRANT_HOST
            port = self.config.QDRANT_PORT
            
            client = QdrantClient(host=host, port=port, timeout=timeout)
            client.get_collections()
            logger.info(f"Qdrant已运行 - {host}:{port}")
            return True
        except Exception as e:
            logger.debug(f"Qdrant未运行或无法连接: {e}")
            return False
    
    def start(self, wait_timeout: float = 30.0, process_events_callback: callable = None) -> bool:
        """
        启动Qdrant进程
        
        Args:
            wait_timeout: 等待Qdrant启动的超时时间（秒）
            process_events_callback: 等待期间调用的回调（用于处理UI事件，避免界面卡死）
            
        Returns:
            bool: 如果启动成功返回True
            
        Raises:
            FileNotFoundError: 如果qdrant.exe不存在
            RuntimeError: 如果启动失败
        """
        # 检查是否已经在运行
        if self.is_running():
            # 检查是不是我们启动的进程
            if self.process and self.process.poll() is None:
                logger.info("Qdrant已经在运行（我们启动的进程），无需重启")
                return True
            else:
                # 不是我们启动的，先停止它
                logger.info("Qdrant已在运行（其他进程），先停止它...")
                self.stop()
                # 停止后继续下面的启动流程
        
        # 检查qdrant.exe是否存在
        if not os.path.exists(self.qdrant_exe_path):
            raise FileNotFoundError(f"qdrant.exe不存在: {self.qdrant_exe_path}")
        
        # 启动Qdrant进程
        logger.info(f"启动Qdrant进程: {self.qdrant_exe_path}")
        
        # 设置工作目录为项目根目录（agent-client）
        work_dir = str(Path(self.qdrant_exe_path).parent)
        
        try:
            # 使用CREATE_NO_WINDOW标志避免在Windows上弹出控制台窗口
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            
            self.process = subprocess.Popen(
                [self.qdrant_exe_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,  # 添加stdin，避免Qdrant等待输入
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                cwd=work_dir  # 设置工作目录
            )
            
            logger.info(f"Qdrant进程已启动 - PID: {self.process.pid}, 工作目录: {work_dir}")
            
        except Exception as e:
            logger.error(f"启动Qdrant进程失败: {e}")
            raise RuntimeError(f"启动Qdrant失败: {e}")
        
        # 等待Qdrant启动完成（先等待2秒让Qdrant输出启动信息）
        time.sleep(2)
        
        # 检查进程是否还在运行
        if self.process.poll() is not None:
            # 进程已退出，读取错误信息
            try:
                stdout, stderr = self.process.communicate(timeout=5)
                stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
                stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
                logger.error(f"Qdrant进程已退出 - 返回码: {self.process.returncode}")
                logger.error(f"Qdrant stdout: {stdout_text[:500]}")
                logger.error(f"Qdrant stderr: {stderr_text[:500]}")
                raise RuntimeError(f"Qdrant启动失败，进程异常退出（返回码: {self.process.returncode}）：{stderr_text[:200]}")
            except Exception as ce:
                if "Qdrant启动失败" in str(ce):
                    raise
                logger.error(f"检查Qdrant进程状态时出错: {ce}")
        
        logger.info(f"等待Qdrant启动（超时: {wait_timeout}秒）...")
        start_time = time.time()
        
        while time.time() - start_time < wait_timeout:
            # 调用回调处理UI事件（如果提供了回调）
            if process_events_callback:
                process_events_callback()
            
            if self.is_running(timeout=1.0):
                logger.info("Qdrant启动成功")
                return True
            
            # 检查进程是否还在运行
            if self.process.poll() is not None:
                # 进程已退出
                returncode = self.process.returncode
                _, stderr = self.process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
                logger.error(f"Qdrant进程异常退出 - 返回码: {returncode}, 错误: {error_msg}")
                raise RuntimeError(f"Qdrant启动失败，进程异常退出: {error_msg}")
            
            time.sleep(0.5)
        
        # 超时
        logger.error(f"等待Qdrant启动超时（{wait_timeout}秒）")
        self.stop()  # 停止进程
        raise RuntimeError(f"Qdrant启动超时（{wait_timeout}秒）")
    
    def stop(self):
        """停止Qdrant进程"""
        if self.process is None:
            logger.debug("Qdrant进程未启动，无需停止")
            return
        
        if self.process.poll() is None:
            # 进程还在运行
            logger.info(f"停止Qdrant进程 - PID: {self.process.pid}")
            
            try:
                self.process.terminate()
                
                # 等待进程结束（最多5秒）
                try:
                    self.process.wait(timeout=5)
                    logger.info("Qdrant进程已终止")
                except subprocess.TimeoutExpired:
                    # 强制杀死进程
                    logger.warning("Qdrant进程未响应terminate，强制杀死")
                    self.process.kill()
                    self.process.wait(timeout=2)
                    logger.info("Qdrant进程已强制终止")
                    
            except Exception as e:
                logger.error(f"停止Qdrant进程时出错: {e}")
        else:
            logger.debug(f"Qdrant进程已退出 - 返回码: {self.process.returncode}")
        
        self.process = None
    
    def restart(self, wait_timeout: float = 30.0) -> bool:
        """
        重启Qdrant进程
        
        Args:
            wait_timeout: 等待启动的超时时间（秒）
            
        Returns:
            bool: 如果重启成功返回True
        """
        logger.info("重启Qdrant进程")
        self.stop()
        return self.start(wait_timeout)
    
    def get_status(self) -> dict:
        """
        获取Qdrant状态
        
        Returns:
            dict: 状态信息字典
        """
        is_running = self.is_running()
        
        status = {
            "is_running": is_running,
            "exe_path": self.qdrant_exe_path,
            "exe_exists": os.path.exists(self.qdrant_exe_path) if self.qdrant_exe_path else False,
            "process_pid": self.process.pid if self.process else None,
            "process_alive": self.process.poll() is None if self.process else False,
        }
        
        if is_running:
            try:
                from qdrant_client import QdrantClient
                
                client = QdrantClient(
                    host=self.config.QDRANT_HOST,
                    port=self.config.QDRANT_PORT,
                    timeout=2.0
                )
                
                collections = client.get_collections()
                status["collections_count"] = len(collections.collections)
                status["collections"] = [c.name for c in collections.collections]
                
            except Exception as e:
                status["error"] = str(e)
        
        return status


# 全局Qdrant管理器实例
_qdrant_manager: Optional[QdrantManager] = None


def get_qdrant_manager() -> QdrantManager:
    """
    获取全局Qdrant管理器实例（单例模式）
    
    Returns:
        QdrantManager: Qdrant管理器实例
    """
    global _qdrant_manager
    
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager()
    
    return _qdrant_manager


def start_qdrant() -> bool:
    """
    启动Qdrant（便捷函数）
    
    Returns:
        bool: 如果启动成功返回True
    """
    manager = get_qdrant_manager()
    return manager.start()


def stop_qdrant():
    """
    停止Qdrant（便捷函数）
    """
    manager = get_qdrant_manager()
    manager.stop()


def is_qdrant_running() -> bool:
    """
    检查Qdrant是否正在运行（便捷函数）
    
    Returns:
        bool: 如果Qdrant正在运行返回True
    """
    manager = get_qdrant_manager()
    return manager.is_running()


# 测试代码
if __name__ == "__main__":
    print("=" * 50)
    print("Qdrant管理器测试")
    print("=" * 50)
    
    # 创建管理器
    manager = QdrantManager()
    
    # 检查状态
    print("\n1. 检查Qdrant状态")
    status = manager.get_status()
    print(f"   运行中: {status['is_running']}")
    print(f"   exe路径: {status['exe_path']}")
    print(f"   exe存在: {status['exe_exists']}")
    
    if not status['is_running']:
        # 启动Qdrant
        print("\n2. 启动Qdrant")
        try:
            success = manager.start()
            print(f"   启动成功: {success}")
        except Exception as e:
            print(f"   启动失败: {e}")
            sys.exit(1)
        
        # 再次检查状态
        print("\n3. 检查启动后的状态")
        status = manager.get_status()
        print(f"   运行中: {status['is_running']}")
        print(f"   集合数量: {status.get('collections_count', 'N/A')}")
        print(f"   集合列表: {status.get('collections', 'N/A')}")
        
        # 停止Qdrant
        print("\n4. 停止Qdrant")
        manager.stop()
        print("   已停止")
        
        # 最终状态
        print("\n5. 检查停止后的状态")
        status = manager.get_status()
        print(f"   运行中: {status['is_running']}")
    else:
        print("   Qdrant已经在运行，跳过启动测试")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
