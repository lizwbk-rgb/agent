"""
Agent核心模块

协调对话流程，管理记忆注入和提取，完整保留会话历史
支持记忆指令识别、文件上传处理、KV缓存优化
"""

import os
import re
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from config import Config, get_config
from deepseek_client import DeepSeekClient, ChatResponse, UsageInfo
from memory_manager import MemoryManager, Memory
from utils.helpers import Message, truncate_text, format_timestamp
from utils.file_processor import FileProcessor, extract_file_text

# 配置日志
logger = logging.getLogger(__name__)


class ChatMode(Enum):
    """对话模式"""
    ASK = "ask"      # 问答模式
    CRAFT = "craft"  # 创作模式


@dataclass
class ConversationMessage:
    """会话消息"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    file_path: Optional[str] = None
    file_content: Optional[str] = None
    
    def to_api_format(self) -> Dict[str, str]:
        """转换为API格式"""
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResult:
    """对话结果"""
    response: str
    usage: UsageInfo
    memories_added: List[str] = field(default_factory=list)
    memories_deleted: List[str] = field(default_factory=list)
    memories_updated: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "response": self.response,
            "usage": self.usage.to_dict(),
            "memories_added": self.memories_added,
            "memories_deleted": self.memories_deleted,
            "memories_updated": self.memories_updated
        }


class Agent:
    """
    AI对话Agent
    
    协调DeepSeek API、记忆系统和文件处理，提供完整的对话功能
    """
    
    def __init__(
        self,
        user_id: str = None,
        workspace_path: str = None,
        max_history_messages: int = 50,
        system_prompt: str = None
    ):
        """
        初始化Agent
        
        Args:
            user_id: 用户ID
            workspace_path: 工作区路径（Craft模式使用）
            max_history_messages: 最大会话历史消息数
            system_prompt: 自定义系统提示词
        """
        self.config = get_config()
        self.user_id = user_id or self.config.USER_ID
        self.workspace_path = workspace_path
        self.max_history_messages = max_history_messages
        
        # 初始化组件
        self.deepseek_client = DeepSeekClient()
        self.memory_manager = MemoryManager(user_id=self.user_id)
        self.file_processor = FileProcessor()
        
        # 会话历史
        self.conversation_history: List[ConversationMessage] = []
        
        # 当前模式
        self.current_mode = ChatMode.ASK
        
        # 构建系统提示词
        self.system_prompt = self._build_system_prompt(system_prompt)
        
        logger.info(f"Agent初始化完成 - User: {self.user_id}, Mode: {self.current_mode.value}")
    
    def _build_system_prompt(self, custom_prompt: str = None) -> str:
        """构建系统提示词"""
        base_prompt = """你是一个智能AI助手，具备以下能力：

1. **智能对话**: 可以进行多轮对话，记住上下文信息
2. **文件分析**: 可以分析用户上传的文档内容
3. **记忆管理**: 可以记住用户的信息和偏好

回答要求：
- 使用清晰、准确的语言
- 适当使用Markdown格式增强可读性
- 对于代码问题，提供完整的代码示例
- 保持友好和专业的态度

当前日期: {date}
用户ID: {user_id}
""".format(date=datetime.now().strftime("%Y年%m月%d日"), user_id=self.user_id)
        
        if custom_prompt:
            base_prompt += f"\n\n{custom_prompt}"
        
        # Craft模式特殊提示
        if self.current_mode == ChatMode.CRAFT:
            base_prompt += """

