"""
记忆搜索异步工作器

在后台线程中搜索相关记忆，避免在主线程中阻塞。
"""

import logging
from typing import List, Optional

from .base_worker import BaseWorker
from memory_manager import MemoryManager, Memory

logger = logging.getLogger(__name__)


class MemorySearchWorker(BaseWorker):
    """
    记忆搜索异步工作器
    
    在后台线程中搜索相关记忆，通过finished信号返回结果。
    结果格式: List[Memory] - 搜索到的记忆列表
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        query: str,
        limit: int = 5,
        parent=None
    ):
        """
        初始化记忆搜索工作器
        
        Args:
            memory_manager: 记忆管理器实例
            query: 搜索查询文本
            limit: 返回结果数量限制
            parent: 父对象
        """
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.query = query
        self.limit = limit
        
    def run(self):
        """执行记忆搜索任务"""
        try:
            self._safe_emit_progress(0, "正在搜索相关记忆...")
            
            logger.info(f"开始异步搜索记忆 - 查询: {self.query[:50]}...")
            
            if self.is_cancelled():
                logger.info("记忆搜索任务已取消")
                return
            
            # 执行搜索
            memories = self.memory_manager.search(self.query, limit=self.limit)
            
            if self.is_cancelled():
                logger.info("记忆搜索任务已取消（搜索完成后检查）")
                return
            
            self._safe_emit_progress(100, f"找到 {len(memories)} 条相关记忆")
            self._safe_emit_finished(memories)
            
            logger.info(f"记忆搜索任务完成，找到 {len(memories)} 条记忆")
            
        except Exception as e:
            error_msg = f"记忆搜索失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._safe_emit_error(error_msg)
