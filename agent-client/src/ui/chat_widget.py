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
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QEvent, QTimer
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent, QKeyEvent, QTextCursor

from agent import Agent, ChatMode, ChatResult
from memory_manager import Memory
from utils.helpers import truncate_text, format_timestamp
from utils.file_processor import FileProcessor
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
        is_thinking: bool = False,
        parent=None
    ):
        """
        初始化消息气泡
        
        Args:
            content: 消息内容
            role: 角色（user/assistant）
            timestamp: 时间戳
            file_path: 附件文件路径
            is_thinking: 是否是思考中状态
            parent: 父组件
        """
        super().__init__(parent)
        self.content = content
        self.role = role
        self.timestamp = timestamp or datetime.now()
        self.file_path = file_path
        self.is_thinking = is_thinking
        
        # 节流计时器 - 减少 setHtml 调用频率
        self._update_timer = None
        self._pending_content = None
        
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
        
        # 消息内容（使用MarkdownRenderer渲染）
        renderer = MarkdownRenderer()
        html_content = renderer.render(self.content)
        
        # 使用QTextBrowser代替QTextEdit，支持完整HTML/CSS
        from PyQt6.QtWidgets import QTextBrowser
        content_browser = QTextBrowser()
        content_browser.setHtml(html_content)
        content_browser.setReadOnly(True)
        # 禁用滚动条，让内容自动展开
        content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                background-color: transparent;
                font-size: 14px;
            }
        """)
        # 先添加到布局，让QTextBrowser获得正确的宽度
        layout.addWidget(content_browser)
        
        # 保存引用，在showEvent中调整高度
        self._content_text_edit = content_browser
        
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
            # AI消息样式
            if self.is_thinking:
                # 思考中状态样式
                self.setStyleSheet("""
                    MessageBubble {
                        background-color: #fff3e0;
                        border: 1px solid #ffe0b2;
                        border-radius: 12px;
                    }
                """)
                # 设置思考中文本
                self._content_text_edit.setText(self.content)
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
    
    def _adjust_content_height(self):
        """调整内容区域高度"""
        if hasattr(self, '_content_text_edit') and self._content_text_edit:
            # 获取文档高度
            doc = self._content_text_edit.document()
            # 使用documentLayout来获取更准确的高度
            layout = doc.documentLayout()
            if layout:
                doc_height = layout.documentSize().height()
            else:
                doc_height = doc.size().height()
            doc_height = int(doc_height) + 20  # +20 for padding
            self._content_text_edit.setFixedHeight(doc_height)
        # 清理timer
        if hasattr(self, '_adjust_timer'):
            self._adjust_timer = None
    
    def showEvent(self, event):
        """显示事件 - 调整内容高度"""
        super().showEvent(event)
        # 延迟调整高度，确保布局完成
        if hasattr(self, '_content_text_edit') and self._content_text_edit:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, self._adjust_content_height)
    
    def update_content(self, new_content: str):
        """
        更新消息内容（用于流式更新）- 使用节流机制
        
        Args:
            new_content: 新的消息内容
        """
        self.content = new_content
        self._pending_content = new_content
        
        # 使用节流机制 - 每100ms最多更新一次UI
        if self._update_timer is None:
            from PyQt6.QtCore import QTimer
            self._update_timer = QTimer()
            self._update_timer.setSingleShot(True)
            self._update_timer.timeout.connect(self._do_update_content)
        
        # 重启计时器（100ms后触发）
        self._update_timer.start(100)
    
    def _do_update_content(self):
        """实际执行内容更新（由计时器触发）"""
        if self._pending_content is None:
            return
        
        # 重新渲染Markdown
        renderer = MarkdownRenderer.get_instance()
        html_content = renderer.render(self._pending_content)
        
        # 更新显示
        if hasattr(self, '_content_text_edit') and self._content_text_edit:
            self._content_text_edit.setHtml(html_content)
            # 延迟调整高度
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._adjust_content_height)
        
        self._pending_content = None
        self._update_timer = None
    
    def set_thinking_state(self, is_thinking: bool):
        """
        设置思考中状态
        
        Args:
            is_thinking: 是否是思考中状态
        """
        self.is_thinking = is_thinking
        
        # 更新内容显示
        if is_thinking:
            self.content = "AI思考中，请稍后......"
            self._content_text_edit.setText(self.content)
        
        # 更新样式
        self._update_thinking_style()
    
    def _update_thinking_style(self):
        """更新思考中状态样式"""
        if self.role == "assistant" and self.is_thinking:
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #fff3e0;
                    border: 1px solid #ffe0b2;
                    border-radius: 12px;
                }
            """)
        elif self.role == "assistant":
            self.setStyleSheet("""
                MessageBubble {
                    background-color: #f5f5f5;
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                }
            """)