**工作区模式**: 用户已启用工作区功能，可以分析项目代码。
工作区路径: {workspace}
""".format(workspace=self.workspace_path or "未设置")
        
        return base_prompt
    
    def set_mode(self, mode: ChatMode):
        """
        设置对话模式
        
        Args:
            mode: 对话模式（ASK或CRAFT）
        """
        self.current_mode = mode
        self.system_prompt = self._build_system_prompt()
        logger.info(f"切换模式: {mode.value}")
    
    def set_workspace(self, path: str):
        """
        设置工作区路径
        
        Args:
            path: 工作区路径
        """
        self.workspace_path = path
        self.system_prompt = self._build_system_prompt()
        logger.info(f"设置工作区: {path}")
    
    def get_workspace_path(self) -> Optional[str]:
        """获取工作区路径"""
        return self.workspace_path
    
    # ==================== 记忆指令处理 ====================
    
    def _is_memory_command(self, message: str) -> Optional[Tuple[str, str]]:
        """
        检查是否是记忆指令
        
        Returns:
            Tuple[command, content]: 指令类型和内容，如果不是指令返回None
        """
        message = message.strip()
        
        # 记住指令: "记住 xxx" 或 "remember xxx"
        remember_patterns = [
            r'^记住\s+(.+)$',
            r'^remember\s+(.+)$',
            r'^请记住\s+(.+)$',
        ]
        
        for pattern in remember_patterns:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                return ("add", match.group(1).strip())
        
        # 删除记忆指令: "删除记忆 xxx" 或 "delete memory xxx"
        delete_patterns = [
            r'^删除记忆\s+(.+)$',
            r'^delete\s+memory\s+(.+)$',
            r'^删除\s+(.+?)\s+的记忆?$',
        ]
        
        for pattern in delete_patterns:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                return ("delete", match.group(1).strip())
        
        # 修改记忆指令: "修改记忆 xxx 为 yyy" 或 "update memory xxx to yyy"
        update_patterns = [
            r'^修改记忆\s+(.+?)\s+为\s+(.+)$',
            r'^update\s+memory\s+(.+?)\s+to\s+(.+)$',
        ]
        
        for pattern in update_patterns:
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                return ("update", f"{match.group(1).strip()} -> {match.group(2).strip()}")
        
        return None
    
    def _handle_memory_command(self, message: str) -> Optional[Dict[str, Any]]:
        """
        处理记忆指令
        
        Returns:
            Dict: 指令处理结果，如果不是指令返回None
        """
        command_result = self._is_memory_command(message)
        
        if command_result is None:
            return None
        
        command, content = command_result
        result = {
            "command": command,
            "content": content,
            "success": False,
            "message": "",
            "memory_id": None
        }
        
        try:
            if command == "add":
                # 添加记忆
                memory_id = self.memory_manager.add(content)
                result["success"] = True
                result["memory_id"] = memory_id
                result["message"] = f"已记住: {content}"
                logger.info(f"添加记忆: {memory_id}")
                
            elif command == "delete":
                # 删除记忆
                # 先搜索相关记忆
                memories = self.memory_manager.search(content, limit=5)
                
                if memories:
                    # 删除最匹配的记忆
                    deleted_id = memories[0].id
                    self.memory_manager.delete(deleted_id)
                    result["success"] = True
                    result["memory_id"] = deleted_id
                    result["message"] = f"已删除记忆: {memories[0].content[:50]}..."
                    logger.info(f"删除记忆: {deleted_id}")
                else:
                    result["message"] = f"未找到相关记忆: {content}"
                    
            elif command == "update":
                # 修改记忆
                parts = content.split(" -> ")
                if len(parts) == 2:
                    old_content, new_content = parts
                    
                    # 搜索旧内容
                    memories = self.memory_manager.search(old_content, limit=5)
                    
                    if memories:
                        # 更新最匹配的记忆
                        updated_id = memories[0].id
                        self.memory_manager.update(updated_id, new_content)
                        result["success"] = True
                        result["memory_id"] = updated_id
                        result["message"] = f"已修改记忆为: {new_content}"
                        logger.info(f"更新记忆: {updated_id}")
                    else:
                        result["message"] = f"未找到相关记忆: {old_content}"
                else:
                    result["message"] = "修改指令格式错误"
                    
        except Exception as e:
            result["message"] = f"指令执行失败: {str(e)}"
            logger.error(f"记忆指令处理失败: {str(e)}")
        
        return result
    
    # ==================== 文件处理 ====================
    
    def _handle_file_upload(self, file_path: str) -> str:
        """
        处理文件上传
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件内容摘要
        """
        logger.info(f"处理文件上传: {file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"错误: 文件不存在 - {file_path}"
        
        # 提取文件内容
        content = extract_file_text(file_path)
        
        # 获取文件信息
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(file_path)[1].lstrip('.')
        
        # 构建文件摘要
        summary = f"""已上传文件: {file_name}
