"""
记忆管理模块

封装mem0记忆引擎，提供记忆的CRUD操作
支持向量检索、记忆修改、格式化显示等功能
"""

import os
import json
import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from config import Config, get_config
from utils.helpers import truncate_text

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """记忆数据类"""
    id: str
    content: str
    user_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    score: float = 0.0  # 检索相关性分数
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "score": self.score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """从字典创建，兼容多种格式（直接格式或Qdrant payload格式）"""
        # 处理Qdrant格式：{'id': ..., 'payload': {'memory': ..., 'user_id': ...}}
        if 'payload' in data:
            payload = data['payload']
            memory_id = data.get('id', '')
            return cls.from_dict(payload)  # 递归处理payload
        
        # 处理时间字段
        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except ValueError:
                pass
        
        updated_at = None
        if data.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(data["updated_at"])
            except ValueError:
                pass
        
        return cls(
            id=data.get("id", ""),
            content=data.get("content", data.get("memory", "")),
            user_id=data.get("user_id", ""),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
            score=data.get("score", 0.0)
        )
    
    def format_display(self, include_score: bool = True) -> str:
        """格式化为显示文本"""
        if include_score and self.score > 0:
            return f"[{self.id}] (相关度: {self.score:.2f})\n{self.content}"
        return f"[{self.id}]\n{self.content}"


class BaseMemoryStore(ABC):
    """记忆存储基类"""
    
    @abstractmethod
    def add(self, memory: Memory) -> str:
        """添加记忆"""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[Memory]:
        """搜索记忆"""
        pass
    
    @abstractmethod
    def get(self, memory_id: str) -> Optional[Memory]:
        """获取记忆"""
        pass
    
    @abstractmethod
    def update(self, memory_id: str, content: str) -> bool:
        """更新记忆"""
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        pass
    
    @abstractmethod
    def clear(self, user_id: str) -> bool:
        """清空记忆"""
        pass
    
    @abstractmethod
    def get_all(self, user_id: str) -> List[Memory]:
        """获取所有记忆"""
        pass


