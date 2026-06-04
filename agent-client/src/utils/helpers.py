"""
工具函数模块

提供消息格式化、文本截断、时间格式化、日志工具等通用功能
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re


# ==================== 消息格式化 ====================

@dataclass
class Message:
    """消息数据类"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: Optional[datetime] = None
    file_path: Optional[str] = None  # 附件文件路径
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_api_format(self) -> Dict[str, str]:
        """转换为API格式"""
        return {
            "role": self.role,
            "content": self.content
        }
    
    def to_display_format(self) -> str:
        """转换为显示格式"""
        time_str = self.timestamp.strftime("%H:%M:%S") if self.timestamp else ""
        file_info = f" [附件: {self.file_path}]" if self.file_path else ""
        return f"[{time_str}] {self.role.upper()}{file_info}:\n{self.content}"


def format_messages_for_api(messages: List[Message]) -> List[Dict[str, str]]:
    """
    将消息列表转换为API格式
    
    Args:
        messages: Message对象列表
        
    Returns:
        List[Dict]: API格式的消息列表
    """
    return [msg.to_api_format() for msg in messages]


def format_messages_for_display(messages: List[Message]) -> str:
    """
    将消息列表格式化为显示文本
    
    Args:
        messages: Message对象列表
        
    Returns:
        str: 格式化的显示文本
    """
    return "\n\n".join([msg.to_display_format() for msg in messages])


def build_conversation_history(
    messages: List[Dict[str, str]],
    max_messages: int = 20
) -> List[Dict[str, str]]:
    """
    构建对话历史，限制最大消息数
    
    Args:
        messages: 原始消息列表
        max_messages: 最大消息数
        
    Returns:
        List[Dict]: 限制后的消息列表
    """
    if len(messages) <= max_messages:
        return messages
    
    # 保留最近的消息，但确保包含第一条系统消息（如果有）
    system_messages = [msg for msg in messages if msg.get("role") == "system"]
    non_system_messages = [msg for msg in messages if msg.get("role") != "system"]
    
    # 计算可以保留的非系统消息数
    available_slots = max_messages - len(system_messages)
    
    if available_slots < 0:
        # 如果系统消息过多，只保留最后一条
        system_messages = [system_messages[-1]]
        available_slots = max_messages - 1
    
    # 保留最近的非系统消息
    recent_messages = non_system_messages[-available_slots:]
    
    # 组合结果
    result = system_messages + recent_messages
    
    return result


# ==================== 文本截断 ====================

def truncate_text(
    text: str,
    max_length: int = 1000,
    suffix: str = "..."
) -> str:
    """
    截断文本到指定长度
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀
        
    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    # 在最大长度处找到最后一个完整单词或句子边界
    truncated = text[:max_length]
    
    # 尝试在句子边界截断
    sentence_endings = ['.', '!', '?', '。', '！', '？', '\n']
    last_boundary = max_length
    
    for ending in sentence_endings:
        pos = truncated.rfind(ending, max_length - 200, max_length)
        if pos > max_length // 2:
            last_boundary = min(last_boundary, pos + 1)
    
    # 如果找到句子边界，在边界处截断
    if last_boundary < max_length:
        return text[:last_boundary] + suffix
    
    # 否则直接截断
    return truncated + suffix


def truncate_message_content(
    message: str,
    max_length: int = 500
) -> str:
    """
    截断消息内容，保留完整句子
    
    Args:
        message: 原始消息
        max_length: 最大长度
        
    Returns:
        str: 截断后的消息
    """
    if len(message) <= max_length:
        return message
    
    # 按句子分割
    sentences = re.split(r'([.!?。！？])', message)
    result = []
    current_length = 0
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
        
        if current_length + len(sentence) + len(punctuation) <= max_length:
            result.append(sentence)
            if punctuation:
                result.append(punctuation)
            current_length += len(sentence) + len(punctuation)
        else:
            break
    
    if current_length < len(message) * 0.3:
        # 如果截断后内容太少，直接按字符截断
        return truncate_text(message, max_length)
    
    return "".join(result)


def truncate_file_content(
    content: str,
    max_lines: int = 100,
    max_chars: int = 10000
) -> str:
    """
    截断文件内容
    
    Args:
        content: 文件内容
        max_lines: 最大行数
        max_chars: 最大字符数
        
    Returns:
        str: 截断后的内容
    """
    lines = content.split('\n')
    
    # 限制行数
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append(f"\n... [截断，共 {len(content.split(chr(10)))} 行]")
    
    result = '\n'.join(lines)
    
    # 限制字符数
    if len(result) > max_chars:
        result = truncate_text(result, max_chars)
    
    return result


def smart_truncate(
    text: str,
    max_length: int = 500,
    preserve_code: bool = True
) -> str:
    """
    智能截断文本
    
    保留代码块完整性
    
    Args:
        text: 原始文本
        max_length: 最大长度
        preserve_code: 是否保留代码块
        
    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    if not preserve_code:
        return truncate_text(text, max_length)
    
    # 查找代码块
    code_pattern = r'```[\s\S]*?```'
    code_matches = list(re.finditer(code_pattern, text))
    
    if not code_matches:
        return truncate_text(text, max_length)
    
    # 如果文本中有代码块，尝试保留完整
    result = text[:max_length]
    
    # 检查是否在代码块中间截断
    for match in code_matches:
        if match.start() < max_length < match.end():
            # 在代码块中间，截断到代码块开始
            result = text[:match.start()] + "\n... [代码块已截断]\n"
            break
    
    return result + "..." if len(result) >= max_length else result