文件类型: {file_ext}
文件大小: {file_size} 字节

文件内容:
{content}
"""
        
        return summary
    
    # ==================== 记忆注入 ====================
    
    def _search_related_memories(self, query: str) -> str:
        """
        搜索相关记忆并格式化
        
        Args:
            query: 查询文本
            
        Returns:
            str: 格式化的记忆上下文
        """
        # 搜索相关记忆
        max_memories = self.config.MAX_MEMORY_COUNT
        memories = self.memory_manager.search(query, limit=max_memories)
        
        if not memories:
            return ""
        
        # 格式化为上下文
        return self.memory_manager.format_memories_for_context(memories)
    
    def _build_context_messages(self, memory_context: str) -> List[Dict[str, str]]:
        """
        构建包含记忆上下文的消息列表
        
        Args:
            memory_context: 记忆上下文文本
            
        Returns:
            List[Dict]: 消息列表
        """
        messages = []
        
        # 添加系统提示
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # 如果有记忆上下文，添加记忆信息
        if memory_context:
            messages.append({
                "role": "system",
                "content": f"{memory_context}\n\n请参考以上记忆信息来回答用户问题。"
            })
        
        return messages
    
    # ==================== 对话处理 ====================
    
    def chat(
        self,
        user_message: str,
        file_path: str = None,
        stream: bool = False
    ) -> ChatResult:
        """
        处理用户消息
        
        Args:
            user_message: 用户消息
            file_path: 附件文件路径（可选）
            stream: 是否使用流式响应
            
        Returns:
            ChatResult: 对话结果
        """
        logger.info(f"处理消息: {truncate_text(user_message, 50)}...")
        
        # 1. 检查是否是记忆指令
        command_result = self._handle_memory_command(user_message)
        
        if command_result:
            # 是记忆指令，直接返回结果
            return ChatResult(
                response=command_result["message"],
                usage=UsageInfo(),
                memories_added=[command_result["memory_id"]] if command_result["command"] == "add" and command_result["memory_id"] else [],
                memories_deleted=[command_result["memory_id"]] if command_result["command"] == "delete" and command_result["memory_id"] else [],
                memories_updated=[command_result["memory_id"]] if command_result["command"] == "update" and command_result["memory_id"] else []
            )
        
        # 2. 处理文件上传
        file_content = None
        if file_path:
            file_content = self._handle_file_upload(file_path)
            # 将文件内容添加到用户消息
            user_message = f"{user_message}\n\n{file_content}"
        
        # 3. 添加用户消息到历史
        user_msg = ConversationMessage(
            role="user",
            content=user_message,
            file_path=file_path,
            file_content=file_content
        )
        self.conversation_history.append(user_msg)
        
        # 4. 搜索相关记忆
        memory_context = self._search_related_memories(user_message)
        
        # 5. 构建消息列表
        context_messages = self._build_context_messages(memory_context)
        
        # 6. 添加历史消息（限制数量）
        history_messages = self._get_history_messages()
        context_messages.extend(history_messages)
        
        # 7. 调用DeepSeek API
        try:
            response = self.deepseek_client.chat(
                messages=context_messages,
                stream=stream,
                temperature=0.7
            )
            
            # 8. 添加AI回复到历史
            assistant_msg = ConversationMessage(
                role="assistant",
                content=response.content
            )
            self.conversation_history.append(assistant_msg)
            
            # 9. 尝试从对话中提取记忆
            self._extract_memories_from_conversation(user_msg, assistant_msg)
            
            return ChatResult(
                response=response.content,
                usage=response.usage
            )
            
        except Exception as e:
            logger.error(f"对话处理失败: {str(e)}")
            return ChatResult(
                response=f"抱歉，处理您的请求时发生了错误: {str(e)}",
                usage=UsageInfo()
            )
    
    def _get_history_messages(self) -> List[Dict[str, str]]:
        """
        获取历史消息（限制数量）
        
        Returns:
            List[Dict]: 历史消息列表
        """
        # 计算要保留的消息数
        max_messages = self.max_history_messages - 2  # 减去当前消息和回复
        
        if len(self.conversation_history) <= max_messages:
            return [msg.to_api_format() for msg in self.conversation_history]
        
        # 保留最近的消息
        recent_messages = self.conversation_history[-max_messages:]
        return [msg.to_api_format() for msg in recent_messages]
    
    def _extract_memories_from_conversation(
        self,
        user_msg: ConversationMessage,
        assistant_msg: ConversationMessage
    ):
        """
        从对话中提取记忆
        
        使用LLM自动识别对话中的关键信息
        """
        try:
            # 构建提取提示
            extract_prompt = f"""分析以下对话，提取用户的关键信息（如偏好、个人信息、习惯等）。

