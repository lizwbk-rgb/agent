"""
会话数据库模块

使用SQLite存储会话和消息数据，支持创建、保存、加载、删除会话
"""

import sqlite3
import uuid
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path


class ConversationDB:
    """
    会话数据库管理类
    
    封装SQLite操作，提供会话和消息的CRUD操作
    """
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径，默认为项目根目录下的 data/conversations.db
        """
        if db_path is None:
            # 获取项目根目录（src的上级目录）
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "conversations.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 创建conversations表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        """)
        
        # 创建messages表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at 
            ON conversations(updated_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
            ON messages(conversation_id, timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def create_conversation(self, title: str = "新对话") -> str:
        """
        创建新会话
        
        Args:
            title: 会话标题
            
        Returns:
            str: 会话ID
        """
        conversation_id = str(uuid.uuid4())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (id, title, created_at, updated_at, message_count)
            VALUES (?, ?, ?, ?, ?)
        """, (conversation_id, title, now, now, 0))
        
        conn.commit()
        conn.close()
        
        return conversation_id
    
    def save_message(self, conversation_id: str, role: str, content: str, 
                    timestamp: datetime = None, file_path: str = None):
        """
        保存消息到数据库
        
        Args:
            conversation_id: 会话ID
            role: 角色（user/assistant/system）
            content: 消息内容
            timestamp: 时间戳
            file_path: 附件路径
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if isinstance(timestamp, datetime) else timestamp
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 插入消息
        cursor.execute("""
            INSERT INTO messages (conversation_id, role, content, timestamp, file_path)
            VALUES (?, ?, ?, ?, ?)
        """, (conversation_id, role, content, ts_str, file_path))
        
        # 更新会话的updated_at和message_count
        cursor.execute("""
            UPDATE conversations 
            SET updated_at = ?, message_count = message_count + 1
            WHERE id = ?
        """, (now_str, conversation_id))
        
        conn.commit()
        conn.close()
    
    def get_conversations(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取会话列表（按updated_at降序排序）
        
        Args:
            limit: 返回数量限制
            offset: 偏移量（用于分页）
            
        Returns:
            List[Dict]: 会话列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, created_at, updated_at, message_count
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        conversations = []
        for row in rows:
            conversations.append({
                "id": row[0],
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "message_count": row[4]
            })
        
        return conversations
    
    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        获取会话的所有消息
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            List[Dict]: 消息列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, role, content, timestamp, file_path
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        """, (conversation_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            messages.append({
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "timestamp": row[3],
                "file_path": row[4]
            })
        
        return messages
    
    def load_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        加载会话数据（包括会话信息和消息）
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            Dict: 会话数据，包含conversation和messages；如果会话不存在返回None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 获取会话信息
        cursor.execute("""
            SELECT id, title, created_at, updated_at, message_count
            FROM conversations
            WHERE id = ?
        """, (conversation_id,))
        
        conv_row = cursor.fetchone()
        if conv_row is None:
            conn.close()
            return None
        
        conversation = {
            "id": conv_row[0],
            "title": conv_row[1],
            "created_at": conv_row[2],
            "updated_at": conv_row[3],
            "message_count": conv_row[4]
        }
        
        # 获取消息
        cursor.execute("""
            SELECT id, role, content, timestamp, file_path
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        """, (conversation_id,))
        
        msg_rows = cursor.fetchall()
        messages = []
        for row in msg_rows:
            messages.append({
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "timestamp": row[3],
                "file_path": row[4]
            })
        
        conn.close()
        
        return {
            "conversation": conversation,
            "messages": messages
        }
    
    def delete_conversation(self, conversation_id: str):
        """
        删除会话（包括所有消息）
        
        Args:
            conversation_id: 会话ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 由于设置了ON DELETE CASCADE，删除会话会自动删除消息
        cursor.execute("""
            DELETE FROM conversations WHERE id = ?
        """, (conversation_id,))
        
        conn.commit()
        conn.close()
    
    def update_conversation_title(self, conversation_id: str, title: str):
        """
        更新会话标题
        
        Args:
            conversation_id: 会话ID
            title: 新标题
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE conversations SET title = ? WHERE id = ?
        """, (title, conversation_id))
        
        conn.commit()
        conn.close()
    
    def update_conversation_timestamp(self, conversation_id: str):
        """
        更新会话的updated_at时间戳（用于重新打开会话时）
        
        Args:
            conversation_id: 会话ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE conversations SET updated_at = ? WHERE id = ?
        """, (now_str, conversation_id))
        
        conn.commit()
        conn.close()
    
    def close(self):
        """关闭数据库连接（实际上sqlite3是自动管理的，这个方法主要用于兼容性）"""
        pass


# 便捷函数
def create_conversation_db(db_path: str = None) -> ConversationDB:
    """创建会话数据库实例"""
    return ConversationDB(db_path)
