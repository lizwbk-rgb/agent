"""
历史会话记录页面组件

显示历史会话列表，支持点击加载历史会话
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QFrame,
    QScrollArea,
    QAbstractItemView,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QCursor


# 配置日志
logger = logging.getLogger(__name__)


class HistoryItemWidget(QFrame):
    """历史会话项组件"""
    
    clicked = pyqtSignal(str)  # 会话ID信号
    title_edited = pyqtSignal(str, str)  # 会话ID, 新标题信号
    delete_requested = pyqtSignal(str)  # 会话ID信号 - 删除请求
    
    def __init__(self, conversation: Dict[str, Any], parent=None):
        """
        初始化历史会话项
        
        Args:
            conversation: 会话数据字典
            parent: 父组件
        """
        super().__init__(parent)
        self.conversation = conversation
        self._parent_widget = parent  # 保存父组件引用用于右键菜单
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # 标题行
        title_layout = QHBoxLayout()
        
        # 会话标题（可编辑）
        self.title_label = QLabel(self.conversation.get("title", "新对话"))
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #333;")
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        # 修改标题按钮
        edit_title_btn = QPushButton("✏️")
        edit_title_btn.setToolTip("修改标题")
        edit_title_btn.clicked.connect(lambda: self.on_edit_title())
        edit_title_btn.setFixedSize(28, 28)
        edit_title_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ddd;
                border-radius: 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #2196F3;
            }
        """)
        title_layout.addWidget(edit_title_btn)
        
        # 删除按钮
        delete_btn = QPushButton("×")
        delete_btn.setToolTip("删除会话")
        delete_btn.clicked.connect(lambda: self.on_delete_conversation())
        delete_btn.setFixedSize(28, 28)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ddd;
                border-radius: 14px;
                font-size: 16px;
                font-weight: bold;
                color: #999;
            }
            QPushButton:hover {
                background-color: #ffebee;
                border-color: #f44336;
                color: #f44336;
            }
        """)
        title_layout.addWidget(delete_btn)
        
        # 消息数量
        msg_count = self.conversation.get("message_count", 0)
        count_label = QLabel(f"{msg_count} 条消息")
        count_font = QFont()
        count_font.setPointSize(11)
        count_label.setFont(count_font)
        count_label.setStyleSheet("color: #999;")
        title_layout.addWidget(count_label)
        
        layout.addLayout(title_layout)
        
        # 最后更新时间
        updated_at = self.conversation.get("updated_at", "")
        if updated_at:
            try:
                # 解析时间字符串
                dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                delta = now - dt
                
                if delta.days == 0:
                    time_str = dt.strftime("%H:%M")
                elif delta.days == 1:
                    time_str = "昨天 " + dt.strftime("%H:%M")
                elif delta.days < 7:
                    time_str = f"{delta.days}天前"
                else:
                    time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = updated_at
        else:
            time_str = "未知时间"
        
        time_label = QLabel(time_str)
        time_font = QFont()
        time_font.setPointSize(11)
        time_label.setFont(time_font)
        time_label.setStyleSheet("color: #999;")
        layout.addWidget(time_label)
        
        # 设置样式
        self.setStyleSheet("""
            HistoryItemWidget {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            HistoryItemWidget:hover {
                background-color: #f5f5f5;
                border-color: #2196F3;
            }
        """)
        
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    def minimumHeight(self):
        """最小高度"""
        return 60
    
    def sizeHint(self):
        """推荐大小"""
        return QSize(self.width(), 60)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        super().mousePressEvent(event)
        
        # 右键点击显示菜单
        if event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPos())
        else:
            self.clicked.emit(self.conversation["id"])
    
    def show_context_menu(self, pos):
        """显示右键菜单"""
        from PyQt6.QtWidgets import QMenu, QAction
        
        menu = QMenu(self)
        
        # 加载会话
        load_action = QAction("加载会话", self)
        load_action.triggered.connect(lambda: self.clicked.emit(self.conversation["id"]))
        menu.addAction(load_action)
        
        # 编辑标题
        edit_action = QAction("编辑标题", self)
        edit_action.triggered.connect(self.on_edit_title)
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        # 删除会话
        delete_action = QAction("删除会话", self)
        delete_action.triggered.connect(self.on_delete_conversation)
        menu.addAction(delete_action)
        
        menu.exec(pos)
    
    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件 - 编辑标题"""
        self.on_edit_title()
    
    def on_edit_title(self):
        """编辑标题"""
        from PyQt6.QtWidgets import QInputDialog
        current_title = self.conversation.get("title", "新对话")
        new_title, ok = QInputDialog.getText(
            self, 
            "编辑标题", 
            "请输入新的会话标题:", 
            text=current_title
        )
        if ok and new_title.strip():
            self.title_edited.emit(self.conversation["id"], new_title.strip())
    
    def update_title(self, new_title: str):
        """更新标题显示"""
        self.title_label.setText(new_title)
        self.conversation["title"] = new_title
    
    def on_delete_conversation(self):
        """删除会话"""
        from PyQt6.QtWidgets import QMessageBox
        
        conv_id = self.conversation["id"]
        title = self.conversation.get("title", "新对话")
        
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除会话「{title}」吗？此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"请求删除会话: {conv_id}")
            self.delete_requested.emit(conv_id)


