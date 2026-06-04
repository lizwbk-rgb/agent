"""
主窗口组件

PyQt应用主窗口，支持Ask和Craft两种模式
Ask模式: 对话85% + 记忆15%
Craft模式: 工作区15% + 对话70% + 记忆15%
"""

import os
import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QMenuBar,
    QMenu,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QLabel
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QActionGroup

from agent import Agent, ChatMode
from config import get_config
from ui.chat_widget import ChatWidget
from ui.memory_widget import MemoryWidget

# 配置日志
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    主窗口
    
    AI对话客户端的主界面，支持Ask和Craft两种模式
    """
    
    def __init__(self, agent: Agent = None, parent=None):
        """
        初始化主窗口
        
        Args:
            agent: Agent实例
            parent: 父组件
        """
        super().__init__(parent)
        
        self.agent = agent or Agent()
        self.current_mode = ChatMode.ASK
        self.settings = QSettings("AgentClient", "MainWindow")
        
        self._init_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._setup_connections()
        self._load_settings()
        
        logger.info("主窗口初始化完成")
    
    def _init_ui(self):
        """初始化UI"""
        # 窗口设置
        self.setWindowTitle("AI对话客户端")
        self.setMinimumSize(1024, 700)
        
        # 中央容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 根据模式设置布局
        self.set_mode(ChatMode.ASK)
        
        main_layout.addWidget(self.main_splitter)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 2px;
            }
            QSplitter::handle:hover {
                background-color: #ccc;
            }
        """)
    
    def _setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        # 打开工作区
        open_workspace_action = QAction("打开工作区...", self)
        open_workspace_action.triggered.connect(self.open_workspace)
        file_menu.addAction(open_workspace_action)
        
        # 刷新工作区
        refresh_workspace_action = QAction("刷新工作区", self)
        refresh_workspace_action.triggered.connect(self.refresh_workspace)
        refresh_workspace_action.setEnabled(False)  # Ask模式下禁用
        self.refresh_workspace_action = refresh_workspace_action
        file_menu.addAction(refresh_workspace_action)
        
        # 清除工作区
        clear_workspace_action = QAction("清除工作区", self)
        clear_workspace_action.triggered.connect(self.clear_workspace)
        clear_workspace_action.setEnabled(False)  # Ask模式下禁用
        self.clear_workspace_action = clear_workspace_action
        file_menu.addAction(clear_workspace_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 模式菜单
        mode_menu = menubar.addMenu("模式")
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        
        # Ask模式
        ask_action = QAction("Ask模式", self)
        ask_action.setCheckable(True)
        ask_action.setChecked(True)
        ask_action.triggered.connect(lambda: self.set_mode(ChatMode.ASK))
        mode_group.addAction(ask_action)
        mode_menu.addAction(ask_action)
        
        # Craft模式
        craft_action = QAction("Craft模式", self)
        craft_action.setCheckable(True)
        craft_action.triggered.connect(lambda: self.set_mode(ChatMode.CRAFT))
        mode_group.addAction(craft_action)
        mode_menu.addAction(craft_action)
        
        # 记忆菜单
        memory_menu = menubar.addMenu("记忆")
        
        # 刷新记忆
        refresh_memory_action = QAction("刷新记忆", self)
        refresh_memory_action.triggered.connect(self.refresh_memories)
        memory_menu.addAction(refresh_memory_action)
        
        memory_menu.addSeparator()
        
        # 清空记忆
        clear_memory_action = QAction("清空所有记忆", self)
        clear_memory_action.triggered.connect(self.clear_all_memories)
        memory_menu.addAction(clear_memory_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _setup_statusbar(self):
        """设置状态栏"""
        statusbar = self.statusBar()
        
        # 模式标签
        self.mode_label = QLabel("模式: Ask")
        statusbar.addWidget(self.mode_label)
        
        # 记忆数量标签
        self.memory_count_label = QLabel("记忆: 0")
        statusbar.addWidget(self.memory_count_label)
        
        # 工作区标签
        self.workspace_label = QLabel("工作区: 未设置")
        statusbar.addWidget(self.workspace_label)
        
        statusbar.showMessage("就绪")
    
    def _setup_connections(self):
        """设置信号连接"""
        # ChatWidget信号
        self.chat_widget.message_sent.connect(self.on_message_sent)
        self.chat_widget.file_uploaded.connect(self.on_file_uploaded)
        self.chat_widget.mode_changed.connect(self.on_mode_changed)
        
        # MemoryWidget信号
        self.memory_widget.memory_deleted.connect(self.on_memory_deleted)
        self.memory_widget.memories_cleared.connect(self.on_memories_cleared)
        
        # Craft模式下连接工作区信号
        if self.current_mode == ChatMode.CRAFT:
            self._connect_workspace_signals()
    
    def _connect_workspace_signals(self):
        """连接工作区组件信号"""
        if hasattr(self, 'workspace_widget') and self.workspace_widget:
            self.workspace_widget.file_selected.connect(self.on_file_selected_from_workspace)
            logger.info("工作区信号已连接")
    
    def set_mode(self, mode: ChatMode):
        """
        设置对话模式
        
        Args:
            mode: 对话模式
        """
        if self.current_mode == mode:
            logger.debug(f"已在 {mode.value} 模式，无需切换")
            return
        
        # 保存当前工作区路径（切换模式时保留）
        old_workspace_path = None
        if hasattr(self, 'workspace_widget') and self.workspace_widget:
            old_workspace_path = self.workspace_widget.workspace_path
        
        self.current_mode = mode
        self.agent.set_mode(mode)
        
        # 清除现有组件
        while self.main_splitter.count():
            widget = self.main_splitter.widget(0)
            self.main_splitter.removeWidget(widget)
            widget.deleteLater()
        
        if mode == ChatMode.ASK:
            self._setup_ask_mode()
        else:
            self._setup_craft_mode()
            # 恢复工作区路径
            if old_workspace_path and hasattr(self, 'workspace_widget'):
                self.workspace_widget.set_workspace(old_workspace_path)
        
        # 更新菜单项状态
        self._update_menu_state()
        
        # 更新状态栏
        self.mode_label.setText(f"模式: {mode.value}")
        self.statusBar().showMessage(f"已切换到 {mode.value} 模式")
        
        logger.info(f"切换到 {mode.value} 模式")
    
    def _update_menu_state(self):
        """更新菜单项状态"""
        # 更新模式菜单选中状态
        # 这里需要根据实际的QAction引用更新
        
        # 更新工作区相关菜单项的启用状态
        if hasattr(self, 'refresh_workspace_action'):
            self.refresh_workspace_action.setEnabled(self.current_mode == ChatMode.CRAFT)
        
        if hasattr(self, 'clear_workspace_action'):
            self.clear_workspace_action.setEnabled(self.current_mode == ChatMode.CRAFT)
    
    def _setup_ask_mode(self):
        """设置Ask模式布局（对话85%+记忆15%）"""
        # 对话组件
        self.chat_widget = ChatWidget(self.agent)
        self.chat_widget.setup_file_drop()
        
        # 记忆组件
        self.memory_widget = MemoryWidget(self.agent.memory_manager)
        
        # 添加到分割器
        self.main_splitter.addWidget(self.chat_widget)
        self.main_splitter.addWidget(self.memory_widget)
        
        # 设置比例
        self.main_splitter.setStretchFactor(0, 85)
        self.main_splitter.setStretchFactor(1, 15)
        
        # 连接信号
        self._setup_connections()
        
        # 保存当前模式
        self.settings.setValue("mode", "ask")
    
    def _setup_craft_mode(self):
        """设置Craft模式布局（工作区15%+对话70%+记忆15%）"""
        # 工作区组件
        from .workspace_widget import WorkspaceWidget
        self.workspace_widget = WorkspaceWidget()
        
        # 对话组件
        self.chat_widget = ChatWidget(self.agent)
        self.chat_widget.setup_file_drop()
        
        # 记忆组件
        self.memory_widget = MemoryWidget(self.agent.memory_manager)
        
        # 添加到分割器
        self.main_splitter.addWidget(self.workspace_widget)
        self.main_splitter.addWidget(self.chat_widget)
        self.main_splitter.addWidget(self.memory_widget)
        
        # 设置比例
        self.main_splitter.setStretchFactor(0, 15)
        self.main_splitter.setStretchFactor(1, 70)
        self.main_splitter.setStretchFactor(2, 15)
        
        # 连接信号（包含工作区信号）
        self._setup_connections()
        
        # 保存当前模式
        self.settings.setValue("mode", "craft")
        
        # 更新工作区标签
        if self.workspace_widget.workspace_path:
            self.workspace_label.setText(f"工作区: {self.workspace_widget.workspace_path}")
    
    # ==================== 事件处理 ====================
    
    def on_message_sent(self, message: str, file_path: str):
        """消息发送事件"""
        logger.info(f"发送消息: {message[:50]}...")
        self.statusBar().showMessage("正在处理...")
        
        # 更新记忆计数
        self._update_memory_count()
        
        self.statusBar().showMessage("处理完成")
    
    def on_file_uploaded(self, file_path: str):
        """文件上传事件"""
        file_name = os.path.basename(file_path)
        logger.info(f"上传文件: {file_name}")
        self.statusBar().showMessage(f"已上传: {file_name}")
    
    def on_mode_changed(self, mode: str):
        """模式切换事件"""
        # 这个信号由ChatWidget发出，但模式切换由MainWindow控制
        # 所以这里不需要做额外处理
        # 可以在这里添加日志记录
        logger.debug(f"ChatWidget请求切换模式: {mode}")
    
    def on_file_selected_from_workspace(self, file_path: str):
        """从工作区选择文件事件"""
        file_name = os.path.basename(file_path)
        logger.info(f"从工作区选择文件: {file_name}")
        
        # 更新状态栏
        self.statusBar().showMessage(f"已选择文件: {file_name}")
        
        # 在对话中显示文件信息
        self.chat_widget.add_system_message(f"已从工作区选择文件: {file_name}")
    
    def on_memory_deleted(self, memory_id: str):
        """记忆删除事件"""
        self._update_memory_count()
        self.statusBar().showMessage(f"已删除记忆: {memory_id}")
    
    def on_memories_cleared(self):
        """记忆清空事件"""
        self._update_memory_count()
        self.statusBar().showMessage("所有记忆已清空")
    
    # ==================== 菜单操作 ====================
    
    def open_workspace(self):
        """打开工作区"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择工作区",
            os.path.expanduser("~")
        )
        
        if directory:
            self.agent.set_workspace(directory)
            self.workspace_label.setText(f"工作区: {directory}")
            
            if hasattr(self, 'workspace_widget'):
                self.workspace_widget.set_workspace(directory)
            
            self.statusBar().showMessage(f"工作区已设置: {directory}")
            logger.info(f"设置工作区: {directory}")
    
    def refresh_workspace(self):
        """刷新工作区文件树"""
        if hasattr(self, 'workspace_widget') and self.workspace_widget:
            self.workspace_widget.refresh_file_tree()
            self.statusBar().showMessage("工作区已刷新")
            logger.info("刷新工作区文件树")
    
    def clear_workspace(self):
        """清除工作区"""
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除工作区设置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.agent.set_workspace(None)
            self.workspace_label.setText("工作区: 未设置")
            
            if hasattr(self, 'workspace_widget'):
                self.workspace_widget.set_workspace(None)
            
            self.statusBar().showMessage("工作区已清除")
            logger.info("清除工作区")
    
    def refresh_memories(self):
        """刷新记忆"""
        if hasattr(self, 'memory_widget'):
            self.memory_widget.refresh_memories()
            self._update_memory_count()
    
    def clear_all_memories(self):
        """清空所有记忆"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有记忆吗？此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.agent.clear_memories()
            self.refresh_memories()
            self.statusBar().showMessage("所有记忆已清空")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 AI对话客户端",
            """<h3>AI对话客户端</h3>
            <p>基于DeepSeek API和mem0记忆系统的智能对话客户端</p>
            <p>版本: 1.0.0</p>
            <p>功能:</p>
            <ul>
                <li>智能多轮对话</li>
                <li>自动记忆提取和管理</li>
                <li>文件分析（PDF、Word、Excel、代码等）</li>
                <li>Markdown消息渲染</li>
                <li>Ask/Craft双模式</li>
            </ul>"""
        )
    
    # ==================== 辅助方法 ====================
    
    def _update_memory_count(self):
        """更新记忆数量"""
        count = self.agent.get_memories().__len__()
        self.memory_count_label.setText(f"记忆: {count}")
    
    def _load_settings(self):
        """加载设置"""
        mode = self.settings.value("mode", "ask")
        if mode == "craft":
            self.set_mode(ChatMode.CRAFT)
        else:
            self.set_mode(ChatMode.ASK)
    
    def get_current_workspace(self) -> str:
        """获取当前工作区路径"""
        if hasattr(self, 'workspace_widget') and self.workspace_widget:
            return self.workspace_widget.get_workspace_path()
        return None
    
    def is_in_craft_mode(self) -> bool:
        """是否处于Craft模式"""
        return self.current_mode == ChatMode.CRAFT
    
    def _save_settings(self):
        """保存设置"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
    
    def closeEvent(self, event):
        """关闭事件"""
        self._save_settings()
        event.accept()


# 便捷函数
def create_main_window(agent: Agent = None) -> MainWindow:
    """创建主窗口"""
    return MainWindow(agent)


def run_application(agent: Agent = None):
    """运行应用"""
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyleSheet("""
        QApplication {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        QMainWindow {
            background-color: #f5f5f5;
        }
    """)
    
    # 创建主窗口
    window = MainWindow(agent)
    window.show()
    
    # 运行应用
    sys.exit(app.exec())
