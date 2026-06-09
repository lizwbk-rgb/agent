"""
文件引用弹出组件

在输入框中输入"@"时弹出，用于选择工作区中的文件或文件夹进行引用
"""

import os
import logging
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QTextCursor


# 配置日志
logger = logging.getLogger(__name__)


class FileReferencePopup(QFrame):
    """
    文件引用弹出组件
    
    在输入框中输入"@"时弹出，显示工作区中的文件和文件夹列表
    """
    
    # 信号
    file_selected = pyqtSignal(str)  # 选中的文件路径
    
    def __init__(self, parent=None):
        """
        初始化文件引用弹出组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        
        self.workspace_path = None
        self.file_list = []  # 存储文件路径列表
        
        self.setup_ui()
        
        # 设置窗口标志：弹出窗口，无边框
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        
        logger.info("文件引用弹出组件初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        self.setFixedSize(300, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标题栏
        title_bar = QFrame()
        title_bar.setMaximumHeight(32)
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        
        title_layout = QVBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 4, 8, 4)
        
        title_label = QLabel("选择文件或文件夹")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        
        layout.addWidget(title_bar)
        
        # 文件列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: #fff;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.list_widget)
    
    def set_workspace(self, workspace_path: str):
        """
        设置工作区路径
        
        Args:
            workspace_path: 工作区路径
        """
        self.workspace_path = workspace_path
        self.refresh_file_list()
    
    def refresh_file_list(self):
        """刷新文件列表"""
        self.list_widget.clear()
        self.file_list = []
        
        if not self.workspace_path or not os.path.exists(self.workspace_path):
            return
        
        try:
            # 遍历工作区根目录
            for entry in os.listdir(self.workspace_path):
                # 跳过隐藏文件和目录
                if entry.startswith('.'):
                    continue
                
                entry_path = os.path.join(self.workspace_path, entry)
                entry_path = os.path.normpath(entry_path)  # 规范化路径，修复Windows混合分隔符问题

                # 添加到列表
                if os.path.isdir(entry_path):
                    item_text = f"📁 {entry}"
                else:
                    item_text = f"📄 {entry}"

                item = QListWidgetItem(item_text)
                self.list_widget.addItem(item)
                self.file_list.append(entry_path)
            
            logger.info(f"刷新文件列表完成: {len(self.file_list)} 项")
            
        except Exception as e:
            logger.error(f"刷新文件列表失败: {str(e)}")
    
    def show_at_cursor(self, cursor_global_pos: QPoint):
        """
        在光标位置显示弹出框
        
        Args:
            cursor_global_pos: 光标全局位置
        """
        if not self.workspace_path:
            logger.warning("工作区路径未设置，无法显示文件引用弹出框")
            return
        
        # 刷新文件列表
        self.refresh_file_list()
        
        if self.list_widget.count() == 0:
            logger.info("工作区为空，不显示文件引用弹出框")
            return
        
        # 计算弹出框位置（在光标下方）
        popup_x = cursor_global_pos.x()
        popup_y = cursor_global_pos.y() + 20
        
        self.move(popup_x, popup_y)
        self.show()
        self.list_widget.setFocus()
        
        logger.info("显示文件引用弹出框")
    
    def hide_popup(self):
        """隐藏弹出框"""
        self.hide()
        logger.info("隐藏文件引用弹出框")
    
    def on_item_clicked(self, item: QListWidgetItem):
        """列表项点击事件"""
        row = self.list_widget.row(item)
        if row >= 0 and row < len(self.file_list):
            file_path = self.file_list[row]
            logger.info(f"选择文件: {file_path}")
            
            # 发出信号
            self.file_selected.emit(file_path)
            
            # 隐藏弹出框
            self.hide_popup()
    
    def on_item_double_clicked(self, item: QListWidgetItem):
        """列表项双击事件"""
        self.on_item_clicked(item)
    
    def keyPressEvent(self, event):
        """按键事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide_popup()
        else:
            super().keyPressEvent(event)


# 便捷函数
def create_file_reference_popup(parent=None) -> FileReferencePopup:
    """创建文件引用弹出组件"""
    return FileReferencePopup(parent)
