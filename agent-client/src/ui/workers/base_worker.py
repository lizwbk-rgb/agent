"""
基础异步工作器类

所有异步工作器的基类，提供通用的线程管理和信号处理功能。
"""

import logging
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class BaseWorker(QThread):
    """
    异步工作器基类
    
    所有异步工作器应继承此类，并实现run方法。
    提供finished和error信号，用于通知操作完成或失败。
    """
    
    # 信号定义
    finished = pyqtSignal(object)  # 完成信号，传递结果
    error = pyqtSignal(str)  # 错误信号，传递错误信息
    progress = pyqtSignal(int, str)  # 进度信号，传递进度百分比和描述
    
    def __init__(self, parent=None):
        """
        初始化工作器
        
        Args:
            parent: 父对象
        """
        super().__init__(parent)
        self._is_cancelled = False
        self._error_occurred = False
        
    def cancel(self):
        """取消任务"""
        self._is_cancelled = True
        logger.info(f"{self.__class__.__name__} 任务已取消")
    
    def is_cancelled(self) -> bool:
        """检查任务是否已取消"""
        return self._is_cancelled
    
    def run(self):
        """
        执行任务，子类需重写此方法
        
        子类实现时应在适当位置检查self._is_cancelled，
        如果为True则应提前退出。
        """
        raise NotImplementedError("子类必须实现run方法")
    
    def _safe_emit_finished(self, result=None):
        """
        安全地发送finished信号
        
        Args:
            result: 结果数据
        """
        if not self._is_cancelled:
            self.finished.emit(result)
    
    def _safe_emit_error(self, error_msg: str):
        """
        安全地发送error信号
        
        Args:
            error_msg: 错误信息
        """
        self._error_occurred = True
        if not self._is_cancelled:
            self.error.emit(error_msg)
    
    def _safe_emit_progress(self, percent: int, description: str = ""):
        """
        安全地发送progress信号
        
        Args:
            percent: 进度百分比 (0-100)
            description: 进度描述
        """
        if not self._is_cancelled:
            self.progress.emit(percent, description)
