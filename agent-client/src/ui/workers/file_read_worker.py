"""
文件读取异步工作器

在后台线程中读取文件内容，避免在主线程中阻塞。
"""

import logging
import os
from typing import List, Tuple

from .base_worker import BaseWorker
from utils.file_processor import extract_file_text

logger = logging.getLogger(__name__)


class FileReadWorker(BaseWorker):
    """
    文件读取异步工作器
    
    在后台线程中读取多个文件的内容，通过finished信号返回结果。
    结果格式: List[Tuple[str, str]] - [(文件路径, 文件内容), ...]
    """
    
    def __init__(self, file_paths: List[str], parent=None):
        """
        初始化文件读取工作器
        
        Args:
            file_paths: 要读取的文件路径列表
            parent: 父对象
        """
        super().__init__(parent)
        self.file_paths = file_paths
        
    def run(self):
        """执行文件读取任务"""
        try:
            results = []
            total_files = len(self.file_paths)
            
            logger.info(f"开始异步读取 {total_files} 个文件")
            
            for i, file_path in enumerate(self.file_paths):
                if self.is_cancelled():
                    logger.info("文件读取任务已取消")
                    return
                
                # 发送进度信号
                progress_percent = int((i / total_files) * 100) if total_files > 0 else 0
                self._safe_emit_progress(progress_percent, f"正在读取: {os.path.basename(file_path)}")
                
                if not os.path.exists(file_path):
                    logger.warning(f"文件不存在: {file_path}")
                    continue
                
                try:
                    content = extract_file_text(file_path)
                    results.append((file_path, content))
                    logger.info(f"读取文件成功: {file_path} ({len(content)} 字符)")
                except Exception as e:
                    error_msg = f"读取文件失败: {file_path}, {str(e)}"
                    logger.error(error_msg)
                    # 继续处理其他文件，不中断
            
            # 发送完成信号
            self._safe_emit_progress(100, "文件读取完成")
            self._safe_emit_finished(results)
            
            logger.info(f"文件读取任务完成，成功读取 {len(results)}/{total_files} 个文件")
            
        except Exception as e:
            error_msg = f"文件读取任务失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._safe_emit_error(error_msg)
