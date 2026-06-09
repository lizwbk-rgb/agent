"""
思考区域组件

可折叠的深度思考内容显示区域，浅灰色背景
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QCursor

from ui.markdown_renderer import MarkdownRenderer

# 配置日志
logger = logging.getLogger(__name__)


class ThinkingArea(QFrame):
    """
    思考区域组件
    
    可折叠的深度思考内容显示区域
    """
    
    # 信号：展开/折叠状态变化
    expanded_changed = pyqtSignal(bool)
    
    def __init__(
        self,
        parent=None
    ):
        """
        初始化思考区域
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        
        self._is_expanded = False
        self._has_content = False
        self._auto_expanded = False  # 标记是否已自动展开（首次收到内容时）
        
        self.setup_ui()
        self.hide()  # 默认隐藏
        
        logger.info("思考区域组件初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 折叠标题栏
        self.header = QFrame()
        self.header.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.header.setMaximumHeight(40)
        self.header.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #e0e0e0;
                border-radius: 6px 6px 0 0;
            }
            QFrame:hover {
                background-color: #e8e8e8;
            }
        """)
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)
        
        # 展开/折叠按钮
        self.toggle_btn = QLabel("▶")
        toggle_font = QFont()
        toggle_font.setPointSize(10)
        toggle_font.setBold(True)
        self.toggle_btn.setFont(toggle_font)
        self.toggle_btn.setStyleSheet("color: #666;")
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header_layout.addWidget(self.toggle_btn)
        
        # 标题
        self.title_label = QLabel("思考过程")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #333;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # 加载指示器
        self.loading_label = QLabel("思考中...")
        self.loading_label.setStyleSheet("color: #FF9800;")
        self.loading_label.hide()
        header_layout.addWidget(self.loading_label)
        
        layout.addWidget(self.header)
        
        # 内容区域
        self.content_container = QFrame()
        self.content_container.setMaximumHeight(0)
        self.content_container.setStyleSheet("""
            QFrame {
                background-color: #f9f9f9;
                border: 1px solid #e0e0e0;
                border-top: none;
                border-radius: 0 0 6px 6px;
            }
        """)
        
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(0)
        
        # 思考内容显示 - 不限制高度，让它自适应内容
        self.content_browser = QTextBrowser()
        self.content_browser.setReadOnly(True)
        # 禁用滚动条，让内容自动展开
        self.content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 设置大小策略为Expanding，让内容区域自动展开
        from PyQt6.QtWidgets import QSizePolicy
        self.content_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                background-color: transparent;
                font-size: 12px;
                color: #666;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
        """)
        content_layout.addWidget(self.content_browser)
        
        layout.addWidget(self.content_container)
        
        # 连接点击事件
        self.header.mousePressEvent = self.on_header_clicked
    
    def on_header_clicked(self, event):
        """
        标题栏点击事件
        
        Args:
            event: 鼠标事件
        """
        self.toggle()
    
    def toggle(self):
        """切换展开/折叠状态"""
        self._is_expanded = not self._is_expanded
        
        # 更新UI
        if self._is_expanded:
            self.toggle_btn.setText("▼")
            self.content_container.setMaximumHeight(16777215)  # 大值，允许展开
        else:
            self.toggle_btn.setText("▶")
            self.content_container.setMaximumHeight(0)
        
        # 发出信号
        self.expanded_changed.emit(self._is_expanded)
        
        logger.info(f"思考区域{'展开' if self._is_expanded else '折叠'}")
    
    def expand(self):
        """展开区域"""
        if not self._is_expanded:
            self.toggle()
    
    def collapse(self):
        """折叠区域"""
        if self._is_expanded:
            self.toggle()
    
    def set_content(self, content: str):
        """
        设置思考内容
        
        Args:
            content: 思考内容
        """
        self._has_content = bool(content)
        
        # 渲染Markdown
        renderer = MarkdownRenderer()
        html_content = renderer.render(content)
        
        self.content_browser.setHtml(html_content)
        
        # 显示组件
        if self._has_content:
            self.show()
            self.loading_label.hide()
        
        # 延迟调整内容区域高度，确保HTML渲染完成
        QTimer.singleShot(100, self._adjust_content_height)
        
        logger.info(f"设置思考内容: {len(content)} 字符")
    
    def update_content(self, content: str):
        """
        更新思考内容（流式更新）
        
        Args:
            content: 思考内容
        """
        self._has_content = bool(content)
        
        # 渲染Markdown
        renderer = MarkdownRenderer()
        html_content = renderer.render(content)
        
        self.content_browser.setHtml(html_content)
        
        # 延迟调整内容区域高度，确保HTML渲染完成
        QTimer.singleShot(100, self._adjust_content_height)
        
        # 显示组件
        if self._has_content and not self.isVisible():
            self.show()
        
        # 如果有内容，隐藏加载标签（内容本身就是思考过程）
        if self._has_content:
            self.loading_label.hide()
            # 自动展开内容区域（仅首次收到内容时）
            if not self._is_expanded and not self._auto_expanded:
                self.expand()
                self._auto_expanded = True
        else:
            # 没有内容时显示"思考中..."
            self.loading_label.show()
    
    def clear_content(self):
        """清空内容"""
        self.content_browser.clear()
        self._has_content = False
        self.loading_label.hide()
        
        # 如果没有内容，隐藏组件
        if not self._has_content:
            self.hide()
        
        logger.info("思考内容已清空")
    
    def show_thinking(self):
        """显示思考中状态"""
        self._has_content = True
        self.show()
        self.loading_label.setText("思考中...")
        self.loading_label.show()
        self.content_browser.setHtml("")
        self._auto_expanded = False  # 重置自动展开标记
        logger.info("显示思考中状态")
    
    def set_thinking_finished(self):
        """设置思考结束状态"""
        self.loading_label.setText("思考结束")
        logger.info("设置思考结束状态")
    
    def hide_thinking(self):
        """隐藏思考区域"""
        self.hide()
        self.loading_label.hide()
        logger.info("隐藏思考区域")
    
    def is_expanded(self) -> bool:
        """
        获取展开状态
        
        Returns:
            bool: 是否展开
        """
        return self._is_expanded
    
    def has_content(self) -> bool:
        """
        获取是否有内容
        
        Returns:
            bool: 是否有内容
        """
        return self._has_content
    
    def set_expanded(self, expanded: bool):
        """
        设置展开状态
        
        Args:
            expanded: 是否展开
        """
        if expanded != self._is_expanded:
            self._is_expanded = expanded
            if expanded:
                self.toggle_btn.setText("▼")
                self.content_container.setMaximumHeight(16777215)
                # 展开后调整高度
                self._adjust_content_height()
            else:
                self.toggle_btn.setText("▶")
                self.content_container.setMaximumHeight(0)
    
    def _adjust_content_height(self):
        """调整内容区域高度以显示完整内容"""
        if not self._has_content:
            return
        
        # 获取文档高度
        doc = self.content_browser.document()
        doc_height = doc.size().height()
        
        # 加上内边距
        margins = self.content_container.layout().contentsMargins()
        total_height = int(doc_height) + margins.top() + margins.bottom() + 20
        
        # 限制最大高度为400px，避免过大
        max_height = 400
        if total_height > max_height:
            total_height = max_height
            # 超过最大高度时启用滚动条
            self.content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            # 未超过最大高度时禁用滚动条
            self.content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 设置内容浏览器最小高度（让它自适应）
        self.content_browser.setMinimumHeight(int(doc_height) + 10)
        self.content_browser.setMaximumHeight(16777215)  # 允许增长
        
        # 如果已展开，调整容器高度
        if self._is_expanded:
            self.content_container.setMaximumHeight(total_height)
        
        logger.info(f"调整内容高度: {total_height}px")