class ChatWidget(QWidget):
    """
    对话组件
    
    提供完整的对话界面，支持消息输入、发送、历史显示、文件上传、模式切换
    """
    
    # 信号
    message_sent = pyqtSignal(str, str)  # 消息内容, 文件路径
    file_uploaded = pyqtSignal(str)      # 文件路径
    mode_changed = pyqtSignal(str)       # 模式（ask/craft）
    new_conversation_requested = pyqtSignal()  # 新建对话请求
    history_requested = pyqtSignal()         # 历史会话请求
    model_changed = pyqtSignal(str)          # 模型变化信号
    thinking_state_changed = pyqtSignal(bool)  # 深度思考状态变化信号
    
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
        
        # 深度思考状态
        self._deep_think_enabled = False
        
        # 当前AI消息气泡引用（用于流式更新）
        self._current_ai_bubble = None

        # 附件文件管理：{文件名: {"path": 绝对路径, "content": 文件内容}}
        self.attached_files = {}

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
        
        # 在底部添加stretch，使消息集中在顶部而非铺满整个会话区
        messages_layout.addStretch(1)
        
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
        
        # 模式切换行1：模式选择、模型选择、深度思考
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        
        # 模式标签
        mode_label = QLabel("模式:")
        mode_font = QFont()
        mode_font.setPointSize(11)
        mode_label.setFont(mode_font)
        mode_layout.addWidget(mode_label)
        
        # 模式下拉框
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Ask（问答）", "Craft（创作）"])
        self.mode_combo.setMinimumWidth(120)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fff;
                font-size: 11px;
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
        
        # 模型选择器
        from ui.model_selector import ModelSelector
        self.model_selector = ModelSelector()
        mode_layout.addWidget(self.model_selector)
        
        # 深度思考按钮
        from ui.deep_think_button import DeepThinkButton
        self.deep_think_btn = DeepThinkButton()
        mode_layout.addWidget(self.deep_think_btn)
        
        mode_layout.addStretch()
        
        # 新对话按钮（+）
        self.new_conv_btn = QPushButton("+")
        self.new_conv_btn.setToolTip("创建新对话")
        self.new_conv_btn.setFixedSize(28, 28)
        self.new_conv_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ddd;
                border-radius: 14px;
                font-size: 16px;
                font-weight: bold;
                color: #666;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #2196F3;
                color: #2196F3;
            }
        """)
        mode_layout.addWidget(self.new_conv_btn)
        
        # 历史会话按钮（时钟）
        self.history_btn = QPushButton("🕐")
        self.history_btn.setToolTip("历史会话记录")
        self.history_btn.setFixedSize(28, 28)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ddd;
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #2196F3;
            }
        """)
        mode_layout.addWidget(self.history_btn)
        
        input_layout.addLayout(mode_layout)
        
        # 消息输入框
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("输入消息... (Ctrl+Enter 发送，拖拽文件到此处上传)")
        self.message_input.setMinimumHeight(40)
        self.message_input.setMaximumHeight(200)  # 最大高度200px，超出显示滚动条
        self.message_input.setAcceptDrops(False)  # 禁用输入框默认拖拽，由ChatWidget处理
        self.message_input.viewport().setAcceptDrops(False)  # 同时禁用viewport的拖拽处理
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
        
        # 模型选择器
        self.model_selector.model_changed.connect(self.on_model_changed)
        
        # 深度思考按钮
        self.deep_think_btn.state_changed.connect(self.on_deep_think_state_changed)
        
        # 新对话和历史按钮
        self.new_conv_btn.clicked.connect(self.new_conversation_requested.emit)
        self.history_btn.clicked.connect(self.history_requested.emit)
        
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
        # 如果是来自输入框@触发，需要删除输入框中@及后续字符
        if hasattr(self, '_from_input_at') and self._from_input_at:
            text_edit = self.message_input
            text = text_edit.toPlainText()
            cursor = text_edit.textCursor()
            cursor_pos = cursor.position()

            # 找到@的位置（从光标位置往前找）
            at_pos = text.rfind('@', 0, cursor_pos)
            if at_pos >= 0:
                # 删除从@到光标位置的内容
                cursor.setPosition(at_pos)
                cursor.setPosition(cursor_pos, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                text_edit.setTextCursor(cursor)

            self._from_input_at = False

        # 附加文件（读取内容并插入[文件名]到输入框）
        self._attach_file(file_path)

        logger.info(f"插入文件引用: {file_path}")

    def _attach_file(self, file_path: str):
        """
        附加文件到输入框（不自动发送）

        Args:
            file_path: 文件绝对路径
        """
        # 规范化路径（修复Windows混合分隔符问题）
        file_path = os.path.normpath(file_path)
        try:
            # 读取文件内容
            file_processor = FileProcessor()
            file_content = file_processor.extract_text(file_path)
            file_name = os.path.basename(file_path)

            # 存储到 attached_files
            self.attached_files[file_name] = {
                "path": file_path,
                "content": file_content
            }

            # 在输入框光标处插入 [文件名]
            cursor = self.message_input.textCursor()
            cursor.insertText(f"[{file_name}] ")

            logger.info(f"附加文件: {file_name}")
        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, {e}")
            # 即使读取失败，也插入文件名
            file_name = os.path.basename(file_path)
            cursor = self.message_input.textCursor()
            cursor.insertText(f"[{file_name}] ")

    def set_workspace_path(self, workspace_path: str):
        """设置工作区路径"""
        self.workspace_path = workspace_path
        logger.info(f"设置工作区路径: {workspace_path}")
    
    def send_message(self):
        """发送消息"""
        # 获取输入内容（含[文件名]）
        content = self.message_input.toPlainText().strip()

        if not content:
            return

        # 检查是否正在处理消息
        if hasattr(self, '_chat_worker') and self._chat_worker.isRunning():
            logger.warning("正在处理消息，请稍候...")
            return

        # 构建显示内容（原始内容，含[文件名]）
        display_content = content

        # 构建发送内容：将[文件名]替换为@绝对路径
        send_content = content
        logger.info(f"send_message: content='{content}', attached_files={list(self.attached_files.keys())}")
        for file_name, file_info in self.attached_files.items():
            # 替换 [文件名] 为 @绝对路径
            old_send = send_content
            send_content = send_content.replace(f"[{file_name}]", f"@{file_info['path']}")
            logger.info(f"send_message: replace '[{file_name}]' with '@{file_info['path']}', result='{send_content[:100]}'")

        # 清空输入框和附件
        self.message_input.clear()
        self.attached_files = {}

        # 发送信号
        self.message_sent.emit(display_content, "")

        # 如果有agent，直接处理（使用流式）
        if self.agent:
            self._process_message_stream(display_content, send_content)
    
    def _process_message_stream(self, display_content: str, send_content: str = None):
        """流式处理消息"""
        # 如果没有提供send_content，使用display_content
        if send_content is None:
            send_content = display_content

        try:
            # 1. 显示用户消息（使用display_content，含[文件名]）
            self.add_message(display_content, "user")

            # 2. 显示AI思考中占位消息
            ai_bubble = self.add_message("AI思考中，请稍后......", "assistant", is_thinking=True)
            self._current_ai_bubble = ai_bubble

            # 3. 如果启用深度思考，显示思考区域
            if self._deep_think_enabled:
                self._show_thinking_area()

            # 4. 禁用发送按钮
            self._disable_send_button()

            # 5. 启动ChatWorker线程（使用send_content，含@绝对路径）
            from ui.chat_worker import ChatWorker

            self._chat_worker = ChatWorker(
                agent=self.agent,
                user_message=send_content,
                file_path=None,
                enable_thinking=self._deep_think_enabled,
                model=self.model_selector.get_current_model()
            )

            # 连接信号
            self._chat_worker.content_update.connect(self._on_content_update)
            self._chat_worker.thinking_update.connect(self._on_thinking_update)
            self._chat_worker.finished.connect(self._on_chat_finished)
            self._chat_worker.error.connect(self._on_chat_error)
            self._chat_worker.thinking_started.connect(self._on_thinking_started)
            self._chat_worker.thinking_finished.connect(self._on_thinking_finished)

            # 启动线程
            self._chat_worker.start()

        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            # 移除占位消息
            if self._current_ai_bubble:
                self._current_ai_bubble.set_thinking_state(False)
                self._current_ai_bubble.update_content(f"错误: {str(e)}")
            self._enable_send_button()
    
    def _on_content_update(self, content: str):
        """处理流式内容更新"""
        if self._current_ai_bubble:
            # 更新占位消息的内容
            self._current_ai_bubble.set_thinking_state(False)
            self._current_ai_bubble.update_content(content)
            self._scroll_to_bottom()
    
    def _on_thinking_update(self, thinking_content: str):
        """处理深度思考内容更新"""
        if hasattr(self, '_thinking_area') and self._thinking_area:
            try:
                self._thinking_area.update_content(thinking_content)
            except RuntimeError:
                # 思考区域已被删除
                self._thinking_area = None
    
    def _on_chat_finished(self, content: str, usage_dict: dict):
        """处理聊天完成"""
        logger.info(f"聊天完成 - 内容长度: {len(content)}")
        
        # 更新最终内容
        if self._current_ai_bubble:
            self._current_ai_bubble.set_thinking_state(False)
            self._current_ai_bubble.update_content(content)
        
        # 启用发送按钮
        self._enable_send_button()
        
        # 清除当前AI气泡引用
        self._current_ai_bubble = None
        
        # 滚动到底部
        self._scroll_to_bottom()
    
    def _on_chat_error(self, error_msg: str):
        """处理聊天错误"""
        logger.error(f"聊天错误: {error_msg}")
        
        # 更新错误信息
        if self._current_ai_bubble:
            self._current_ai_bubble.set_thinking_state(False)
            self._current_ai_bubble.update_content(f"错误: {error_msg}")
        
        # 启用发送按钮
        self._enable_send_button()
        
        # 清除当前AI气泡引用
        self._current_ai_bubble = None
    
    def _on_thinking_started(self):
        """处理思考开始"""
        logger.info("深度思考开始")
        if hasattr(self, '_thinking_area') and self._thinking_area:
            try:
                self._thinking_area.show_thinking()
            except RuntimeError:
                # 思考区域已被删除
                self._thinking_area = None
    
    def _on_thinking_finished(self, thinking_content: str):
        """处理思考结束"""
        logger.info("深度思考结束")
        # 思考结束后更新显示"思考结束"
        if hasattr(self, '_thinking_area') and self._thinking_area:
            try:
                self._thinking_area.set_thinking_finished()
            except RuntimeError:
                # 思考区域已被删除
                self._thinking_area = None
    
    def _show_thinking_area(self):
        """显示思考区域"""
        from ui.thinking_area import ThinkingArea
        
        # 检查是否已有思考区域且未被删除
        need_create = False
        if not hasattr(self, '_thinking_area') or not self._thinking_area:
            need_create = True
        else:
            # 检查对象是否已被删除
            try:
                # 尝试访问一个属性，如果对象已删除会抛出RuntimeError
                _ = self._thinking_area.isVisible()
            except RuntimeError:
                # 对象已被删除，需要重新创建
                need_create = True
                self._thinking_area = None
        
        # 如果没有思考区域或已被删除，创建一个
        if need_create:
            self._thinking_area = ThinkingArea()
            # 插入到当前AI消息之前
            ai_bubble_index = self.messages_layout.indexOf(self._current_ai_bubble)
            self.messages_layout.insertWidget(ai_bubble_index, self._thinking_area)
        
        self._thinking_area.show_thinking()
    
    def _disable_send_button(self):
        """禁用发送按钮"""
        # 找到发送按钮并禁用
        for btn in self.findChildren(QPushButton):
            if btn.text() == "发送":
                btn.setEnabled(False)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ccc;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                """)
                break
    
    def _enable_send_button(self):
        """启用发送按钮"""
        for btn in self.findChildren(QPushButton):
            if btn.text() == "发送":
                btn.setEnabled(True)
                btn.setStyleSheet("""
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
                break
    
    def add_message(
        self,
        content: str,
        role: str,
        file_path: str = None,
        is_thinking: bool = False
    ):
        """
        添加消息到对话区域
        
        Args:
            content: 消息内容
            role: 角色（user/assistant）
            file_path: 附件文件路径
            is_thinking: 是否是思考中状态
            
        Returns:
            MessageBubble: 消息气泡组件
        """
        # 创建消息气泡
        message_widget = MessageBubble(
            content=content,
            role=role,
            file_path=file_path,
            is_thinking=is_thinking
        )
        
        # 添加到布局（插入到stretch之前）
        # messages_layout的最后一个项目是stretch，所以插入位置是count()-1
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
        
        # 滚动到底部
        self._scroll_to_bottom()
        
        return message_widget
    
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
            
            # 清空附件
            self.attached_files = {}
            
            logger.info("对话已清空")
    
    def clear_chat_display(self):
        """清空聊天显示（不显示确认对话框）"""
        # 清空UI
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 清除思考区域引用（组件已被删除）
        self._thinking_area = None
        
        # 清空附件
        self.attached_files = {}
        
        logger.info("聊天显示已清空")
    
    def load_conversation_history(self):
        """加载会话历史到显示区域"""
        if not self.agent:
            logger.warning("Agent未设置，无法加载会话历史")
            return
        
        # 清空当前显示
        self.clear_chat_display()
        
        # 获取会话历史
        history = self.agent.get_conversation_history()
        
        # 显示历史消息
        for msg in history:
            if msg.role == "thinking":
                # 思考内容：显示在思考区域中，而不是作为普通消息
                from ui.thinking_area import ThinkingArea
                thinking_area = ThinkingArea()
                thinking_area.set_content(msg.content)
                thinking_area.set_thinking_finished()
                thinking_area.collapse()  # 默认折叠，用户可以点击展开
                # 插入到stretch之前
                self.messages_layout.insertWidget(self.messages_layout.count() - 1, thinking_area)
                self._thinking_area = thinking_area  # 保存引用
            else:
                # 普通消息（user/assistant）：正常显示
                self.add_message(msg.content, msg.role)
        
        # 滚动到底部
        self._scroll_to_bottom()
        
        logger.info(f"已加载会话历史: {len(history)} 条消息")
    
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
            self._attach_file(file_path)
    
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
    
    def on_model_changed(self, model: str):
        """模型变化事件"""
        logger.info(f"切换模型: {model}")
        # 发出信号
        self.model_changed.emit(model)
        
        # 更新agent的客户端模型
        if self.agent:
            self.agent.deepseek_client.set_model(model)
    
    def on_deep_think_state_changed(self, enabled: bool):
        """深度思考状态变化事件"""
        self._deep_think_enabled = enabled
        logger.info(f"深度思考模式{'启用' if enabled else '禁用'}")
        self.thinking_state_changed.emit(enabled)
    
    def set_deep_think_enabled(self, enabled: bool):
        """设置深度思考启用状态"""
        self.deep_think_btn.set_enabled(enabled)
    
    def is_deep_think_enabled(self) -> bool:
        """获取深度思考启用状态"""
        return self._deep_think_enabled
    
    def get_current_model(self) -> str:
        """获取当前选择的模型"""
        return self.model_selector.get_current_model()
    
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
                    self._attach_file(file_path)
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
