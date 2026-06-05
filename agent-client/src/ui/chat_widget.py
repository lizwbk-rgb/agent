"""
对话组件

提供消息输入、发送、历史显示、文件上传、模式切换等功能
"""

import os
import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QFrame,
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QEvent
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent, QKeyEvent, QTextCursor

from agent import Agent, ChatMode, ChatResult
from memory_manager import Memory
from utils.helpers import truncate_text, format_timestamp
from ui.markdown_renderer import MarkdownRenderer
from ui.file_reference_popup import FileReferencePopup

# 配置日志
logger = logging.getLogger(__name__)


class MessageBubble(QFrame):
    """消息气泡组件"""
    
    def __init__(
        self,
        content: str,
        role: str,
        timestamp: datetime = None,
        file_path: str = None,
        parent=None
    ):
        """
        初始化消息气泡
        
        Args:
            content: 消息内容
            role: 角色（user/assistant）
            timestamp: 时间戳
            file_path: 附件文件路径
            parent: 父组件
        """
        super().__init__(parent)
        self.content = content
        self.role = role
        self.timestamp = timestamp or datetime.now()
        self.file_path = file_path
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # 角色标签和时间
        role_text = "你" if self.role == "user" else "AI"
        time_text = self.timestamp.strftime("%H:%M")
        header = QLabel(f"{role_text} · {time_text}")
        header_font = QFont()
        header_font.setPointSize(9)
        header.setFont(header_font)
        header.setStyleSheet("color: #999;")
        layout.addWidget(header)
        
        # 文件信息（如果有）
        if self.file_path:
            file_label = QLabel(f"📎 附件: {os.path.basename(self.file_path)}")
            file_font = QFont()
            file_font.setPointSize(10)
            file_label.setFont(file_font)
            file_label.setStyleSheet("color: #666;")
            layout.addWidget(file_label)
        
        # 消息内容
        content_label = QLabel()
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setText(self._format_content())
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(content_label)
        
        # 设置样式
        if self.role == "user":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #e3f2fd;
                    border: 1px solid #bbdefb;
                    border-radius: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #f5f5f5;
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                }
            """)
    
    def _format_content(self) -> str:
        """格式化内容为HTML"""
        # 简单的Markdown转换
        text = self.content
        
        # 代码块
        text = re.sub(r'```(\w*)\n(.*?)```', r'<pre>\2</pre>', text, flags=re.DOTALL)
        # 行内代码
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        # 粗体
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        # 斜体
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        # 链接
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        # 换行
        text = text.replace('\n', '<br>')
        
        return text


class ChatWidget(QWidget):
    """
    对话组件
    
    提供完整的对话界面，支持消息输入、发送、历史显示、文件上传、模式切换
    """
    
    # 信号
    message_sent = pyqtSignal(str, str)  # 消息内容, 文件路径
    file_uploaded = pyqtSignal(str)      # 文件路径
    mode_changed = pyqtSignal(str)       # 模式（ask/craft）
    
    def __init__(
        self,
        agent: Agent = None,
        parent: QWidget = None
    ):
        """
        初始化对话组件
        
        Args:
            agent: Agent实例
            parent: 父组件
        """
        super().__init__(parent)
        
        self.agent = agent
        self.current_mode = ChatMode.ASK
        self.markdown_renderer = MarkdownRenderer()
        self.workspace_path = None  # 工作区路径，用于文件引用
        self._from_input_at = False  # 标志：是否来自输入框@触发
        
        # 文件引用弹出框
        self.file_reference_popup = FileReferencePopup(self)
        self.file_reference_popup.file_selected.connect(self.on_file_reference_selected)
        
        self.setup_ui()
        self.setup_connections()
        
        logger.info("对话组件初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 使用分割器分割对话区域和输入区域（比例 8:2）
        self.chat_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 对话区域
        self.messages_container = QWidget()
        messages_layout = QVBoxLayout(self.messages_container)
        messages_layout.setContentsMargins(16, 16, 16, 8)
        messages_layout.setSpacing(12)
        
        self.messages_layout = messages_layout
        
        # 消息滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.messages_container)
        
        # 设置滚动条样式
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #ccc;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #999;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        
        self.chat_splitter.addWidget(scroll_area)
        
        # 输入区域
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-top: 1px solid #e0e0e0;
            }
        """)
        
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(8)
        
        # 模式切换
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        
        mode_label = QLabel("模式:")
        mode_font = QFont()
        mode_font.setPointSize(11)
        mode_label.setFont(mode_font)
        mode_layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Ask（问答）", "Craft（创作）"])
        self.mode_combo.setMinimumWidth(120)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fff;
            }
            QComboBox:hover {
                border-color: #999;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fff;
            }
        """)
        mode_layout.addWidget(self.mode_combo)
        
        mode_layout.addStretch()
        
        input_layout.addLayout(mode_layout)
        
        # 消息输入框
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("输入消息... (Ctrl+Enter 发送，拖拽文件到此处上传)")
        self.message_input.setMinimumHeight(40)
        self.message_input.setMaximumHeight(200)  # 最大高度200px，超出显示滚动条
        self.message_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 10px;
                background-color: #fff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QTextEdit:focus {
                border-color: #2196F3;
            }
        """)
        input_layout.addWidget(self.message_input)
        
        # 按钮栏
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 发送按钮
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self.send_message)
        send_btn.setMinimumHeight(36)
        send_btn.setMinimumWidth(80)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        button_layout.addWidget(send_btn)
        
        # 文件按钮
        file_btn = QPushButton("📎 文件")
        file_btn.clicked.connect(self.on_file_button_clicked)
        file_btn.setMinimumHeight(36)
        file_btn.setMinimumWidth(80)
        file_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #efefef;
            }
        """)
        button_layout.addWidget(file_btn)
        
        # 清空按钮
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.clicked.connect(self.clear_conversation)
        clear_btn.setMinimumHeight(36)
        clear_btn.setMinimumWidth(80)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #fff;
                color: #999;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #fff5f5;
                color: #cc0000;
                border-color: #ffcccc;
            }
        """)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        input_layout.addLayout(button_layout)
        
        # 限制输入容器的高度
        input_container.setMaximumHeight(200)
        
        self.chat_splitter.addWidget(input_container)
        self.chat_splitter.setStretchFactor(0, 7)  # 对话区域占 70%
        self.chat_splitter.setStretchFactor(1, 3)  # 输入区域占 30%
        
        # 设置分割器的具体高度（像素值）
        self.chat_splitter.setSizes([600, 250])
        
        main_layout.addWidget(self.chat_splitter)
        
        # 设置整体样式
        self.setStyleSheet("""
            ChatWidget {
                background-color: #fafafa;
                border-radius: 8px;
            }
        """)
    
    def setup_connections(self):
        """设置信号连接"""
        # 模式切换
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        
        # 输入框事件过滤器
        self.message_input.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于检测@输入"""
        if obj == self.message_input and event.type() == QEvent.Type.KeyPress:
            # 检查是否输入了@
            if event.text() == '@':
                # 设置标志：来自输入框@触发
                self._from_input_at = True
                # 显示文件引用弹出框
                self.show_file_reference_popup()
        
        return super().eventFilter(obj, event)
    
    def show_file_reference_popup(self):
        """显示文件引用弹出框"""
        if not self.workspace_path:
            logger.warning("工作区路径未设置，无法显示文件引用弹出框")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "提示",
                "请先设置工作区路径（点击工作区组件的'选择...'按钮）"
            )
            return
        
        # 设置弹出框的工作区路径
        self.file_reference_popup.set_workspace(self.workspace_path)
        
        # 获取光标全局位置
        cursor_pos = self.message_input.mapToGlobal(self.message_input.cursorRect().bottomRight())
        self.file_reference_popup.show_at_cursor(cursor_pos)
    
    def on_file_reference_selected(self, file_path: str):
        """文件引用选中事件"""
        # 在输入框中插入文件路径
        cursor = self.message_input.textCursor()
        
        # 判断来源：如果是从输入框@触发，不插入@（用户已输入）
        # 如果是从右键菜单"添加至会话"触发，需要插入@
        if hasattr(self, '_from_input_at') and self._from_input_at:
            # 来自输入框@触发，只插入文件路径（不含@）
            cursor.insertText(f"{file_path} ")
            self._from_input_at = False  # 重置标志
        else:
            # 来自右键菜单，插入@文件路径
            cursor.insertText(f"@{file_path} ")
        
        logger.info(f"插入文件引用: {file_path}")
    
    def set_workspace_path(self, workspace_path: str):
        """设置工作区路径"""
        self.workspace_path = workspace_path
        logger.info(f"设置工作区路径: {workspace_path}")
    
    def send_message(self):
        """发送消息"""
        # 获取输入内容
        content = self.message_input.toPlainText().strip()
        
        if not content:
            return
        
        # 清空输入框
        self.message_input.clear()
        
        # 发送信号
        self.message_sent.emit(content, "")
        
        # 如果有agent，直接处理
        if self.agent:
            self._process_message(content)
    
    def _process_message(self, content: str, file_path: str = None):
        """处理消息"""
        try:
            # 显示用户消息
            self.add_message(content, "user", file_path=file_path)
            
            # 调用agent
            result: ChatResult = self.agent.chat(content, file_path=file_path)
            
            # 显示AI回复
            self.add_message(result.response, "assistant")
            
            # 滚动到底部
            self._scroll_to_bottom()
            
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            self.add_message(f"错误: {str(e)}", "assistant")
    
    def add_message(
        self,
        content: str,
        role: str,
        file_path: str = None
    ):
        """
        添加消息到对话区域
        
        Args:
            content: 消息内容
            role: 角色（user/assistant）
            file_path: 附件文件路径
        """
        # 创建消息气泡
        message_widget = MessageBubble(
            content=content,
            role=role,
            file_path=file_path
        )
        
        # 添加到布局
        self.messages_layout.addWidget(message_widget)
        
        # 滚动到底部
        self._scroll_to_bottom()
    
    def clear_conversation(self):
        """清空对话"""
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有对话历史吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 清空UI
            while self.messages_layout.count():
                item = self.messages_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 清空agent历史
            if self.agent:
                self.agent.clear_conversation()
            
            logger.info("对话已清空")
    
    def on_file_button_clicked(self):
        """文件按钮点击事件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            os.path.expanduser("~"),
            "所有文件 (*.*);;文本文件 (*.txt);;文档 (*.pdf *.docx);;图片 (*.png *.jpg *.gif)"
        )
        
        if file_path:
            self.file_uploaded.emit(file_path)
            self._process_message("请分析这个文件", file_path=file_path)
    
    def on_mode_changed(self, index: int):
        """模式切换事件"""
        if index == 0:
            self.current_mode = ChatMode.ASK
            mode_str = "ask"
        else:
            self.current_mode = ChatMode.CRAFT
            mode_str = "craft"
        
        # 更新agent模式
        if self.agent:
            self.agent.set_mode(self.current_mode)
        
        self.mode_changed.emit(mode_str)
        logger.info(f"切换模式: {mode_str}")
    
    def get_current_mode(self) -> str:
        """获取当前模式"""
        return self.current_mode.value
    
    def set_mode(self, mode: str):
        """
        设置模式
        
        Args:
            mode: 模式（ask/craft）
        """
        if mode == "ask":
            self.mode_combo.setCurrentIndex(0)
            self.current_mode = ChatMode.ASK
        elif mode == "craft":
            self.mode_combo.setCurrentIndex(1)
            self.current_mode = ChatMode.CRAFT
        
        if self.agent:
            self.agent.set_mode(self.current_mode)
    
    def setup_file_drop(self):
        """设置文件拖拽上传"""
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """拖拽释放事件"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path:
                    self.file_uploaded.emit(file_path)
                    self._process_message(f"请分析文件: {os.path.basename(file_path)}", file_path=file_path)
                    break
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件"""
        # Ctrl+Enter 发送消息
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
                self.send_message()
                return
        
        super().keyPressEvent(event)
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        # 延迟滚动，确保UI更新完成
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._do_scroll_to_bottom)
    
    def _do_scroll_to_bottom(self):
        """执行滚动到底部"""
        scroll_area = self.findChild(QScrollArea)
        if scroll_area and scroll_area.verticalScrollBar():
            scroll_area.verticalScrollBar().setValue(scroll_area.verticalScrollBar().maximum())
    
    def render_message(self, text: str) -> str:
        """
        渲染消息为HTML
        
        Args:
            text: 消息文本
            
        Returns:
            str: HTML文本
        """
        return self.markdown_renderer.render(text)
    
    def update_agent(self, agent: Agent):
        """更新Agent实例"""
        self.agent = agent
        self.set_mode(self.current_mode.value)


# 便捷函数
def create_chat_widget(agent: Agent = None, parent: QWidget = None) -> ChatWidget:
    """创建对话组件"""
    return ChatWidget(agent, parent)
