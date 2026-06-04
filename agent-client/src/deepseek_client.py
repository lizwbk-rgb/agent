"""
DeepSeek API客户端模块

封装OpenAI SDK调用DeepSeek API，支持无状态多轮对话、错误处理和重试机制
"""

import time
import logging
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from config import Config, get_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class UsageInfo:
    """API使用信息"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        """转换为字典"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }
    
    def __add__(self, other: "UsageInfo") -> "UsageInfo":
        """支持使用信息相加"""
        return UsageInfo(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )


@dataclass
class ChatResponse:
    """对话响应"""
    content: str
    usage: UsageInfo = field(default_factory=UsageInfo)
    model: str = ""
    finish_reason: str = ""
    is_streaming: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "usage": self.usage.to_dict(),
            "model": self.model,
            "finish_reason": self.finish_reason,
            "is_streaming": self.is_streaming
        }


class DeepSeekClient:
    """
    DeepSeek API客户端
    
    封装OpenAI SDK，提供无状态多轮对话功能
    支持流式和非流式响应，包含错误处理和重试机制
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        初始化DeepSeek客户端
        
        Args:
            api_key: API密钥，默认从配置读取
            base_url: API基础URL，默认从配置读取
            model: 模型名称，默认从配置读取
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        # 从配置获取默认值
        config = get_config()
        
        self.api_key = api_key or config.DEEPSEEK_API_KEY
        self.base_url = base_url or config.DEEPSEEK_BASE_URL
        self.model = model or config.DEEPSEEK_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        logger.info(f"DeepSeek客户端初始化完成 - Model: {self.model}, Base URL: {self.base_url}")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        **kwargs
    ) -> ChatResponse:
        """
        发送对话请求
        
        Args:
            messages: 消息列表，格式为 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数，控制随机性 (0-2)
            max_tokens: 最大生成token数
            stream: 是否使用流式响应
            **kwargs: 其他参数传递给API
            
        Returns:
            ChatResponse: 对话响应对象
            
        Raises:
            ValueError: 参数错误
            Exception: API调用失败
        """
        if not messages:
            raise ValueError("消息列表不能为空")
        
        # 构建请求参数
        request_params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **kwargs
        }
        
        # 调用API（带重试机制）
        if stream:
            return self._chat_stream(request_params)
        else:
            return self._chat_sync(request_params)
    
    def _chat_sync(self, request_params: Dict[str, Any]) -> ChatResponse:
        """同步对话"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response: ChatCompletion = self.client.chat.completions.create(**request_params)
                
                # 解析响应
                message = response.choices[0].message
                content = message.content or ""
                
                # 解析使用信息
                usage = UsageInfo(
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
                    total_tokens=response.usage.total_tokens if response.usage else 0
                )
                
                logger.info(f"对话完成 - Tokens: {usage.total_tokens}, Attempt: {attempt + 1}")
                
                return ChatResponse(
                    content=content,
                    usage=usage,
                    model=response.model,
                    finish_reason=response.choices[0].finish_reason or "",
                    is_streaming=False
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                
                # 检查是否可重试
                if not self._is_retryable_error(e):
                    raise
                
                # 等待后重试
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避: 1, 2, 4秒
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        # 所有重试都失败
        logger.error(f"API调用失败，已重试 {self.max_retries} 次")
        raise last_error
    
    def _chat_stream(self, request_params: Dict[str, Any]) -> ChatResponse:
        """流式对话"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # 累积内容和使用信息
                content_parts = []
                total_usage = UsageInfo()
                model = ""
                finish_reason = ""
                
                stream: ChatCompletionChunk
                for stream in self.client.chat.completions.create(**request_params):
                    # 累积内容
                    if stream.choices and stream.choices[0].delta.content:
                        content_parts.append(stream.choices[0].delta.content)
                    
                    # 更新使用信息
                    if stream.usage:
                        total_usage = UsageInfo(
                            prompt_tokens=stream.usage.prompt_tokens,
                            completion_tokens=stream.usage.completion_tokens,
                            total_tokens=stream.usage.total_tokens
                        )
                    
                    # 记录模型和完成原因
                    if stream.model:
                        model = stream.model
                    if stream.choices and stream.choices[0].finish_reason:
                        finish_reason = stream.choices[0].finish_reason
                
                content = "".join(content_parts)
                
                logger.info(f"流式对话完成 - Tokens: {total_usage.total_tokens}, Attempt: {attempt + 1}")
                
                return ChatResponse(
                    content=content,
                    usage=total_usage,
                    model=model,
                    finish_reason=finish_reason,
                    is_streaming=True
                )
                
            except Exception as e:
                last_error = e
                logger.warning(f"流式API调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                
                if not self._is_retryable_error(e):
                    raise
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        logger.error(f"流式API调用失败，已重试 {self.max_retries} 次")
        raise last_error
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        判断错误是否可重试
        
        可重试的错误：网络错误、超时、5xx服务器错误
        不可重试的错误：4xx客户端错误（除429外）
        """
        error_str = str(error).lower()
        
        # 不可重试的错误
        if "400" in error_str or "401" in error_str or "403" in error_str:
            return False
        if "invalid" in error_str or "authentication" in error_str:
            return False
        
        # 可重试的错误
        if "timeout" in error_str or "connection" in error_str:
            return True
        if "500" in error_str or "502" in error_str or "503" in error_str:
            return True
        if "429" in error_str:  # 速率限制
            return True
        
        # 默认可重试网络相关错误
        return True
    
    def chat_with_system(
        self,
        user_message: str,
        system_prompt: str,
        history: List[Dict[str, str]] = None,
        **kwargs
    ) -> ChatResponse:
        """
        带系统提示的对话
        
        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            history: 历史对话消息
            **kwargs: 其他参数
            
        Returns:
            ChatResponse: 对话响应
        """
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 添加历史消息
        if history:
            messages.extend(history)
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        return self.chat(messages, **kwargs)
    
    def simple_chat(
        self,
        user_message: str,
        **kwargs
    ) -> str:
        """
        简单对话，直接返回文本
        
        Args:
            user_message: 用户消息
            **kwargs: 其他参数
            
        Returns:
            str: AI回复内容
        """
        response = self.chat([
            {"role": "user", "content": user_message}
        ], **kwargs)
        
        return response.content
    
    def get_usage_info(self, response: ChatResponse) -> Dict[str, int]:
        """
        获取响应的使用信息
        
        Args:
            response: 对话响应
            
        Returns:
            Dict: 使用信息字典
        """
        return response.usage.to_dict()
    
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 发送简单请求测试连接
            response = self.simple_chat("你好，请简单介绍一下你自己。", max_tokens=50)
            logger.info("API连接测试成功")
            return True
        except Exception as e:
            logger.error(f"API连接测试失败: {str(e)}")
            return False


# 便捷函数
def get_client() -> DeepSeekClient:
    """获取DeepSeek客户端实例"""
    return DeepSeekClient()


def quick_chat(message: str, **kwargs) -> str:
    """快速对话"""
    client = get_client()
    return client.simple_chat(message, **kwargs)


# 测试代码
if __name__ == "__main__":
    print("=" * 50)
    print("DeepSeek API客户端测试")
    print("=" * 50)
    
    # 创建客户端
    client = DeepSeekClient()
    
    # 测试连接
    print("\n1. 测试API连接...")
    if client.test_connection():
        print("✓ 连接成功")
    else:
        print("✗ 连接失败")
        exit(1)
    
    # 测试简单对话
    print("\n2. 测试简单对话...")
    response = client.simple_chat("1+1等于多少？")
    print(f"AI回复: {response}")
    
    # 测试带系统提示的对话
    print("\n3. 测试带系统提示的对话...")
    response = client.chat_with_system(
        user_message="用Python写一个hello world程序",
        system_prompt="你是一个专业的Python程序员，只回答编程相关问题。",
        max_tokens=200
    )
    print(f"AI回复:\n{response.content}")
    print(f"\n使用信息: {response.usage.to_dict()}")
    
    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)