class HistoryWidget(QWidget):
    """
    历史会话记录组件
    
    显示历史会话列表，支持点击加载历史会话
    """
    
    # 信号
    conversation_selected = pyqtSignal(str)  # 会话ID信号
    new_conversation_requested = pyqtSignal()   # 新建对话请求信号
    back_requested = pyqtSignal()              # 返回请求信号
    conversation_deleted = pyqtSignal(str)      # 会话删除信号
    
    def __init__(
        self,
        agent=None,
        parent: QWidget = None
    ):
        """
        初始化历史会话记录组件
        
        Args:
            agent: Agent实例
            parent: 父组件
        """
        super().__init__(parent)
        
        self.agent = agent
        self.conversations: List[Dict[str, Any]] = []
        
        self.setup_ui()
        self.load_conversations()
        
        logger.info("历史会话记录组件初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 标题栏
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #fff;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 12, 16, 12)
        
        # 返回按钮
        self.back_btn = QPushButton("← 返回")
        self.back_btn.setToolTip("返回会话页面")
        self.back_btn.clicked.connect(self.back_requested.emit)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                color: #666;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #2196F3;
                color: #2196F3;
            }
        """)
        header_layout.addWidget(self.back_btn)
        
        title_label = QLabel("历史会话记录")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_histories)
        refresh_btn.setMinimumHeight(30)
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #fff;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
        """)
        header_layout.addWidget(refresh_btn)
        
        main_layout.addWidget(header_widget)
        
        # 会话列表容器
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #f5f5f5;
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
        
        # 会话列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.itemClicked.connect(self.on_conversation_item_clicked)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                border: none;
                padding: 4px 8px;
                background-color: transparent;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        
        scroll_area.setWidget(self.list_widget)
        main_layout.addWidget(scroll_area)
        
        # 底部按钮栏
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet("""
            QWidget {
                background-color: #fff;
                border-top: 1px solid #e0e0e0;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(16, 12, 16, 12)
        
        # 新建对话按钮
        new_conv_btn = QPushButton("+ 新建对话")
        new_conv_btn.clicked.connect(self.on_new_conversation)
        new_conv_btn.setMinimumHeight(36)
        new_conv_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        bottom_layout.addWidget(new_conv_btn)
        
        bottom_layout.addStretch()
        
        main_layout.addWidget(bottom_widget)
    
    def load_conversations(self):
        """加载会话列表"""
        if not self.agent:
            logger.warning("Agent未设置，无法加载会话列表")
            return
        
        try:
            self.conversations = self.agent.get_conversations()
            self.display_conversations()
            logger.info(f"加载了 {len(self.conversations)} 个会话")
        except Exception as e:
            logger.error(f"加载会话列表失败: {str(e)}")
            self.show_empty_state()
    
    def display_conversations(self):
        """显示会话列表"""
        self.list_widget.clear()
        
        if not self.conversations:
            self.show_empty_state()
            return
        
        # 添加会话项
        for conv in self.conversations:
            item = QListWidgetItem()
            item_widget = HistoryItemWidget(conv)
            item_widget.clicked.connect(self.on_history_item_clicked)
            item_widget.title_edited.connect(self.on_title_edited)
            item_widget.delete_requested.connect(self.on_delete_conversation)
            
            # 设置sizeHint确保widget可见
            item.setSizeHint(QSize(item_widget.sizeHint().width(), 70))
            
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, item_widget)
    
    def show_empty_state(self):
        """显示空状态"""
        self.list_widget.clear()
        # 可以添加空状态提示
        logger.info("会话列表为空")
    
    def refresh_histories(self):
        """刷新会话列表"""
        logger.info("刷新会话列表")
        self.load_conversations()
    
    def on_conversation_item_clicked(self, item: QListWidgetItem):
        """会话项点击事件"""
        # 这个方法不需要处理，因为点击逻辑在HistoryItemWidget中
        pass
    
    def on_history_item_clicked(self, conversation_id: str):
        """历史会话项点击事件"""
        logger.info(f"点击历史会话: {conversation_id}")
        self.conversation_selected.emit(conversation_id)
    
    def on_title_edited(self, conversation_id: str, new_title: str):
        """标题编辑事件"""
        logger.info(f"编辑会话标题: {conversation_id} -> {new_title}")
        if self.agent:
            self.agent.update_conversation_title(conversation_id, new_title)
            # 刷新列表以显示新标题
            self.load_conversations()
        else:
            logger.warning("Agent未设置，无法更新会话标题")
    
    def on_delete_conversation(self, conversation_id: str):
        """删除会话事件"""
        logger.info(f"删除会话: {conversation_id}")
        if self.agent:
            self.agent.delete_conversation(conversation_id)
            # 刷新列表
            self.load_conversations()
            # 发出删除信号
            self.conversation_deleted.emit(conversation_id)
        else:
            logger.warning("Agent未设置，无法删除会话")
    
    def on_new_conversation(self):
        """新建对话按钮点击事件"""
        logger.info("请求新建对话")
        self.new_conversation_requested.emit()
    
    def update_agent(self, agent):
        """更新Agent实例"""
        self.agent = agent
        self.load_conversations()


# 便捷函数
def create_history_widget(agent=None, parent: QWidget = None) -> HistoryWidget:
    """创建历史会话记录组件"""
    return HistoryWidget(agent, parent)
