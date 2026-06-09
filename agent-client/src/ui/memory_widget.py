"""
记忆管理UI组件

提供记忆列表显示、刷新、删除、清空等功能
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
    QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

from memory_manager import MemoryManager, Memory
from utils.helpers import truncate_text, format_relative_time

# 配置日志
logger = logging.getLogger(__name__)


class MemoryItemWidget(QFrame):
    """记忆项组件"""
    
    clicked = pyqtSignal(str)  # 记忆ID信号
    
    def __init__(self, memory: Memory, parent=None):
        """
        初始化记忆项
        
        Args:
            memory: 记忆对象
            parent: 父组件
        """
        super().__init__(parent)
        self.memory = memory
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # ID标签
        id_label = QLabel(self.memory.id)
        id_font = QFont()
        id_font.setPointSize(9)
        id_font.setItalic(True)
        id_label.setFont(id_font)
        id_label.setStyleSheet("color: #999;")
        layout.addWidget(id_label)
        
        # 内容标签 - 完整显示记忆内容
        content_label = QLabel(self.memory.content)
        content_font = QFont()
        content_font.setPointSize(11)
        content_label.setFont(content_font)
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        # 元数据
        meta_parts = []
        
        # 相关度分数
        if self.memory.score > 0:
            meta_parts.append(f"相关度: {self.memory.score:.2f}")
        
        # 时间
        if self.memory.created_at:
            relative_time = format_relative_time(self.memory.created_at)
            meta_parts.append(f"{relative_time}")
        
        if meta_parts:
            meta_label = QLabel(" • ".join(meta_parts))
            meta_font = QFont()
            meta_font.setPointSize(9)
            meta_label.setFont(meta_font)
            meta_label.setStyleSheet("color: #666;")
            layout.addWidget(meta_label)
        
        # 设置样式
        self.setStyleSheet("""
            MemoryItemWidget {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
            }
            MemoryItemWidget:hover {
                background-color: #e9ecef;
                border-color: #dee2e6;
            }
        """)
        
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        super().mousePressEvent(event)
        self.clicked.emit(self.memory.id)


class MemoryWidget(QWidget):
    """
    记忆管理组件
    
    显示记忆列表，支持刷新、删除、清空操作
    分为"系统提取"和"用户自定义"两个页签
    """
    
    # 信号
    memory_deleted = pyqtSignal(str)  # 记忆删除信号
    memories_cleared = pyqtSignal()    # 记忆清空信号
    memory_selected = pyqtSignal(str)  # 记忆选中信号
    back_requested = pyqtSignal()      # 返回请求信号
    
    def __init__(
        self,
        memory_manager: MemoryManager = None,
        parent: QWidget = None
    ):
        """
        初始化记忆管理组件
        
        Args:
            memory_manager: 记忆管理器实例
            parent: 父组件
        """
        super().__init__(parent)
        
        self.memory_manager = memory_manager or MemoryManager()
        self.memories: List[Memory] = []
        self.system_memories: List[Memory] = []  # 系统提取的记忆
        self.custom_memories: List[Memory] = []  # 用户自定义的记忆
        
        self.setup_ui()
        self.load_memories()
        
        logger.info("记忆管理组件初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # 标题栏
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
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
        
        title_label = QLabel("记忆管理")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        # 记忆数量
        self.count_label = QLabel("0 条记忆")
        count_font = QFont()
        count_font.setPointSize(10)
        self.count_label.setFont(count_font)
        self.count_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.count_label)
        
        header_layout.addStretch()
        
        main_layout.addLayout(header_layout)
        
        # 按钮栏
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_memories)
        refresh_btn.setMinimumHeight(30)
        button_layout.addWidget(refresh_btn)
        
        # 删除按钮
        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(self.delete_selected_memory)
        delete_btn.setMinimumHeight(30)
        button_layout.addWidget(delete_btn)
        
        # 清空按钮
        clear_btn = QPushButton("清空全部")
        clear_btn.clicked.connect(self.clear_all_memories)
        clear_btn.setMinimumHeight(30)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffcccc;
                color: #cc0000;
                border: 1px solid #ff9999;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ff9999;
            }
        """)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        # 页签组件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 20px;
                font-size: 12px;
                color: #666;
            }
            QTabBar::tab:selected {
                background-color: #fff;
                color: #2196F3;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e8e8e8;
            }
        """)
        
        # 系统提取页
        self.system_tab = QWidget()
        system_layout = QVBoxLayout(self.system_tab)
        system_layout.setContentsMargins(8, 8, 8, 8)
        system_layout.setSpacing(0)
        
        self.system_list_widget = QListWidget()
        self.system_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.system_list_widget.itemClicked.connect(self.on_system_memory_item_clicked)
        self.system_list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                border: none;
                padding: 4px 8px;
            }
        """)
        system_layout.addWidget(self.system_list_widget)
        
        # 系统提取空状态
        self.system_empty_label = QLabel("暂无系统提取的记忆")
        self.system_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.system_empty_label.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 14px;
                padding: 40px;
                background-color: transparent;
            }
        """)
        self.system_empty_label.hide()
        system_layout.addWidget(self.system_empty_label)
        
        self.tab_widget.addTab(self.system_tab, "系统提取")
        
        # 用户自定义页
        self.custom_tab = QWidget()
        custom_layout = QVBoxLayout(self.custom_tab)
        custom_layout.setContentsMargins(8, 8, 8, 8)
        custom_layout.setSpacing(0)
        
        self.custom_list_widget = QListWidget()
        self.custom_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.custom_list_widget.itemClicked.connect(self.on_custom_memory_item_clicked)
        self.custom_list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                border: none;
                padding: 4px 8px;
            }
        """)
        custom_layout.addWidget(self.custom_list_widget)
        
        # 用户自定义空状态
        self.custom_empty_label = QLabel("暂无用户自定义记忆")
        self.custom_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_empty_label.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 14px;
                padding: 40px;
                background-color: transparent;
            }
        """)
        self.custom_empty_label.hide()
        custom_layout.addWidget(self.custom_empty_label)
        
        self.tab_widget.addTab(self.custom_tab, "用户自定义")
        
        main_layout.addWidget(self.tab_widget, 1)  # stretch=1，填充剩余空间
        
        # 设置整体样式
        self.setStyleSheet("""
            MemoryWidget {
                background-color: #fff;
                border: 1px solid #e9ecef;
                border-radius: 8px;
            }
        """)
    
    def load_memories(self):
        """加载记忆列表"""
        try:
            self.memories = self.memory_manager.get_all()
            # 分类记忆
            self.system_memories = []
            self.custom_memories = []
            for memory in self.memories:
                source = memory.metadata.get('source', '') if memory.metadata else ''
                if source == 'auto_extract':
                    self.system_memories.append(memory)
                else:
                    self.custom_memories.append(memory)
            self.display_memories()
            logger.info(f"加载了 {len(self.memories)} 条记忆（系统提取: {len(self.system_memories)}, 用户自定义: {len(self.custom_memories)}）")
        except Exception as e:
            logger.error(f"加载记忆失败: {str(e)}")
            self.show_empty_state()
    
    def display_memories(self):
        """显示记忆列表"""
        # 显示系统提取的记忆
        self.system_list_widget.clear()
        if self.system_memories:
            self.system_list_widget.show()
            self.system_empty_label.hide()
            for memory in self.system_memories:
                item = QListWidgetItem()
                item_widget = MemoryItemWidget(memory)
                item_widget.clicked.connect(self.on_memory_clicked)
                item.setSizeHint(item_widget.sizeHint())
                self.system_list_widget.addItem(item)
                self.system_list_widget.setItemWidget(item, item_widget)
        else:
            self.system_list_widget.hide()
            self.system_empty_label.show()
        
        # 显示用户自定义的记忆
        self.custom_list_widget.clear()
        if self.custom_memories:
            self.custom_list_widget.show()
            self.custom_empty_label.hide()
            for memory in self.custom_memories:
                item = QListWidgetItem()
                item_widget = MemoryItemWidget(memory)
                item_widget.clicked.connect(self.on_memory_clicked)
                item.setSizeHint(item_widget.sizeHint())
                self.custom_list_widget.addItem(item)
                self.custom_list_widget.setItemWidget(item, item_widget)
        else:
            self.custom_list_widget.hide()
            self.custom_empty_label.show()
        
        # 更新计数
        total = len(self.system_memories) + len(self.custom_memories)
        self.count_label.setText(f"{total} 条记忆")
    
    def show_empty_state(self):
        """显示空状态"""
        self.system_list_widget.hide()
        self.system_list_widget.clear()
        self.system_empty_label.show()
        self.custom_list_widget.hide()
        self.custom_list_widget.clear()
        self.custom_empty_label.show()
        self.count_label.setText("0 条记忆")
    
    def refresh_memories(self):
        """刷新记忆列表"""
        logger.info("刷新记忆列表")
        self.load_memories()
    
    def delete_selected_memory(self):
        """删除选中的记忆"""
        memory = self.get_selected_memory()
        
        if not memory:
            QMessageBox.warning(self, "提示", "请先选择要删除的记忆")
            return
        
        # 确认对话框
        confirm_msg = f"确定要删除记忆 [{memory.id}] 吗？\n\n{truncate_text(memory.content, 100)}"
        reply = QMessageBox.question(
            self,
            "确认删除",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.memory_manager.delete(memory.id)
                
                if success:
                    logger.info(f"删除成功: {memory.id}")
                    # 从对应的列表中移除
                    if memory in self.system_memories:
                        self.system_memories.remove(memory)
                    elif memory in self.custom_memories:
                        self.custom_memories.remove(memory)
                    if memory in self.memories:
                        self.memories.remove(memory)
                    self.display_memories()
                    self.memory_deleted.emit(memory.id)
                    QMessageBox.information(self, "成功", "记忆已删除")
                else:
                    QMessageBox.warning(self, "失败", "删除记忆失败")
                    
            except Exception as e:
                logger.error(f"删除记忆失败: {str(e)}")
                QMessageBox.warning(self, "错误", f"删除记忆时发生错误: {str(e)}")
    
    def clear_all_memories(self):
        """清空所有记忆"""
        if not self.memories:
            QMessageBox.information(self, "提示", "没有记忆可以清空")
            return
        
        # 确认对话框
        confirm_msg = f"确定要清空所有 {len(self.memories)} 条记忆吗？\n\n此操作不可撤销！"
        reply = QMessageBox.question(
            self,
            "确认清空",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.memory_manager.clear()
                
                if success:
                    logger.info("清空记忆成功")
                    self.memories.clear()
                    self.show_empty_state()
                    self.memories_cleared.emit()
                    QMessageBox.information(self, "成功", "所有记忆已清空")
                else:
                    QMessageBox.warning(self, "失败", "清空记忆失败")
                    
            except Exception as e:
                logger.error(f"清空记忆失败: {str(e)}")
                QMessageBox.warning(self, "错误", f"清空记忆时发生错误: {str(e)}")
    
    def on_memory_item_clicked(self, item: QListWidgetItem):
        """记忆项点击事件（兼容旧代码）"""
        pass
    
    def on_system_memory_item_clicked(self, item: QListWidgetItem):
        """系统提取记忆项点击事件"""
        widget = self.system_list_widget.itemWidget(item)
        if widget:
            self.memory_selected.emit(widget.memory.id)
    
    def on_custom_memory_item_clicked(self, item: QListWidgetItem):
        """用户自定义记忆项点击事件"""
        widget = self.custom_list_widget.itemWidget(item)
        if widget:
            self.memory_selected.emit(widget.memory.id)
    
    def on_memory_clicked(self, memory_id: str):
        """记忆点击事件"""
        self.memory_selected.emit(memory_id)
    
    def get_selected_memory(self) -> Optional[Memory]:
        """获取选中的记忆"""
        # 根据当前页签获取选中的记忆
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # 系统提取页
            current_row = self.system_list_widget.currentRow()
            if current_row >= 0 and current_row < len(self.system_memories):
                return self.system_memories[current_row]
        else:  # 用户自定义页
            current_row = self.custom_list_widget.currentRow()
            if current_row >= 0 and current_row < len(self.custom_memories):
                return self.custom_memories[current_row]
        
        return None
    
    def get_memory_count(self) -> int:
        """获取记忆数量"""
        return len(self.memories)
    
    def update_memory_manager(self, memory_manager: MemoryManager):
        """更新记忆管理器"""
        self.memory_manager = memory_manager
        self.load_memories()


# 便捷函数
def create_memory_widget(memory_manager: MemoryManager = None, parent: QWidget = None) -> MemoryWidget:
    """创建记忆管理组件"""
    return MemoryWidget(memory_manager, parent)
