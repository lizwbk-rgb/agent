"""
记忆加载异步工作器

在后台线程中加载所有记忆，避免在主线程中阻塞。
"""

import logging
from typing import List

from .base_worker import BaseWorker
from memory_manager import MemoryManager, Memory

logger = logging.getLogger(__name__)


class MemoryLoadWorker(BaseWorker):
    """
    记忆加载异步工作器
    
    在后台线程中加载所有记忆，通过finished信号返回结果。
    结果格式: List[Memory] - 所有记忆列表
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        parent=None
    ):
        """
        初始化记忆加载工作器
        
        Args:
            memory_manager: 记忆管理器实例
            parent: 父对象
        """
        super().__init__(parent)
        self.memory_manager = memory_manager
        
    def run(self):
        """执行记忆加载任务"""
        try:
            self._safe_emit_progress(0, "正在加载记忆...")
            
            logger.info("开始异步加载记忆")
            
            if self.is_cancelled():
                logger.info("记忆加载任务已取消")
                return
            
            # 执行加载
            memories = self.memory_manager.get_all()
            
            if self.is_cancelled():
                logger.info("记忆加载任务已取消（加载完成后检查）")
                return
            
            self._safe_emit_progress(100, f"加载完成，共 {len(memories)} 条记忆")
            self._safe_emit_finished(memories)
            
            logger.info(f"记忆加载任务完成，加载了 {len(memories)} 条记忆")
            
        except Exception as e:
            error_msg = f"记忆加载失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._safe_emit_error(error_msg)