class LocalMemoryStore(BaseMemoryStore):
    """本地文件记忆存储（备用方案）"""
    
    def __init__(self, data_dir: str = "data"):
        """
        初始化本地存储
        
        Args:
            data_dir: 数据目录
        """
        self.data_dir = data_dir
        self.memories_file = os.path.join(data_dir, "memories.json")
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 加载现有记忆
        self.memories: Dict[str, List[Dict[str, Any]]] = self._load_memories()
        
        logger.info(f"本地记忆存储初始化完成: {self.memories_file}")
    
    def _load_memories(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载记忆数据"""
        if os.path.exists(self.memories_file):
            try:
                with open(self.memories_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"加载记忆失败: {str(e)}，创建新文件")
        return {}
    
    def _save_memories(self):
        """保存记忆数据"""
        try:
            with open(self.memories_file, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"保存记忆失败: {str(e)}")
    
    def _generate_id(self, content: str) -> str:
        """生成记忆ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"mem_{timestamp}_{content_hash}"
    
    def add(self, memory: Memory) -> str:
        """添加记忆"""
        if memory.user_id not in self.memories:
            self.memories[memory.user_id] = []
        
        self.memories[memory.user_id].append({
            "id": memory.id,
            "content": memory.content,
            "metadata": memory.metadata,
            "created_at": memory.created_at.isoformat() if memory.created_at else datetime.now().isoformat(),
            "updated_at": memory.updated_at.isoformat() if memory.updated_at else datetime.now().isoformat()
        })
        
        self._save_memories()
        logger.info(f"添加记忆: {memory.id}")
        return memory.id
    
    def search(self, query: str, limit: int = 10, user_id: str = None, filters: dict = None) -> List[Memory]:
        """
        搜索记忆（简单文本匹配）
        
        Args:
            query: 查询文本
            limit: 返回数量限制
            user_id: 用户ID（已弃用，请使用filters参数）
            filters: 过滤条件，可包含user_id等字段
            
        Returns:
            List[Memory]: 按相关性排序的记忆列表
        """
        # 从filters参数中提取user_id（优先），如果没有则使用user_id参数
        if filters and 'user_id' in filters:
            user_id = filters['user_id']
        
        user_id = user_id or "default_user"
        memories = self.memories.get(user_id, [])
        
        if not memories:
            return []
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # 计算每个记忆的相关性分数
        scored_memories = []
        for mem_data in memories:
            content_lower = mem_data.get("content", "").lower()
            content_words = set(content_lower.split())
            
            # 计算词重叠
            overlap = len(query_words & content_words)
            score = overlap / len(query_words) if query_words else 0
            
            if score > 0 or query_lower in content_lower:
                mem_data["score"] = score
                scored_memories.append(mem_data)
        
        # 按分数排序
        scored_memories.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # 转换为Memory对象
        return [Memory.from_dict(mem) for mem in scored_memories[:limit]]
    
    def get(self, memory_id: str, user_id: str = None) -> Optional[Memory]:
        """获取记忆"""
        user_id = user_id or "default_user"
        memories = self.memories.get(user_id, [])
        
        for mem_data in memories:
            if mem_data.get("id") == memory_id:
                return Memory.from_dict(mem_data)
        
        return None
    
    def update(self, memory_id: str, content: str, user_id: str = None) -> bool:
        """更新记忆"""
        user_id = user_id or "default_user"
        memories = self.memories.get(user_id, [])
        
        for mem_data in memories:
            if mem_data.get("id") == memory_id:
                mem_data["content"] = content
                mem_data["updated_at"] = datetime.now().isoformat()
                self._save_memories()
                logger.info(f"更新记忆: {memory_id}")
                return True
        
        logger.warning(f"记忆不存在: {memory_id}")
        return False
    
    def delete(self, memory_id: str, user_id: str = None) -> bool:
        """删除记忆"""
        user_id = user_id or "default_user"
        memories = self.memories.get(user_id, [])
        
        original_count = len(memories)
        self.memories[user_id] = [
            mem for mem in memories if mem.get("id") != memory_id
        ]
        
        if len(self.memories[user_id]) < original_count:
            self._save_memories()
            logger.info(f"删除记忆: {memory_id}")
            return True
        
        logger.warning(f"记忆不存在: {memory_id}")
        return False
    
    def clear(self, user_id: str = None) -> bool:
        """清空记忆"""
        user_id = user_id or "default_user"
        
        if user_id in self.memories:
            count = len(self.memories[user_id])
            del self.memories[user_id]
            self._save_memories()
            logger.info(f"清空用户 {user_id} 的 {count} 条记忆")
            return True
        
        return True
    
    def get_all(self, user_id: str = None) -> List[Memory]:
        """
        获取所有记忆（按ID倒序）
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Memory]: 按ID倒序排列的记忆列表
        """
        user_id = user_id or "default_user"
        memories = self.memories.get(user_id, [])
        
        # 按ID倒序排列（ID包含时间戳，所以倒序即最新优先）
        memories.sort(key=lambda x: x.get("id", ""), reverse=True)
        
        return [Memory.from_dict(mem) for mem in memories]


class MemoryManager:
    """
    记忆管理器
    
    封装mem0或本地存储，提供统一的记忆管理接口
    """
    
    def __init__(
        self,
        user_id: str = None,
        use_mem0: bool = True,
        data_dir: str = "data"
    ):
        """
        初始化记忆管理器
        
        Args:
            user_id: 用户ID
            use_mem0: 是否使用mem0（如果不可用则回退到本地存储）
            data_dir: 本地存储数据目录
        """
        self.user_id = user_id or get_config().USER_ID
        self.data_dir = data_dir
        self.use_mem0 = use_mem0 and self._check_mem0_available()
        
        if self.use_mem0:
            self.store = self._init_mem0_store()
            logger.info("使用mem0记忆存储")
        else:
            self.store = LocalMemoryStore(data_dir)
            logger.info("使用本地记忆存储")
    
    def _check_mem0_available(self) -> bool:
        """检查mem0是否可用"""
        try:
            import mem0
            return True
        except ImportError:
            logger.info("mem0未安装，将使用本地存储")
            return False
    
    def _init_mem0_store(self):
        """初始化mem0存储"""
        try:
            from mem0 import Memory as Mem0Memory
            
            # 获取mem0配置
            mem0_config = Config.get_mem0_config()
            
            # 在mem0初始化前，先确保Qdrant集合存在且维度正确
            self._ensure_qdrant_collection(mem0_config)
            
            # 初始化mem0（使用from_config方法）
            return Mem0Memory.from_config(mem0_config)
            
        except Exception as e:
            logger.warning(f"mem0初始化失败: {str(e)}，回退到本地存储")
            return LocalMemoryStore(self.data_dir)
    
    def _ensure_qdrant_collection(self, mem0_config: dict):
        """确保Qdrant集合存在且维度正确（手动创建，避免mem0使用错误维度）"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client import models
            
            vector_store_config = mem0_config.get('vector_store', {}).get('config', {})
            host = vector_store_config.get('host', 'localhost')
            port = vector_store_config.get('port', 6333)
            collection_name = vector_store_config.get('collection_name', 'mem0')
            
            # 预期维度（根据embedder配置）
            expected_dims = 384  # all-MiniLM-L6-v2的维度
            
            client = QdrantClient(host=host, port=port, timeout=5)
            
            # 检查集合是否存在
            try:
                collection_info = client.get_collection(collection_name)
                current_dims = collection_info.config.params.vectors.size
                
                if current_dims != expected_dims:
                    logger.warning(f"集合 {collection_name} 维度不匹配: 期望{expected_dims}, 实际{current_dims}, 删除并手动重建")
                    client.delete_collection(collection_name)
                    # 手动创建正确维度的集合
                    self._create_collection_with_correct_dims(client, collection_name, expected_dims)
                else:
                    logger.info(f"集合 {collection_name} 维度正确: {current_dims}")
            except Exception:
                # 集合不存在，手动创建
                logger.info(f"集合 {collection_name} 不存在，手动创建（维度: {expected_dims}）")
                self._create_collection_with_correct_dims(client, collection_name, expected_dims)
                
        except Exception as e:
            logger.warning(f"检查Qdrant集合时出错: {e}")
    
    def _create_collection_with_correct_dims(self, client, collection_name: str, dims: int):
        """创建指定维度的Qdrant集合"""
        try:
            from qdrant_client import models
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=dims,
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"已创建集合 {collection_name}，维度: {dims}")
        except Exception as e:
            logger.warning(f"创建集合 {collection_name} 失败: {e}")
    
    
    # ==================== 记忆操作 ====================
    
    def add(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            metadata: 附加元数据
            
        Returns:
            str: 记忆ID
        """
        memory = Memory(
            id=self.store._generate_id(content) if hasattr(self.store, '_generate_id') else f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            content=content,
            user_id=self.user_id,
            metadata=metadata or {}
        )
        
        return self.store.add(memory)
    
    def search(self, query: str, limit: int = 10, retry_on_error: bool = True) -> List[Memory]:
        """
        搜索记忆
        
        Args:
            query: 查询文本
            limit: 返回数量限制
            retry_on_error: 遇到错误时是否重试
            
        Returns:
            List[Memory]: 按相关性排序的记忆列表
        """
        try:
            # 尝试使用filters参数（mem0新版本）
            results = self.store.search(query, limit=limit, filters={'user_id': self.user_id})
        except TypeError:
            try:
                # 兼容旧版本（user_id作为顶层参数）
                results = self.store.search(query, limit=limit, user_id=self.user_id)
            except TypeError:
                # 兼容LocalMemoryStore（不支持filters参数和user_id参数）
                results = self.store.search(query, limit, self.user_id)
        except ValueError as e:
            # 捕获向量维度不匹配等错误
            error_msg = str(e)
            if "not aligned" in error_msg or "dimension" in error_msg.lower():
                logger.error(f"向量维度不匹配错误: {error_msg}")
                logger.error("请检查Qdrant集合的向量维度是否与当前模型匹配，或手动删除并重新创建集合。")
                # 返回空列表，避免崩溃
                return []
            else:
                # 重新抛出其他ValueError
                raise
        
        # 将结果转换为Memory对象列表
        return self._convert_to_memories(results)
    
    def _convert_to_memories(self, results) -> List[Memory]:
        """
        将搜索结果转换为Memory对象列表
        
        Args:
            results: mem0返回的原始数据
            
        Returns:
            List[Memory]: Memory对象列表
        """
        logger.info(f"[DEBUG] _convert_to_memories() 开始: type={type(results)}, len={len(results) if results else 'None'}")
        
        if not results:
            logger.info(f"[DEBUG] results为空")
            return []
        
        if isinstance(results, list):
            memories = []
            for i, item in enumerate(results):
                logger.info(f"[DEBUG] 处理第{i}项: type={type(item)}, value={str(item)[:200]}")
                if isinstance(item, Memory):
                    memories.append(item)
                    logger.info(f"[DEBUG] 第{i}项是Memory对象: id={item.id}")
                elif isinstance(item, dict):
                    try:
                        mem = Memory.from_dict(item)
                        memories.append(mem)
                        logger.info(f"[DEBUG] 第{i}项转换为Memory: id={mem.id}, content={mem.content[:50]}")
                    except Exception as e:
                        logger.warning(f"[DEBUG] 转换记忆失败: {e}, item keys={list(item.keys()) if isinstance(item, dict) else 'N/A'}")
                elif isinstance(item, str):
                    logger.warning(f"[DEBUG] 记忆数据为字符串，跳过: {item[:100]}")
                else:
                    logger.warning(f"[DEBUG] 未知的记忆数据类型: {type(item)}")
            logger.info(f"[DEBUG] _convert_to_memories() 完成: 返回{len(memories)}条记忆")
            return memories
        elif isinstance(results, dict):
            # mem0可能返回单个字典
            logger.info(f"[DEBUG] results是dict: keys={list(results.keys())[:10]}")
            try:
                mem = Memory.from_dict(results)
                logger.info(f"[DEBUG] 转换为Memory: id={mem.id}")
                return [mem]
            except Exception as e:
                logger.warning(f"[DEBUG] 转换记忆失败: {e}")
                return []
        
        logger.warning(f"[DEBUG] results类型不支持: {type(results)}")
        return []
    
    def get(self, memory_id: str) -> Optional[Memory]:
        """
        获取记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            Memory: 记忆对象，不存在返回None
        """
        try:
            # 尝试不带user_id参数调用（mem0新版本）
            return self.store.get(memory_id)
        except TypeError:
            try:
                # 兼容旧版本（带user_id参数）
                return self.store.get(memory_id, user_id=self.user_id)
            except TypeError:
                # 兼容LocalMemoryStore（带user_id位置参数）
                return self.store.get(memory_id, self.user_id)
    
    def update(self, memory_id: str, content: str) -> bool:
        """
        更新记忆
        
        Args:
            memory_id: 记忆ID
            content: 新内容
            
        Returns:
            bool: 是否成功
        """
        try:
            # 尝试不带user_id参数调用（mem0新版本）
            return self.store.update(memory_id, content)
        except TypeError:
            try:
                # 兼容旧版本（带user_id参数）
                return self.store.update(memory_id, content, user_id=self.user_id)
            except TypeError:
                # 兼容LocalMemoryStore（带user_id位置参数）
                return self.store.update(memory_id, content, self.user_id)
    
    def delete(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # 尝试不带user_id参数调用（mem0新版本）
            return self.store.delete(memory_id)
        except TypeError:
            try:
                # 兼容旧版本（带user_id参数）
                return self.store.delete(memory_id, user_id=self.user_id)
            except TypeError:
                # 兼容LocalMemoryStore（带user_id位置参数）
                return self.store.delete(memory_id, self.user_id)
    
    def clear(self) -> bool:
        """
        清空所有记忆
        
        Returns:
            bool: 是否成功
        """
        try:
            # 尝试不带user_id参数调用（mem0新版本）
            return self.store.clear()
        except TypeError:
            try:
                # 兼容旧版本（带user_id参数）
                return self.store.clear(user_id=self.user_id)
            except TypeError:
                # 兼容LocalMemoryStore（带user_id位置参数）
                return self.store.clear(self.user_id)
    
    def get_all(self) -> List[Memory]:
        """
        获取所有记忆（按ID倒序）
        
        Returns:
            List[Memory]: 记忆列表，按ID倒序排列
        """
        logger.info(f"[DEBUG] get_all() 开始，user_id={self.user_id}")
        results = None
        
        try:
            # 尝试使用filters参数（mem0新版本）
            logger.info(f"[DEBUG] 尝试 store.get_all(filters={{'user_id': ...}})")
            results = self.store.get_all(filters={'user_id': self.user_id})
            logger.info(f"[DEBUG] store.get_all(filters) 返回: type={type(results)}, len={len(results) if results else 'None'}")
        except TypeError as e:
            logger.warning(f"[DEBUG] TypeError: {e}，尝试旧版本")
            try:
                # 兼容旧版本（带user_id参数）
                logger.info(f"[DEBUG] 尝试 store.get_all(user_id=...)")
                results = self.store.get_all(user_id=self.user_id)
                logger.info(f"[DEBUG] store.get_all(user_id) 返回: type={type(results)}, len={len(results) if results else 'None'}")
            except TypeError as e2:
                logger.warning(f"[DEBUG] TypeError2: {e2}，尝试位置参数")
                try:
                    # 兼容LocalMemoryStore（带user_id位置参数）
                    logger.info(f"[DEBUG] 尝试 store.get_all(位置参数)")
                    results = self.store.get_all(self.user_id)
                    logger.info(f"[DEBUG] store.get_all(位置) 返回: type={type(results)}, len={len(results) if results else 'None'}")
                except Exception as e3:
                    logger.error(f"[DEBUG] 所有调用都失败: {e3}")
                    return []
        
        # 打印原始结果用于调试
        if results:
            logger.info(f"[DEBUG] 原始结果: {results}")
        
        # 处理不同类型的返回结果
        # Qdrant store.get_all(filters) 返回格式: {'results': [{'id': ..., 'payload': {...}}, ...]}
        if results and isinstance(results, dict) and 'results' in results:
            results = results['results']
            logger.info(f"[DEBUG] 从dict提取results: type={type(results)}, len={len(results)}")
        
        # 将结果转换为Memory对象列表
        if results and isinstance(results, list):
            memories = []
            for i, item in enumerate(results):
                logger.info(f"[DEBUG] 处理第{i}项: type={type(item)}, value={str(item)[:200]}")
                if isinstance(item, Memory):
                    memories.append(item)
                    logger.info(f"[DEBUG] 第{i}项是Memory对象")
                elif isinstance(item, dict):
                    try:
                        # Qdrant返回格式: {'id': ..., 'payload': {'memory': ..., 'user_id': ..., ...}}
                        if 'payload' in item:
                            payload = item['payload']
                            mem = Memory.from_dict(payload)
                        else:
                            mem = Memory.from_dict(item)
                        memories.append(mem)
                        logger.info(f"[DEBUG] 第{i}项转换为Memory: id={mem.id}")
                    except Exception as e:
                        logger.warning(f"[DEBUG] 转换记忆失败: {e}, item: {item}")
                elif isinstance(item, str):
                    logger.warning(f"[DEBUG] 记忆数据为字符串，跳过: {item[:100]}")
                else:
                    logger.warning(f"[DEBUG] 未知的记忆数据类型: {type(item)}")
            logger.info(f"[DEBUG] get_all() 完成，返回 {len(memories)} 条记忆")
            return memories
        else:
            if results:
                logger.warning(f"[DEBUG] results不是list或为空: type={type(results)}, value={results}")
        
        return []
    
    # ==================== 便捷方法 ====================
    
    def add_conversation_memory(
        self,
        user_message: str,
        assistant_message: str,
        topic: str = None
    ) -> str:
        """
        添加对话记忆
        
        Args:
            user_message: 用户消息
            assistant_message: AI回复
            topic: 话题标签
            
        Returns:
            str: 记忆ID
        """
        content = f"用户: {user_message}\nAI: {assistant_message}"
        
        metadata = {}
        if topic:
            metadata["topic"] = topic
        metadata["type"] = "conversation"
        
        return self.add(content, metadata)
    
    def add_user_info(self, info: str, category: str = "general") -> str:
        """
        添加用户信息记忆
        
        Args:
            info: 用户信息
            category: 分类（general, preference, fact等）
            
        Returns:
            str: 记忆ID
        """
        metadata = {"type": "user_info", "category": category}
        return self.add(info, metadata)
    
    def search_related(self, query: str, max_results: int = 5) -> str:
        """
        搜索相关记忆并格式化输出
        
        Args:
            query: 查询文本
            max_results: 最大结果数
            
        Returns:
            str: 格式化的记忆文本
        """
        memories = self.search(query, limit=max_results)
        
        if not memories:
            return ""
        
        return self.format_memories_for_display(memories)
    
    # ==================== 格式化方法 ====================
    
    def format_memories_for_display(
        self,
        memories: List[Memory],
        include_score: bool = True,
        max_content_length: int = 200
    ) -> str:
        """
        格式化记忆列表用于显示
        
        Args:
            memories: 记忆列表
            include_score: 是否包含相关性分数
            max_content_length: 最大内容长度
            
        Returns:
            str: 格式化的文本
        """
        if not memories:
            return ""
        
        lines = []
        for mem in memories:
            # 截断内容
            content = truncate_text(mem.content, max_content_length)
            
            # 格式化单条记忆
            if include_score and mem.score > 0:
                lines.append(f"[{mem.id}] (相关度: {mem.score:.2f})")
                lines.append(content)
            else:
                lines.append(f"[{mem.id}]")
                lines.append(content)
            
            lines.append("")  # 空行分隔
        
        return "\n".join(lines)
    
    def format_memories_for_context(
        self,
        memories: List[Memory],
        max_length: int = 2000
    ) -> str:
        """
        格式化记忆用于对话上下文
        
        Args:
            memories: 记忆列表
            max_length: 最大长度
            
        Returns:
            str: 格式化的上下文文本
        """
        if not memories:
            return ""
        
        parts = ["以下是与当前对话相关的记忆信息：\n"]
        
        current_length = len("".join(parts))
        
        for mem in memories:
            # 构建记忆文本
            mem_text = f"- [{mem.id}]: {mem.content}\n"
            
            if current_length + len(mem_text) <= max_length:
                parts.append(mem_text)
                current_length += len(mem_text)
            else:
                # 空间不足，停止添加
                break
        
        return "".join(parts)
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """
        获取记忆摘要
        
        Returns:
            Dict: 记忆统计信息
        """
        all_memories = self.get_all()
        
        # 统计分类
        categories = {}
        types = {}
        
        for mem in all_memories:
            # 统计类型
            mem_type = mem.metadata.get("type", "unknown")
            types[mem_type] = types.get(mem_type, 0) + 1
            
            # 统计分类
            if mem_type == "user_info":
                category = mem.metadata.get("category", "general")
                categories[category] = categories.get(category, 0) + 1
        
        return {
            "total_count": len(all_memories),
            "types": types,
            "categories": categories
        }


# 便捷函数
def get_memory_manager(user_id: str = None) -> MemoryManager:
    """获取记忆管理器实例"""
    return MemoryManager(user_id=user_id)


def quick_add_memory(content: str, user_id: str = None) -> str:
    """快速添加记忆"""
    manager = get_memory_manager(user_id)
    return manager.add(content)


def quick_search_memory(query: str, user_id: str = None, limit: int = 10) -> List[Memory]:
    """快速搜索记忆"""
    manager = get_memory_manager(user_id)
    return manager.search(query, limit=limit)


# 测试代码
if __name__ == "__main__":
    print("=" * 50)
    print("记忆管理模块测试")
    print("=" * 50)
    
    # 创建记忆管理器
    manager = MemoryManager(use_mem0=False)  # 使用本地存储进行测试
    
    # 添加记忆
    print("\n1. 添加记忆")
    mem1_id = manager.add("用户喜欢Python编程", {"type": "user_info", "category": "preference"})
    print(f"  记忆1 ID: {mem1_id}")
    
    mem2_id = manager.add("用户的工作单位是腾讯", {"type": "user_info", "category": "fact"})
    print(f"  记忆2 ID: {mem2_id}")
    
    mem3_id = manager.add_conversation_memory(
        "如何学习Python？",
        "建议从基础语法开始，多做练习项目。",
        "学习建议"
    )
    print(f"  对话记忆 ID: {mem3_id}")
    
    # 获取所有记忆
    print("\n2. 获取所有记忆")
    all_memories = manager.get_all()
    print(f"  总数: {len(all_memories)}")
    for mem in all_memories:
        print(f"  - {mem.id}: {truncate_text(mem.content, 50)}")
    
    # 搜索记忆
    print("\n3. 搜索记忆")
    results = manager.search("Python", limit=5)
    print(f"  找到 {len(results)} 条相关记忆:")
    for mem in results:
        print(f"  - {mem.id} (相关度: {mem.score:.2f}): {truncate_text(mem.content, 50)}")
    
    # 更新记忆
    print("\n4. 更新记忆")
    manager.update(mem1_id, "用户非常热爱Python编程，已经学习了3年")
    updated_mem = manager.get(mem1_id)
    if updated_mem:
        print(f"  更新后: {updated_mem.content}")
    
    # 格式化显示
    print("\n5. 格式化显示")
    display_text = manager.format_memories_for_display(all_memories)
    print(f"\n{display_text}")
    
    # 获取摘要
    print("\n6. 记忆摘要")
    summary = manager.get_memory_summary()
    print(f"  总数: {summary['total_count']}")
    print(f"  类型分布: {summary['types']}")
    print(f"  分类分布: {summary['categories']}")
    
    # 清空记忆
    print("\n7. 清空记忆")
    manager.clear()
    print(f"  清空完成，剩余记忆: {len(manager.get_all())}")
    
    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)
