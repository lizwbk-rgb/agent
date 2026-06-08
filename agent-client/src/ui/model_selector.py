"""
模型选择器组件

提供模型下拉选择功能，支持deepseek-v4-pro和deepseek-v4-flash
"""

import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QHBoxLayout,
    QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt

from config import get_config

# 配置日志
logger = logging.getLogger(__name__)


class ModelSelector(QFrame):
    """
    模型选择器组件
    
    提供模型下拉选择功能
    """
    
    # 信号：模型变化
    model_changed = pyqtSignal(str)
    
    def __init__(
        self,
        parent=None,
        current_model: Optional[str] = None
    ):
        """
        初始化模型选择器
        
        Args:
            parent: 父组件
            current_model: 当前选择的模型
        """
        super().__init__(parent)
        
        self.config = get_config()
        self._current_model = current_model or self.config.DEFAULT_MODEL
        
        self.setup_ui()
        self.load_models()
        self.set_current_model(self._current_model)
        
        logger.info(f"模型选择器初始化完成 - 当前模型: {self._current_model}")
    
    def setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 模型标签
        label = QLabel("模型:")
        font = label.font()
        font.setPointSize(11)
        label.setFont(font)
        layout.addWidget(label)
        
        # 模型下拉框
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(150)
        self.model_combo.setStyleSheet("""
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
            QComboBox QAbstractItemView::item {
                padding: 6px 12px;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.model_combo)
        
        # 连接信号
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
    
    def load_models(self):
        """加载可用模型列表"""
        models = self.config.AVAILABLE_MODELS
        self.model_combo.clear()
        self.model_combo.addItems(models)
        logger.info(f"加载模型列表: {models}")
    
    def set_current_model(self, model: str):
        """
        设置当前模型
        
        Args:
            model: 模型名称
        """
        index = self.model_combo.findText(model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
            self._current_model = model
            logger.info(f"设置当前模型: {model}")
        else:
            logger.warning(f"模型 {model} 不存在，使用默认模型")
            self._current_model = self.config.DEFAULT_MODEL
    
    def get_current_model(self) -> str:
        """
        获取当前选择的模型
        
        Returns:
            str: 模型名称
        """
        return self.model_combo.currentText()
    
    def on_model_changed(self, index: int):
        """
        模型变化事件
        
        Args:
            index: 新选择的索引
        """
        model = self.model_combo.currentText()
        if model != self._current_model:
            self._current_model = model
            logger.info(f"模型切换: {model}")
            self.model_changed.emit(model)
    
    def refresh_models(self):
        """刷新模型列表"""
        self.config = get_config()
        self.load_models()
        self.set_current_model(self._current_model)
        logger.info("模型列表已刷新")