用户: {truncate_text(user_msg.content, 500)}
AI: {truncate_text(assistant_msg.content, 500)}

请按以下格式输出提取的记忆（如果没有可提取的信息，输出"无"）：
1. [记忆内容1]
2. [记忆内容2]
...

只输出记忆内容，不要解释。"""
            
            # 调用API提取记忆
            response = self.deepseek_client.simple_chat(
                extract_prompt,
                temperature=0.1,
                max_tokens=200
            )
            
            # 解析记忆
            memories = []
            for line in response.split('\n'):
                line = line.strip()
                if line and not line.startswith('请') and not line.startswith('只'):
                    # 移除编号前缀
                    memory = re.sub(r'^[\d\.\s]+', '', line).strip()
                    if memory and memory != "无":
                        memories.append(memory)
            
            # 添加记忆
            for memory in memories[:3]:  # 最多添加3条记忆
                self.memory_manager.add(memory, {"source": "auto_extract"})
                logger.info(f"自动提取记忆: {truncate_text(memory, 30)}...")
                
        except Exception as e:
            logger.debug(f"记忆提取失败: {str(e)}")
            # 记忆提取失败不影响主流程
    
    # ==================== 会话管理 ====================
    
    def clear_conversation(self):
        """清空对话历史"""
        self.conversation_history.clear()
        logger.info("对话历史已清空")
    
    def get_conversation_history(self) -> List[ConversationMessage]:
        """获取对话历史"""
        return self.conversation_history.copy()
    
    def get_conversation_summary(self) -> str:
        """获取对话摘要"""
        if not self.conversation_history:
            return "暂无对话记录"
        
        summary = f"对话历史 ({len(self.conversation_history)} 条消息):\n\n"
        
        # 只显示最近10条
        recent = self.conversation_history[-10:]
        for msg in recent:
            content = truncate_text(msg.content, 100)
            time_str = msg.timestamp.strftime("%H:%M")
            summary += f"[{time_str}] {msg.role.upper()}: {content}\n\n"
        
        return summary
    
    # ==================== 记忆管理 ====================
    
    def add_memory_by_text(self, text: str) -> str:
        """
        通过文本添加记忆
        
        Args:
            text: 记忆内容
            
        Returns:
            str: 记忆ID
        """
        return self.memory_manager.add(text)
    
    def update_memory(self, memory_id: str, new_content: str) -> bool:
        """
        修改记忆
        
        Args:
            memory_id: 记忆ID
            new_content: 新内容
            
        Returns:
            bool: 是否成功
        """
        return self.memory_manager.update(memory_id, new_content)
    
    def get_memories(self) -> List[Dict[str, Any]]:
        """
        获取所有记忆
        
        Returns:
            List[Dict]: 记忆列表
        """
        logger.info(f"[DEBUG] agent.get_memories() 开始")
        try:
            memories = self.memory_manager.get_all()
            logger.info(f"[DEBUG] memory_manager.get_all() 返回: type={type(memories)}, len={len(memories) if memories else 'None'}")
            
            result = []
            for i, mem in enumerate(memories):
                logger.info(f"[DEBUG] 处理第{i}个记忆: type={type(mem)}, has_to_dict={hasattr(mem, 'to_dict')}")
                if hasattr(mem, 'to_dict'):
                    try:
                        d = mem.to_dict()
                        result.append(d)
                        logger.info(f"[DEBUG] 第{i}个记忆转为dict: id={d.get('id', 'N/A')}")
                    except Exception as e2:
                        logger.error(f"[DEBUG] 第{i}个记忆to_dict失败: {e2}")
                elif isinstance(mem, dict):
                    result.append(mem)
                    logger.info(f"[DEBUG] 第{i}个记忆是dict: keys={list(mem.keys())[:5]}")
                else:
                    logger.warning(f"[DEBUG] 跳过非Memory对象: type={type(mem)}, value={str(mem)[:100]}")
            logger.info(f"[DEBUG] agent.get_memories() 完成: 返回{len(result)}条")
            return result
        except Exception as e:
            logger.error(f"[DEBUG] 获取记忆失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            bool: 是否成功
        """
        return self.memory_manager.delete(memory_id)
    
    def clear_memories(self) -> bool:
        """
        清空所有记忆
        
        Returns:
            bool: 是否成功
        """
        return self.memory_manager.clear()
    
    # ==================== 状态信息 ====================
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取Agent状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "user_id": self.user_id,
            "mode": self.current_mode.value,
            "workspace_path": self.workspace_path,
            "conversation_count": len(self.conversation_history),
            "memory_count": len(self.memory_manager.get_all()),
            "max_history_messages": self.max_history_messages
        }
    
    def print_status(self):
        """打印Agent状态"""
        status = self.get_status()
        
        print("=" * 50)
        print("Agent 状态")
        print("=" * 50)
        print(f"用户ID: {status['user_id']}")
        print(f"对话模式: {status['mode']}")
        print(f"工作区: {status['workspace_path'] or '未设置'}")
        print(f"对话消息数: {status['conversation_count']}")
        print(f"记忆数量: {status['memory_count']}")
        print(f"最大历史消息: {status['max_history_messages']}")
        print("=" * 50)


