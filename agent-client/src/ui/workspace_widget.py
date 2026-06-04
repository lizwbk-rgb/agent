"""
工作区组件

提供工作区路径设置、文件树浏览、文件内容预览、文件选择信号等功能
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QFrame,
    QLabel,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QSplitter,
    QMessageBox,
    QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QFont, QCursor, QDrag

from utils.helpers import truncate_text
from utils.file_processor import FileProcessor

# 配置日志
logger = logging.getLogger(__name__)


class WorkspaceWidget(QWidget):
    """
    工作区组件
    
    提供文件树浏览、文件预览、文件选择等功能
    """
    
    # 信号
    file_selected = pyqtSignal(str)  # 文件路径信号
    
    def __init__(self, parent: QWidget = None):
        """
        初始化工作区组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        
        self.workspace_path = None
        self.file_processor = FileProcessor()
        
        self.setup_ui()
        self._load_settings()
        
        logger.info("工作区组件初始化完成")
    
    def setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部工具栏
        toolbar = QFrame()
        toolbar.setMaximumHeight(40)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(8)
        
        # 路径标签
        path_label = QLabel("工作区:")
        path_font = QFont()
        path_font.setPointSize(10)
        path_label.setFont(path_font)
        toolbar_layout.addWidget(path_label)
        
        # 路径显示
        self.path_display = QLabel("未设置")
        self.path_display.setMaximumWidth(200)
        self.path_display.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 10px;
            }
        """)
        toolbar_layout.addWidget(self.path_display)
        
        toolbar_layout.addStretch()
        
        # 选择按钮
        select_btn = QPushButton("选择...")
        select_btn.setMinimumWidth(60)
        select_btn.setMaximumWidth(60)
        select_btn.clicked.connect(self.on_select_workspace)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #efefef;
            }
        """)
        toolbar_layout.addWidget(select_btn)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setMinimumWidth(60)
        refresh_btn.setMaximumWidth(60)
        refresh_btn.clicked.connect(self.refresh_file_tree)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #efefef;
            }
        """)
        toolbar_layout.addWidget(refresh_btn)
        
        main_layout.addWidget(toolbar)
        
        # 主体区域：文件树 + 预览
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["文件", "大小", "修改时间"])
        self.file_tree.setColumnWidth(0, 200)
        self.file_tree.setColumnWidth(1, 80)
        self.file_tree.setColumnWidth(2, 120)
        self.file_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.file_tree.itemClicked.connect(self.on_file_clicked)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.on_file_context_menu)
        self.file_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #fafafa;
                border: none;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #e9ecef;
            }
            QTreeWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed {
                image: url(icons/plus.svg);
            }
            QTreeWidget::branch:open:has-children:!has-siblings {
                image: url(icons/minus.svg);
            }
        """)
        
        splitter.addWidget(self.file_tree)
        splitter.setStretchFactor(0, 40)
        
        # 文件预览
        preview_container = QFrame()
        preview_container.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-left: 1px solid #e0e0e0;
            }
        """)
        
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(8)
        
        # 预览标题
        self.preview_title = QLabel("文件预览")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.preview_title.setFont(title_font)
        preview_layout.addWidget(self.preview_title)
        
        # 预览内容
        self.preview_content = QTextEdit()
        self.preview_content.setReadOnly(True)
        self.preview_content.setPlaceholderText("选择左侧文件查看内容...")
        self.preview_content.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fff;
            }
        """)
        preview_layout.addWidget(self.preview_content)
        
        splitter.addWidget(preview_container)
        splitter.setStretchFactor(1, 60)
        
        main_layout.addWidget(splitter)
        
        # 设置样式
        self.setStyleSheet("""
            WorkspaceWidget {
                background-color: #fafafa;
                border-radius: 8px;
            }
        """)
    
    def set_workspace(self, path: str):
        """
        设置工作区路径
        
        Args:
            path: 工作区路径
        """
        if not os.path.exists(path):
            QMessageBox.warning(self, "错误", f"工作区路径不存在: {path}")
            return
        
        self.workspace_path = path
        self.path_display.setText(os.path.basename(path))
        
        # 保存设置
        settings = QSettings("AgentClient", "Workspace")
        settings.setValue("path", path)
        
        # 刷新文件树
        self.refresh_file_tree()
        
        logger.info(f"设置工作区: {path}")
    
    def get_workspace_path(self) -> Optional[str]:
        """获取工作区路径"""
        return self.workspace_path
    
    def refresh_file_tree(self):
        """刷新文件树"""
        if not self.workspace_path:
            self.file_tree.clear()
            return
        
        try:
            self.file_tree.clear()
            
            # 遍历目录
            self._populate_tree(self.workspace_path, None)
            
            logger.info(f"刷新文件树: {self.workspace_path}")
            
        except Exception as e:
            logger.error(f"刷新文件树失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"刷新文件树失败: {str(e)}")
    
    def _populate_tree(self, directory: str, parent_item: QTreeWidgetItem):
        """
        填充文件树
        
        Args:
            directory: 目录路径
            parent_item: 父节点
        """
        try:
            items = []
            
            # 获取目录内容
            for entry in os.listdir(directory):
                # 跳过隐藏文件和目录
                if entry.startswith('.'):
                    continue
                
                entry_path = os.path.join(directory, entry)
                
                # 创建树节点
                item = QTreeWidgetItem()
                
                # 获取文件信息
                if os.path.isdir(entry_path):
                    item.setText(0, f"📁 {entry}")
                    item.setText(1, "-")
                    
                    # 递归添加子目录
                    self._populate_tree(entry_path, item)
                    
                    # 如果子目录为空，不添加
                    if item.childCount() == 0:
                        continue
                    
                else:
                    file_size = os.path.getsize(entry_path)
                    file_size_str = self._format_file_size(file_size)
                    item.setText(0, f"📄 {entry}")
                    item.setText(1, file_size_str)
                    
                    # 获取修改时间
                    mtime = os.path.getmtime(entry_path)
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
                    item.setText(2, mtime_str)
                
                items.append((item, entry_path))
            
            # 排序：目录在前，然后按名称排序
            items.sort(key=lambda x: (not os.path.isdir(x[1]), x[0].text(0).lower()))
            
            # 添加到父节点
            for item, _ in items:
                if parent_item:
                    parent_item.addChild(item)
                else:
                    self.file_tree.addTopLevelItem(item)
            
        except PermissionError:
            logger.warning(f"权限不足，无法访问: {directory}")
        except Exception as e:
            logger.error(f"填充文件树失败: {str(e)}")
    
    def _format_file_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
    
    def on_file_clicked(self, item: QTreeWidgetItem, column: int):
        """文件点击事件"""
        file_path = self._get_item_path(item)
        
        if file_path and os.path.isfile(file_path):
            self.show_file_preview(file_path)
            self.file_selected.emit(file_path)
    
    def on_file_context_menu(self, position):
        """文件右键菜单"""
        item = self.file_tree.itemAt(position)
        if not item:
            return
        
        file_path = self._get_item_path(item)
        
        menu = QMenu(self)
        
        # 打开文件
        open_action = menu.addAction("在编辑器中打开")
        
        # 复制路径
        copy_action = menu.addAction("复制路径")
        
        # 分析文件
        if file_path and os.path.isfile(file_path):
            analyze_action = menu.addAction("分析此文件")
        else:
            analyze_action = None
        
        menu.addSeparator()
        
        # 打开所在目录
        explore_action = menu.addAction("在资源管理器中打开")
        
        action = menu.exec(self.file_tree.viewport().mapToGlobal(position))
        
        if action == open_action and file_path:
            self._open_file(file_path)
        elif action == copy_action and file_path:
            from PyQt6.QtGui import QClipboard
            clipboard = QClipboard()
            clipboard.setText(file_path)
        elif action == analyze_action and file_path:
            self.file_selected.emit(file_path)
        elif action == explore_action and file_path:
            self._open_explorer(os.path.dirname(file_path))
    
    def _get_item_path(self, item: QTreeWidgetItem) -> Optional[str]:
        """获取树节点对应的路径"""
        if not self.workspace_path:
            return None
        
        # 收集路径组件
        path_components = []
        
        while item:
            text = item.text(0)
            # 移除emoji前缀
            if text.startswith("📁"):
                name = text[2:].strip()
            elif text.startswith("📄"):
                name = text[2:].strip()
            else:
                name = text.strip()
            
            path_components.insert(0, name)
            item = item.parent()
        
        # 构建完整路径
        return os.path.join(self.workspace_path, *path_components[1:]) if len(path_components) > 1 else None
    
    def show_file_preview(self, file_path: str):
        """
        显示文件预览
        
        Args:
            file_path: 文件路径
        """
        try:
            # 更新标题
            self.preview_title.setText(os.path.basename(file_path))
            
            # 提取文件内容
            content = self.file_processor.extract_text(file_path)
            
            # 显示内容
            self.preview_content.setPlainText(content)
            
            logger.info(f"预览文件: {file_path}")
            
        except Exception as e:
            logger.error(f"预览文件失败: {str(e)}")
            self.preview_content.setPlainText(f"错误: {str(e)}")
    
    def on_select_workspace(self):
        """选择工作区按钮点击"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择工作区",
            self.workspace_path or os.path.expanduser("~")
        )
        
        if directory:
            self.set_workspace(directory)
    
    def _open_file(self, file_path: str):
        """在系统编辑器中打开文件"""
        try:
            import subprocess
            import sys
            
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(['open', file_path])
            else:
                subprocess.Popen(['xdg-open', file_path])
                
        except Exception as e:
            logger.error(f"打开文件失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"无法打开文件: {str(e)}")
    
    def _open_explorer(self, path: str):
        """在资源管理器中打开路径"""
        try:
            import subprocess
            import sys
            
            if sys.platform == "win32":
                subprocess.Popen(['explorer', path])
            elif sys.platform == "darwin":
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
                
        except Exception as e:
            logger.error(f"打开资源管理器失败: {str(e)}")
    
    def _load_settings(self):
        """加载设置"""
        settings = QSettings("AgentClient", "Workspace")
        path = settings.value("path")
        
        if path and os.path.exists(path):
            self.set_workspace(path)
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
    
    def dropEvent(self, event):
        """拖拽释放事件"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path:
                    self.file_selected.emit(file_path)
                    break


# 便捷函数
def create_workspace_widget(parent: QWidget = None) -> WorkspaceWidget:
    """创建工作区组件"""
    return WorkspaceWidget(parent)
