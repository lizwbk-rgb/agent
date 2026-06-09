"""
数据库写入异步工作器

在后台线程中执行数据库写入操作，避免在主线程中阻塞。
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .base_worker import BaseWorker
from conversation_db import ConversationDB

logger = logging.getLogger(__name__)


class DBWriteWorker(BaseWorker):
    """
    数据库写入异步工作器
    
    在后台线程中执行数据库写入操作，通过finished信号通知完成。
    支持多种数据库操作类型。
    """
    
    def __init__(
        self,
        db: ConversationDB,
        operation: str,
        data: Dict[str, Any],
        parent=None
    ):
        """
        初始化数据库写入工作器
        
        Args:
            db: 数据库实例
            operation: 操作类型，可选值:
                - 'create_conversation': 创建会话记录
                - 'save_message': 保存消息
                - 'update_conversation_title': 更新会话标题
                - 'delete_conversation': 删除会话
            data: 操作数据字典
            parent: 父对象
        """
        super().__init__(parent)
        self.db = db
        self.operation = operation
        self.data = data
        
    def run(self):
        """执行数据库写入任务"""
        try:
            self._safe_emit_progress(0, f"正在执行数据库操作: {self.operation}")
            
            logger.info(f"开始异步数据库操作: {self.operation}")
            
            if self.is_cancelled():
                logger.info("数据库写入任务已取消")
                return
            
            # 根据操作类型执行相应的数据库操作
            if self.operation == 'create_conversation':
                result = self._create_conversation()
            elif self.operation == 'save_message':
                result = self._save_message()
            elif self.operation == 'update_conversation_title':
                result = self._update_conversation_title()
            elif self.operation == 'delete_conversation':
                result = self._delete_conversation()
            else:
                raise ValueError(f"未知的操作类型: {self.operation}")
            
            if self.is_cancelled():
                logger.info("数据库写入任务已取消（操作完成后检查）")
                return
            
            self._safe_emit_progress(100, "数据库操作完成")
            self._safe_emit_finished(result)
            
            logger.info(f"数据库操作完成: {self.operation}")
            
        except Exception as e:
            error_msg = f"数据库操作失败 ({self.operation}): {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._safe_emit_error(error_msg)
    
    def _create_conversation(self) -> str:
        """创建会话记录"""
        conversation_id = self.data.get('conversation_id')
        if not conversation_id:
            raise ValueError("create_conversation操作需要conversation_id参数")
        
        self.db.create_conversation_record(conversation_id)
        logger.info(f"异步创建会话记录: {conversation_id}")
        return conversation_id
    
    def _save_message(self) -> bool:
        """保存消息"""
        conversation_id = self.data.get('conversation_id')
        role = self.data.get('role')
        content = self.data.get('content')
        timestamp = self.data.get('timestamp')
        file_path = self.data.get('file_path')
        
        if not all([conversation_id, role, content, timestamp]):
            raise ValueError("save_message操作需要conversation_id, role, content, timestamp参数")
        
        self.db.save_message(conversation_id, role, content, timestamp, file_path)
        logger.info(f"异步保存消息: {conversation_id}, {role}, {len(content)}字符")
        return True
    
    def _update_conversation_title(self) -> bool:
        """更新会话标题"""
        conversation_id = self.data.get('conversation_id')
        title = self.data.get('title')
        
        if not all([conversation_id, title]):
            raise ValueError("update_conversation_title操作需要conversation_id和title参数")
        
        self.db.update_conversation_title(conversation_id, title)
        logger.info(f"异步更新会话标题: {conversation_id} -> {title}")
        return True
    
    def _delete_conversation(self) -> bool:
        """删除会话"""
        conversation_id = self.data.get('conversation_id')
        
        if not conversation_id:
            raise ValueError("delete_conversation操作需要conversation_id参数")
        
        self.db.delete_conversation(conversation_id)
        logger.info(f"异步删除会话: {conversation_id}")
        return True