# 便捷函数
def create_agent(
    user_id: str = None,
    workspace_path: str = None
) -> Agent:
    """创建Agent实例"""
    return Agent(user_id=user_id, workspace_path=workspace_path)


# 测试代码
if __name__ == "__main__":
    print("=" * 50)
    print("Agent核心模块测试")
    print("=" * 50)
    
    # 创建Agent
    agent = Agent()
    
    # 打印状态
    agent.print_status()
    
    # 测试记忆指令
    print("\n1. 测试记忆指令")
    
    # 添加记忆
    result = agent.chat("记住我喜欢Python编程")
    print(f"  添加记忆: {result.response}")
    
    # 再添加一条
    result = agent.chat("记住我是一名软件工程师")
    print(f"  添加记忆: {result.response}")
    
    # 测试普通对话
    print("\n2. 测试普通对话")
    result = agent.chat("你好！请介绍一下你自己。")
    print(f"  AI回复: {truncate_text(result.response, 200)}...")
    print(f"  Token使用: {result.usage.total_tokens}")
    
    # 测试文件上传
    print("\n3. 测试文件处理（模拟）")
    result = agent.chat("请帮我分析这个文件", file_path="test.py")
    print(f"  文件处理结果: {truncate_text(result.response, 200)}...")
    
    # 获取对话摘要
    print("\n4. 对话摘要")
    print(agent.get_conversation_summary())
    
    # 获取记忆
    print("\n5. 记忆列表")
    memories = agent.get_memories()
    print(f"  总数: {len(memories)}")
    for mem in memories[:3]:
        print(f"  - {mem['id']}: {truncate_text(mem['content'], 50)}")
    
    # 清空对话
    print("\n6. 清空对话")
    agent.clear_conversation()
    print(f"  清空后消息数: {len(agent.get_conversation_history())}")
    
    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)