# ==================== 时间格式化 ====================

def format_timestamp(
    timestamp: datetime,
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    格式化时间戳
    
    Args:
        timestamp: datetime对象
        format_str: 格式字符串
        
    Returns:
        str: 格式化的时间字符串
    """
    return timestamp.strftime(format_str)


def format_relative_time(timestamp: datetime) -> str:
    """
    格式化相对时间
    
    Args:
        timestamp: datetime对象
        
    Returns:
        str: 相对时间字符串
    """
    now = datetime.now()
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}分钟前"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}小时前"
    elif seconds < 604800:  # 7天
        days = int(seconds / 86400)
        return f"{days}天前"
    else:
        return timestamp.strftime("%m-%d")


def get_current_timestamp() -> str:
    """获取当前时间戳字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    解析时间戳字符串
    
    Args:
        timestamp_str: 时间字符串
        
    Returns:
        datetime: 解析后的时间对象，失败返回None
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%H:%M:%S",
        "%H:%M"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue
    
    return None


# ==================== 日志工具 ====================

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
        'RESET': '\033[0m'       # 重置
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        record.levelname = f"{log_color}{record.levelname}{reset}"
        return super().format(record)


def setup_logger(
    name: str = "agent",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    colored: bool = True
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径
        colored: 是否使用彩色输出
        
    Returns:
        Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建格式化器
    formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ) if colored else logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
    
    return logger


def log_message(
    logger: logging.Logger,
    message: Message,
    level: int = logging.INFO
):
    """
    记录消息日志
    
    Args:
        logger: 日志记录器
        message: 消息对象
        level: 日志级别
    """
    log_content = truncate_text(message.content, 500) if len(message.content) > 500 else message.content
    file_info = f" [File: {message.file_path}]" if message.file_path else ""
    
    logger.log(
        level,
        f"[{message.role.upper()}]{file_info}: {log_content}"
    )


# 全局日志记录器
_agent_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """获取全局日志记录器"""
    global _agent_logger
    if _agent_logger is None:
        _agent_logger = setup_logger("agent")
    return _agent_logger


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("工具函数模块测试")
    print("=" * 50)
    
    # 测试消息格式化
    print("\n1. 消息格式化测试")
    messages = [
        Message("user", "你好！"),
        Message("assistant", "你好！有什么可以帮你的？"),
    ]
    
    api_format = format_messages_for_api(messages)
    print(f"API格式: {api_format}")
    
    display_format = format_messages_for_display(messages)
    print(f"显示格式:\n{display_format}")
    
    # 测试文本截断
    print("\n2. 文本截断测试")
    long_text = "这是一段很长的文本。" * 100
    truncated = truncate_text(long_text, 100)
    print(f"原文长度: {len(long_text)}")
    print(f"截断后长度: {len(truncated)}")
    print(f"截断结果: {truncated[:50]}...")
    
    # 测试时间格式化
    print("\n3. 时间格式化测试")
    now = datetime.now()
    print(f"当前时间: {format_timestamp(now)}")
    print(f"相对时间: {format_relative_time(now)}")
    
    past_time = now.replace(hour=now.hour - 2)
    print(f"2小时前: {format_relative_time(past_time)}")
    
    # 测试日志
    print("\n4. 日志工具测试")
    logger = setup_logger("test")
    logger.info("这是一条测试日志")
    logger.warning("这是一条警告日志")
    
    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)
