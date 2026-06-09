"""
代码编辑器组件

提供代码编辑、语法高亮、文件保存等功能
"""

import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QSyntaxHighlighter, QTextCharFormat, QColor


# 配置日志
logger = logging.getLogger(__name__)


class CodeHighlighter(QSyntaxHighlighter):
    """代码语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # 关键字格式
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(700)  # Bold
        
        keywords = [
            "if", "else", "elif", "for", "while", "do", "switch", "case",
            "break", "continue", "return", "goto", "try", "catch", "finally",
            "throw", "new", "delete", "this", "super", "class", "def", "function",
            "var", "let", "const", "int", "float", "double", "char", "void",
            "public", "private", "protected", "static", "final", "abstract",
            "import", "from", "as", "in", "of", "is", "null", "undefined",
            "true", "false", "and", "or", "not", "with", "yield", "async", "await"
        ]
        
        for keyword in keywords:
            pattern = f"\\b{keyword}\\b"
            self.highlighting_rules.append((pattern, keyword_format))
        
        # 字符串格式
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append(('"[^"]*"', string_format))
        self.highlighting_rules.append(("'[^']*'", string_format))
        
        # 注释格式
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append(("//[^\n]*", comment_format))
        
        # 数字格式
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append(("\\b\\d+\\b", number_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        import re
        
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class CodeEditorWidget(QWidget):
    """
    代码编辑器组件
    
    提供代码编辑、语法高亮、文件保存等功能
    """
    
    # 信号
    file_changed = pyqtSignal(str)  # 文件路径变化信号
    content_changed = pyqtSignal()  # 内容变化信号
    close_requested = pyqtSignal()  # 关闭请求信号
    
    def __init__(self, parent: QWidget = None):
        """
        初始化代码编辑器组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        
        self.current_file = None
        self.is_modified = False
        
        self.setup_ui()
        
        logger.info("代码编辑器组件初始化完成")
    
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
        
        # 文件名标签
        self.file_name_label = QLabel("未打开文件")
        file_name_font = QFont()
        file_name_font.setPointSize(10)
        file_name_font.setBold(True)
        self.file_name_label.setFont(file_name_font)
        toolbar_layout.addWidget(self.file_name_label)
        
        toolbar_layout.addStretch()
        
        # 保存按钮
        self.save_btn = QPushButton("保存")
        self.save_btn.setMinimumWidth(60)
        self.save_btn.setMaximumWidth(60)
        self.save_btn.clicked.connect(self.save_file)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        toolbar_layout.addWidget(self.save_btn)
        
        # 另存为按钮
        self.save_as_btn = QPushButton("另存为")
        self.save_as_btn.setMinimumWidth(70)
        self.save_as_btn.setMaximumWidth(70)
        self.save_as_btn.clicked.connect(self.save_file_as)
        self.save_as_btn.setStyleSheet("""
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
        toolbar_layout.addWidget(self.save_as_btn)
        
        # 关闭按钮
        self.close_btn = QPushButton("✕")
        self.close_btn.setMinimumWidth(30)
        self.close_btn.setMaximumWidth(30)
        self.close_btn.clicked.connect(self.on_close_clicked)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 14px;
                color: #666;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-radius: 4px;
            }
        """)
        toolbar_layout.addWidget(self.close_btn)
        
        main_layout.addWidget(toolbar)
        
        # 代码编辑器
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("打开文件开始编辑...")
        
        # 设置字体
        editor_font = QFont("Consolas", 11)
        self.editor.setFont(editor_font)
        
        # 设置样式
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 8px;
                line-height: 1.5;
            }
        """)
        
        # 连接文本变化信号
        self.editor.textChanged.connect(self.on_text_changed)
        
        # 设置语法高亮
        self.highlighter = CodeHighlighter(self.editor.document())
        
        main_layout.addWidget(self.editor)
        
        # 底部状态栏
        status_bar = QFrame()
        status_bar.setMaximumHeight(25)
        status_bar.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-top: 1px solid #e0e0e0;
            }
        """)
        
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(8, 2, 8, 2)
        
        # 光标位置标签
        self.cursor_label = QLabel("行 1, 列 1")
        self.cursor_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(self.cursor_label)
        
        status_layout.addStretch()
        
        # 修改状态标签
        self.modified_label = QLabel("")
        self.modified_label.setStyleSheet("color: #f44336; font-size: 11px;")
        status_layout.addWidget(self.modified_label)
        
        main_layout.addWidget(status_bar)
        
        # 连接光标位置变化信号
        self.editor.cursorPositionChanged.connect(self.update_cursor_position)
    
    def open_file(self, file_path: str):
        """
        打开文件
        
        Args:
            file_path: 文件路径
        """
        try:
            # 如果当前文件已修改，询问是否保存
            if self.is_modified:
                reply = QMessageBox.question(
                    self,
                    "保存文件",
                    "当前文件已修改，是否保存？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.save_file()
                elif reply == QMessageBox.StandardButton.Cancel:
                    return
            
            # 尝试多种编码打开文件
            content = None
            encoding_used = None
            
            # 编码尝试顺序：utf-8, utf-16, gbk, latin-1
            for encoding in ['utf-8', 'utf-16', 'gbk', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    encoding_used = encoding
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                # 所有编码都失败（理论上 latin-1 不会失败）
                raise Exception("无法识别文件编码")
            
            # 设置编辑器内容
            self.editor.setPlainText(content)
            
            # 更新状态
            self.current_file = file_path
            self.is_modified = False
            self.file_name_label.setText(os.path.basename(file_path))
            self.save_btn.setEnabled(False)
            self.modified_label.setText("")
            
            # 发出信号
            self.file_changed.emit(file_path)
            
            logger.info(f"打开文件: {file_path} (编码: {encoding_used})")
            
        except Exception as e:
            logger.error(f"打开文件失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"无法打开文件: {str(e)}")
    
    def save_file(self):
        """保存文件"""
        if not self.current_file:
            self.save_file_as()
            return
        
        try:
            content = self.editor.toPlainText()
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.is_modified = False
            self.save_btn.setEnabled(False)
            self.modified_label.setText("")
            
            logger.info(f"保存文件: {self.current_file}")
            
        except Exception as e:
            logger.error(f"保存文件失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"保存文件失败: {str(e)}")
    
    def save_file_as(self):
        """另存为"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "另存为",
            self.current_file or os.path.expanduser("~"),
            "所有文件 (*)"
        )
        
        if file_path:
            self.current_file = file_path
            self.save_file()
    
    def on_close_clicked(self):
        """关闭按钮点击事件"""
        self.close_requested.emit()
    
    def on_text_changed(self):
        """文本变化事件"""
        if not self.is_modified:
            self.is_modified = True
            self.save_btn.setEnabled(True)
            self.modified_label.setText("已修改")
        
        self.content_changed.emit()
    
    def update_cursor_position(self):
        """更新光标位置显示"""
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.cursor_label.setText(f"行 {line}, 列 {column}")
    
    def get_content(self) -> str:
        """获取编辑器内容"""
        return self.editor.toPlainText()
    
    def set_content(self, content: str):
        """设置编辑器内容"""
        self.editor.setPlainText(content)
        self.is_modified = False
        self.save_btn.setEnabled(False)
        self.modified_label.setText("")
    
    def is_file_modified(self) -> bool:
        """检查文件是否已修改"""
        return self.is_modified


# 便捷函数
def create_code_editor_widget(parent: QWidget = None) -> CodeEditorWidget:
    """创建代码编辑器组件"""
    return CodeEditorWidget(parent)
