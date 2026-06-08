"""
聊天工作线程模块

实现异步API调用，通过信号槽机制实时更新UI内容
"""

import logging
from PyQt6.QtCore import QThread, pyqtSignal

from agent import Agent

# 配置日志
logger = logging.getLogger(__name__)


class ChatWorker(QThread):
    """
    异步聊天工作线程
    
    在后台线程中处理API调用，通过信号实时更新UI
    """
    
    # 信号定义
    # 流式内容更新
    content_update = pyqtSignal(str)
    # 深度思考内容更新
    thinking_update = pyqtSignal(str)
    # 完成信号（完整内容）
    finished = pyqtSignal(str, dict)  # content, usage_dict
    # 错误信号
    error = pyqtSignal(str)
    # 思考开始信号
    thinking_started = pyqtSignal()
    # 思考结束信号（包含完整思考内容）
    thinking_finished = pyqtSignal(str)  # thinking_content
    
    def __init__(
        self,
        agent: Agent,
        user_message: str,
        file_path=None,
        enable_thinking: bool = False,
        model: str = "deepseek-v4-pro",
        parent=None
    ):
        """
        初始化聊天工作线程
        
        Args:
            agent: Agent实例
            user_message: 用户消息
            file_path: 附件文件路径
            enable_thinking: 是否启用深度思考模式
            model: 使用的模型名称
            parent: 父组件
        """
        super().__init__(parent)
        
        self.agent = agent
        self.user_message = user_message
        self.file_path = file_path
        self.enable_thinking = enable_thinking
        self.model = model
        
        # 停止标志
        self._stop_flag = False
        
        # 累积思考内容
        self._thinking_content = ""
        
        logger.info(f"ChatWorker初始化 - Model: {model}, Thinking: {enable_thinking}")
    
    def run(self):
        """执行流式API调用"""
        try:
            # 通知UI思考开始（如果是深度思考模式）
            if self.enable_thinking:
                self.thinking_started.emit()
            
            # 调用Agent的chat_stream方法，这会自动处理用户消息保存
            result = self.agent.chat_stream(
                user_message=self.user_message,
                file_path=self.file_path,
                enable_thinking=self.enable_thinking,
                model=self.model,
                content_callback=self._on_content_chunk,
                thinking_callback=self._on_thinking_chunk
            )
            
            # 通知UI思考结束（如果是深度思考模式），传递完整思考内容
            if self.enable_thinking:
                self.thinking_finished.emit(self._thinking_content)
            
            # 完成时发出信号，包含思考内容
            usage_dict = {
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
                "total_tokens": result.usage.total_tokens,
                "model": self.model,
                "finish_reason": "stop",
                "thinking_content": self._thinking_content
            }
            self.finished.emit(result.response, usage_dict)
            
        except Exception as e:
            # 打印详细错误信息
            import traceback
            import sys  
            print(f"[ERROR] ChatWorker捕获到异常: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            
            error_msg = f"API调用失败: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)
    
    def _on_content_chunk(self, content: str):
        """处理内容块"""
        if self._stop_flag:
            return
        self.content_update.emit(content)
    
    def _on_thinking_chunk(self, thinking_content: str):
        """处理思考内容块"""
        if self._stop_flag:
            return
        # 累积思考内容
        self._thinking_content = thinking_content
        self.thinking_update.emit(thinking_content)
    
    def stop(self):
        """停止工作线程"""
        self._stop_flag = True
        logger.info("ChatWorker停止中...")
