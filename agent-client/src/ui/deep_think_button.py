"""
深度思考按钮组件

提供深度思考模式切换功能，开启时按钮高亮显示
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QPushButton,
    QFrame,
    QLabel,
    QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize

# 配置日志
logger = logging.getLogger(__name__)


class DeepThinkButton(QFrame):
    """
    深度思考按钮组件
    
    可切换的深度思考模式按钮，开启时高亮显示
    """
    
    # 信号：深度思考状态变化
    state_changed = pyqtSignal(bool)
    
    def __init__(
        self,
        parent=None,
        enabled: bool = False
    ):
        """
        初始化深度思考按钮
        
        Args:
            parent: 父组件
            enabled: 初始启用状态
        """
        super().__init__(parent)
        
        self._is_enabled = enabled
        
        self.setup_ui()
        self.update_style()
        
        logger.info(f"深度思考按钮初始化完成 - 初始状态: {'启用' if enabled else '禁用'}")
    
    def setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 深度思考按钮
        self.button = QPushButton("深度思考")
        self.button.setCheckable(True)
        self.button.setChecked(self._is_enabled)
        self.button.setMinimumHeight(36)
        self.button.setMinimumWidth(100)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 连接信号
        self.button.toggled.connect(self.on_toggled)
        
        layout.addWidget(self.button)
    
    def update_style(self):
        """更新按钮样式"""
        if self._is_enabled:
            # 启用状态：高亮样式
            self.button.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
                QPushButton:pressed {
                    background-color: #E65100;
                }
            """)
        else:
            # 禁用状态：普通样式
            self.button.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    color: #666;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #efefef;
                    border-color: #999;
                }
                QPushButton:pressed {
                    background-color: #e0e0e0;
                }
            """)
    
    def on_toggled(self, checked: bool):
        """
        按钮切换事件
        
        Args:
            checked: 是否选中
        """
        self._is_enabled = checked
        self.update_style()
        logger.info(f"深度思考模式切换: {'启用' if checked else '禁用'}")
        self.state_changed.emit(checked)
    
    def set_enabled(self, enabled: bool):
        """
        设置启用状态
        
        Args:
            enabled: 是否启用
        """
        if enabled != self._is_enabled:
            self._is_enabled = enabled
            self.button.setChecked(enabled)
            self.update_style()
            logger.info(f"设置深度思考模式: {'启用' if enabled else '禁用'}")
    
    def is_enabled(self) -> bool:
        """
        获取启用状态
        
        Returns:
            bool: 是否启用
        """
        return self._is_enabled
    
    def toggle(self):
        """切换状态"""
        self.set_enabled(not self._is_enabled)
