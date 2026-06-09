"""
记忆提取异步工作器

在后台线程中从对话中提取记忆，避免在主线程中阻塞。
"""

import logging
from typing import List, Optional

from .base_worker import BaseWorker
from agent import Agent, ConversationMessage
from memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class MemoryExtractWorker(BaseWorker):
    """
    记忆提取异步工作器
    
    在后台线程中从对话中提取记忆，通过finished信号返回提取的记忆ID列表。
    结果格式: List[str] - 提取的记忆ID列表
    """
    
    def __init__(
        self,
        agent: Agent,
        user_msg: ConversationMessage,
        assistant_msg: ConversationMessage,
        parent=None
    ):
        """
        初始化记忆提取工作器
        
        Args:
            agent: Agent实例
            user_msg: 用户消息
            assistant_msg: AI回复消息
            parent: 父对象
        """
        super().__init__(parent)
        self.agent = agent
        self.user_msg = user_msg
        self.assistant_msg = assistant_msg
        
    def run(self):
        """执行记忆提取任务"""
        try:
            self._safe_emit_progress(0, "正在提取对话中的记忆...")
            
            logger.info(f"开始异步提取记忆 - 用户消息: {self.user_msg.content[:50]}...")
            
            if self.is_cancelled():
                logger.info("记忆提取任务已取消")
                return
            
            # 搜索已有记忆，避免重复提取
            existing_memories = self.agent.memory_manager.search(self.user_msg.content, limit=5)
            existing_text = "\n".join([f"- {m.content}" for m in existing_memories]) if existing_memories else "（无）"
            
            if self.is_cancelled():
                logger.info("记忆提取任务已取消（搜索完成后检查）")
                return
            
            # 构建提取提示
            from utils.helpers import truncate_text
            extract_prompt = f"""请分析以下对话，从中提取用户的关键信息（如偏好、个人信息、工作、习惯等）。

【已有记忆】（请不要重复提取以下已有记忆）
{existing_text}

【对话内容】
用户: {truncate_text(self.user_msg.content, 500)}
AI: {truncate_text(self.assistant_msg.content, 500)}

【任务说明】
请从上述对话中提取用户的关键信息。这些信息可能是：
- 用户的个人信息（姓名、地点、职业等）
- 用户的工作信息（公司、部门、职位等）
- 用户的偏好和习惯
- 用户提到的其他重要信息

【输出要求】
1. 必须使用中文输出
2. 每条记忆格式："用户[信息描述]"
3. 如果没有可提取的新信息，输出"无"
4. 只输出记忆内容，不要输出任何解释、标题或额外文字
5. 不要重复【已有记忆】中已存在的信息

【输出示例】
如果用户说"我是深圳的软件测试工程师"：
用户来自深圳
用户是一名软件测试工程师

如果用户说"我在腾讯做外包"：
用户在腾讯工作
用户是外包人员

【开始输出】"""
            
            self._safe_emit_progress(50, "正在调用API提取记忆...")
            
            # 调用API提取记忆
            response = self.agent.deepseek_client.simple_chat(
                extract_prompt,
                temperature=0.1,
                max_tokens=200
            )
            
            if self.is_cancelled():
                logger.info("记忆提取任务已取消（API调用后检查）")
                return
            
            # 解析记忆
            import re
            memories = []
            for line in response.split('\n'):
                line = line.strip()
                if line and not line.startswith('请') and not line.startswith('只'):
                    # 移除编号前缀
                    memory = re.sub(r'^[\d\.\s]+', '', line).strip()
                    if memory and memory != "无":
                        memories.append(memory)
            
            logger.info(f"解析到 {len(memories)} 条记忆")
            
            self._safe_emit_progress(80, f"正在保存 {len(memories)} 条记忆...")
            
            # 添加记忆
            memory_ids = []
            for memory in memories[:3]:  # 最多添加3条记忆
                if self.is_cancelled():
                    logger.info("记忆提取任务已取消（保存记忆时检查）")
                    return
                
                logger.info(f"添加记忆: {memory[:30]}")
                memory_id = self.agent.memory_manager.add(memory, {"source": "auto_extract"})
                memory_ids.append(memory_id)
            
            self._safe_emit_progress(100, f"记忆提取完成，共提取 {len(memory_ids)} 条")
            self._safe_emit_finished(memory_ids)
            
            logger.info(f"记忆提取任务完成，提取了 {len(memory_ids)} 条记忆")
            
        except Exception as e:
            error_msg = f"记忆提取失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._safe_emit_error(error_msg)
