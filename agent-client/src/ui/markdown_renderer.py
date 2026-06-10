"""
Markdown渲染器模块

支持Markdown解析、代码语法高亮、表格渲染、URL图片渲染
"""

import re
import html
import logging
import os
import hashlib
import base64
import subprocess
import sys
from typing import Optional
from dataclasses import dataclass

# 配置日志
logger = logging.getLogger(__name__)

# 用于存储LaTeX渲染缓存
_latex_cache = {}

# matplotlib 是否可用的标志
_matplotlib_available = None

def _ensure_matplotlib():
    """确保 matplotlib 已安装，如果未安装则尝试自动安装"""
    global _matplotlib_available
    
    if _matplotlib_available is not None:
        return _matplotlib_available
    
    try:
        import matplotlib
        _matplotlib_available = True
        logger.info("[matplotlib] 已检测到 matplotlib: %s", matplotlib.__version__)
        return True
    except ImportError:
        _matplotlib_available = False
        logger.warning("[matplotlib] 未检测到 matplotlib，尝试自动安装...")
        
        try:
            # 尝试自动安装 matplotlib
            logger.info("[matplotlib] 正在安装 matplotlib...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib>=3.7.0"])
            
            # 重新导入
            import importlib
            importlib.invalidate_caches()
            import matplotlib
            _matplotlib_available = True
            logger.info("[matplotlib] matplotlib 自动安装成功: %s", matplotlib.__version__)
            return True
            
        except Exception as e:
            logger.error("[matplotlib] 自动安装 matplotlib 失败: %s", e)
            logger.warning("[matplotlib] LaTeX渲染功能将不可用，请手动执行: pip install matplotlib>=3.7.0")
            return False


@dataclass
class RenderOptions:
    """渲染选项"""
    code_highlight: bool = True  # 代码语法高亮
    render_tables: bool = True   # 渲染表格
    render_images: bool = True   # 渲染图片
    allow_external_images: bool = False  # 允许外部图片
    max_image_width: int = 400   # 最大图片宽度
    line_numbers: bool = False   # 代码行号


class MarkdownRenderer:
    """
    Markdown渲染器
    
    将Markdown文本转换为HTML，支持代码高亮、表格、图片等
    """
    
    # 单例实例
    _instance = None
    
    def __init__(self, options: RenderOptions = None):
        """
        初始化渲染器
        
        Args:
            options: 渲染选项
        """
        self.options = options or RenderOptions()
        self._lexer = None
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def render(self, markdown_text: str) -> str:
        """
        渲染Markdown文本
        
        Args:
            markdown_text: Markdown文本
            
        Returns:
            str: HTML文本
        """
        if not markdown_text:
            return ""
        
        # 预处理
        text = self._preprocess(markdown_text)
        
        # 解析并渲染 - 使用更简单的方法：按行处理
        lines = text.split('\n')
        
        html_parts = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 检测代码块开始
            if line.strip().startswith('```'):
                # 提取代码块
                code_lines = []
                lang = line.strip()[3:].strip()
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # 跳过结束的 ```
                
                # 渲染代码块
                code_html = self._render_code('\n'.join(code_lines), lang)
                html_parts.append(code_html)
                continue
            
            # 检测块级LaTeX公式开始（$$）
            if line.strip().startswith('$$'):
                # 提取LaTeX公式
                latex_lines = []
                # 移除开头的 $$
                first_line = line.strip()[2:]
                if first_line.endswith('$$'):
                    # 单行公式：$$formula$$
                    latex_lines.append(first_line[:-2])
                    i += 1
                else:
                    # 多行公式：$$formula 或 $$formula\n...$$\n
                    latex_lines.append(first_line)
                    i += 1  # 跳过开头的 $$，指向公式第一行
                    # 继续收集，直到遇到 $$
                    while i < len(lines) and not lines[i].strip().startswith('$$'):
                        latex_lines.append(lines[i])
                        i += 1
                    # 此时 i 指向 $$ 开头的行，需要跳过它
                    i += 1  # 跳过结束的 $$
                
                # 渲染LaTeX公式（块级公式，display_mode=True）
                latex_html = self._render_latex('\n'.join(latex_lines), display_mode=True)
                # 块级LaTeX公式用段落包裹
                latex_html = f'<p style="text-align: center; margin: 1em 0;">{latex_html}</p>'
                html_parts.append(latex_html)
                continue
            
            # 检测表格（包含 | 的行）
            if '|' in line and i + 1 < len(lines) and '|' in lines[i+1]:
                # 提取表格行
                table_lines = []
                while i < len(lines) and lines[i].strip() and '|' in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                
                # 渲染表格
                table_html = self._render_table('\n'.join(table_lines))
                if table_html:
                    html_parts.append(table_html)
                continue
            
            # 普通行 - 收集段落或列表
            para_lines = []
            while i < len(lines) and lines[i].strip():
                # 检查当前行是否是表格的开始
                if '|' in lines[i]:
                    # 可能是表格，检查下一行是否也是表格
                    if i + 1 < len(lines) and '|' in lines[i+1]:
                        # 是表格开始，停止收集段落
                        break
                # 检查当前行是否是块级LaTeX公式的开始（$$）
                if lines[i].strip().startswith('$$'):
                    break
                para_lines.append(lines[i])
                i += 1
            
            if para_lines:
                paragraph = '\n'.join(para_lines)
                
                # 检查是否包含列表项
                lines_in_para = paragraph.split('\n')
                is_list = all(re.match(r'^[-*+]\s+', line.strip()) or re.match(r'^\d+\.\s+', line.strip()) for line in lines_in_para if line.strip())
                
                if is_list:
                    # 处理列表
                    list_html = self._process_list(lines_in_para)
                    if list_html:
                        html_parts.append(list_html)
                else:
                    # 处理普通段落
                    html_content = self._process_paragraph(paragraph)
                    if html_content:
                        html_parts.append(html_content)
            
            # 跳过空行
            while i < len(lines) and not lines[i].strip():
                i += 1
        
        # 组装HTML
        result = self._postprocess(html_parts)
        return result
    
    def _preprocess(self, text: str) -> str:
        """预处理文本"""
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 过滤ASCII控制字符（保留\n、\r、\t，过滤其他控制字符如\x01等）
        text = ''.join(ch for ch in text if ord(ch) >= 32 or ch in '\n\r\t')
        
        # 转义 & 符号（必须先处理）
        text = text.replace('&', '&amp;')
        
        return text
    
    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符（< > " '）"""
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text
    
    def _postprocess(self, html_parts: list) -> str:
        """后处理HTML"""
        # 组装
        html_content = '\n'.join(html_parts)
        
        # 对非HTML标签的文本进行HTML转义
        html_content = self._escape_text_outside_tags(html_content)
        
        # 添加样式
        styled_html = self._wrap_with_styles(html_content)
        
        return styled_html
    
    def _escape_text_outside_tags(self, html_text: str) -> str:
        """转义HTML标签外的文本"""
        # 匹配HTML标签和非标签文本
        pattern = r'(<[^>]+>)|([^<]+)'
        result = []
        for match in re.finditer(pattern, html_text, re.DOTALL):
            if match.group(1):  # HTML标签，保留原样
                result.append(match.group(1))
            else:  # 普通文本，转义HTML特殊字符
                text = match.group(2)
                # 只转义 < 和 >（& 已在预处理中转义）
                text = text.replace('<', '&lt;')
                text = text.replace('>', '&gt;')
                result.append(text)
        return ''.join(result)
    
    def _process_list(self, lines: list) -> str:
        """处理列表"""
        # 判断是有序列表还是无序列表
        is_ordered = re.match(r'^\d+\.\s+', lines[0].strip())
        tag = 'ol' if is_ordered else 'ul'
        
        # 收集列表项并生成HTML
        html_parts = [f'<{tag} style="margin: 0.5em 0; padding-left: 2em;">']
        for line in lines:
            line_stripped = line.strip()
            
            # 检查是否是任务列表
            task_match = re.match(r'^[-*+]\s+\[([ x])\]\s+(.+)$', line_stripped, re.IGNORECASE)
            if task_match:
                # 任务列表
                checked = 'checked' if task_match.group(1).lower() == 'x' else ''
                content = task_match.group(2)
                html_parts.append(f'<li style="margin: 0.2em 0;"><input type="checkbox" {checked} disabled style="margin-right: 4px;">{self._inline_format(content)}</li>')
            else:
                # 普通列表项 - 移除列表标记
                if is_ordered:
                    match = re.match(r'^\d+\.\s+(.+)$', line_stripped)
                    if match:
                        content = match.group(1)
                        html_parts.append(f'<li style="margin: 0.2em 0;">{self._inline_format(content)}</li>')
                else:
                    match = re.match(r'^[-*+]\s+(.+)$', line_stripped)
                    if match:
                        content = match.group(1)
                        html_parts.append(f'<li style="margin: 0.2em 0;">{self._inline_format(content)}</li>')
        
        html_parts.append(f'</{tag}>')
        return '\n'.join(html_parts)
    
    def _process_paragraph(self, paragraph: str) -> str:
        """处理单个段落"""
        # 检测标题
        if paragraph.startswith('# '):
            return f'<h1 style="font-size: 1.5em; margin: 0.5em 0; font-weight: bold; color: #333;">{self._inline_format(paragraph[2:])}</h1>'
        elif paragraph.startswith('## '):
            return f'<h2 style="font-size: 1.3em; margin: 0.5em 0; font-weight: bold; color: #333;">{self._inline_format(paragraph[3:])}</h2>'
        elif paragraph.startswith('### '):
            return f'<h3 style="font-size: 1.1em; margin: 0.5em 0; font-weight: bold; color: #333;">{self._inline_format(paragraph[4:])}</h3>'
        elif paragraph.startswith('#### '):
            return f'<h4 style="font-size: 1em; margin: 0.5em 0; font-weight: bold; color: #333;">{self._inline_format(paragraph[5:])}</h4>'
        
        # 检测引用
        if paragraph.startswith('> '):
            content = self._inline_format(paragraph[2:])
            return f'<blockquote style="border-left: 3px solid #ddd; margin: 0.5em 0; padding: 0.5em 1em; color: #666; background-color: #f9f9f9;">{content}</blockquote>'
        
        # 检测有序列表
        list_match = re.match(r'^(\d+)\.\s+(.+)$', paragraph)
        if list_match:
            return f'<ol style="margin: 0.5em 0; padding-left: 2em;"><li style="margin: 0.2em 0;">{self._inline_format(list_match.group(2))}</li></ol>'
        
        # 检测无序列表
        ul_match = re.match(r'^[-*+]\s+(.+)$', paragraph)
        if ul_match:
            return f'<ul style="margin: 0.5em 0; padding-left: 2em;"><li style="margin: 0.2em 0;">{self._inline_format(ul_match.group(1))}</li></ul>'
        
        # 检测表格
        if self.options.render_tables and '|' in paragraph:
            table_html = self._render_table(paragraph)
            if table_html:
                return table_html
        
        # 检测水平线
        if re.match(r'^[-=*_]{3,}$', paragraph):
            return '<hr style="border: none; border-top: 1px solid #ddd; margin: 1em 0;">'
        
        # 检测任务列表
        task_match = re.match(r'^[-*+]\s+\[[ x]\]\s+(.+)$', paragraph, re.IGNORECASE)
        if task_match:
            checked = 'checked' if '[x]' in paragraph.lower() else ''
            return f'<ul style="margin: 0.5em 0; padding-left: 2em;"><li style="margin: 0.2em 0;"><input type="checkbox" {checked} disabled style="margin-right: 4px;">{task_match.group(1)}</li></ul>'
        
        # 普通段落
        return f'<p style="margin: 0.5em 0; line-height: 1.6; color: #333;">{self._inline_format(paragraph)}</p>'
    
    def _inline_format(self, text: str) -> str:
        """处理行内格式"""
        # 简化策略：只支持 *text* 斜体，不支持 _text_ 斜体（避免与LaTeX公式冲突）
        
        # 首先处理行内LaTeX公式 $...$ 和 \(...\)（必须在其他处理之前）
        def process_inline_latex(text):
            result = []
            last_end = 0
            i = 0
            
            while i < len(text):
                # 找到第一个 $ 或 \
                dollar_pos = text.find('$', i)
                backslash_pos = text.find('\\(', i)
                backslash_end_pos = text.find('\\)', i)
                
                # 优先找最近的起始位置
                if dollar_pos == -1 and backslash_pos == -1:
                    # 没找到任何LaTeX起始符，添加剩余文本并结束
                    if last_end < len(text):
                        result.append(text[last_end:])
                    break
                
                # 选择最近的起始位置
                if dollar_pos != -1 and (backslash_pos == -1 or dollar_pos < backslash_pos):
                    # 处理 $...$ 格式
                    start = dollar_pos
                    
                    # 检查是否是 $$（块级LaTeX）
                    if start + 1 < len(text) and text[start + 1] == '$':
                        # 这是块级LaTeX，跳过 $$
                        i = start + 2
                        continue
                    
                    # 这是行内LaTeX $...$
                    end = start + 1
                    while end < len(text):
                        if text[end] == '$':
                            if end + 1 < len(text) and text[end + 1] == '$':
                                end += 2
                                continue
                            break
                        end += 1
                    
                    if end >= len(text):
                        if last_end < len(text):
                            result.append(text[last_end:])
                        break
                    
                    latex_content = text[start + 1:end]
                    latex_html = self._render_latex(latex_content, display_mode=False)
                    
                    if last_end < start:
                        result.append(text[last_end:start])
                    result.append(latex_html)
                    i = end + 1
                    
                else:
                    # 处理 \(...\) 格式
                    start = backslash_pos
                    
                    # 找到对应的 \)
                    if backslash_end_pos == -1 or backslash_end_pos < start:
                        # 没找到结束符，添加剩余文本并结束
                        if last_end < len(text):
                            result.append(text[last_end:])
                        break
                    
                    end = backslash_end_pos
                    
                    # 提取LaTeX内容（去掉 \( 和 \)）
                    latex_content = text[start + 2:end]
                    latex_html = self._render_latex(latex_content, display_mode=False)
                    
                    if last_end < start:
                        result.append(text[last_end:start])
                    result.append(latex_html)
                    i = end + 2
                
                last_end = i
            
            return ''.join(result)
        
        text = process_inline_latex(text)
        
        # 粗体和斜体
        # ***text*** 或 ___text___
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'___(.+?)___', r'<strong><em>\1</em></strong>', text)
        
        # 粗体 **text** 或 __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        
        # 斜体 *text* （不支持 _text_，避免与LaTeX公式冲突）
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # 注意：故意不处理 _text_ 格式，因为LaTeX公式中的下划线会被误处理
        
        # 删除线 ~~text~~
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
        
        # 行内代码 `code` - 添加内联样式
        # 使用非贪婪匹配，但排除已经是代码块的情况
        def replace_inline_code(match):
            code_content = match.group(1)
            # 转义HTML
            escaped = html.escape(code_content)
            return f'<code style="background-color: #f5f5f5; padding: 2px 4px; font-family: monospace; font-size: 0.9em; border-radius: 3px;">{escaped}</code>'
        
        # 匹配行内代码：`...`，但排除 ``` 代码块标记
        text = re.sub(r'`([^`\n]+?)`', replace_inline_code, text)
        
        # 图片 ![alt](url) - 必须在链接之前处理，否则链接正则会匹配 [alt](url)
        if self.options.render_images:
            text = re.sub(
                r'!\[(.+?)\]\((.+?)\)',
                lambda m: self._render_image(m.group(1), m.group(2)),
                text
            )
        
        # 链接 [text](url)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\\2" style="color: #0066cc; text-decoration: underline;">\\1</a>', text)
        
        return text
    
    def _render_code(self, code: str, language: str = '') -> str:
        """
        渲染代码块
        
        Args:
            code: 代码内容
            language: 编程语言
            
        Returns:
            str: HTML代码块
        """
        # 简单转义HTML（禁用Pygments高亮，避免CSS问题）
        highlighted_code = html.escape(code)
        
        # 构建HTML - 使用简单结构，兼容QTextBrowser
        html_content = f'<pre style="background-color: #f8f8f8; padding: 8px; border: 1px solid #ccc; font-family: monospace; font-size: 0.9em; white-space: pre-wrap;">{highlighted_code}</pre>'
        
        return html_content
    
    def _render_latex(self, latex: str, display_mode: bool = True) -> str:
        """
        渲染LaTeX公式为图片
        
        Args:
            latex: LaTeX公式内容
            display_mode: 是否为显示模式（块级公式）
            
        Returns:
            str: HTML img标签
        """
        # 计算缓存键
        cache_key = hashlib.md5(latex.encode()).hexdigest()
        
        # 检查缓存
        if cache_key in _latex_cache:
            return _latex_cache[cache_key]
        
        # 检查 matplotlib 是否可用
        if not _ensure_matplotlib():
            logger.warning("[_render_latex] matplotlib 不可用，返回原始LaTeX")
            escaped_latex = html.escape(latex)
            return f'<pre style="background-color: #f0f0f0; padding: 8px; font-family: monospace; font-size: 0.9em; overflow-x: auto;">{escaped_latex}</pre>'
        
        try:
            import matplotlib
            import matplotlib.pyplot as plt
            from matplotlib import mathtext
            import io
            
            # 设置matplotlib不显示图形界面
            matplotlib.use('Agg')
            
            # 清理LaTeX字符串
            latex = latex.strip()
            
            # 创建图形 - 使用更大的初始尺寸
            fig = plt.figure(figsize=(6, 2) if not display_mode else (8, 3))
            fig.patch.set_facecolor('white')
            
            # 添加文本 - 使用Figure的坐标系统
            text = fig.text(0.5, 0.5, f'${latex}$', fontsize=14 if not display_mode else 18,
                          ha='center', va='center',
                          usetex=False,
                          fontproperties=None)
            
            # 强制绘制以获取正确的文本边界
            fig.canvas.draw()
            
            # 调整大小以适应文本
            bbox = text.get_window_extent()
            bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
            
            # 调整图形大小
            width, height = bbox.width, bbox.height
            if width > 0 and height > 0:
                fig.set_size_inches(width * 1.5, height * 1.5)
            
            # 转换为base64图片
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                       facecolor='white', edgecolor='none', pad_inches=0.1)
            buffer.seek(0)
            
            # 转换为base64
            img_base64 = base64.b64encode(buffer.read()).decode()
            
            # 释放资源
            plt.close(fig)
            buffer.close()
            
            # 创建HTML img标签
            html_content = f'<img src="data:image/png;base64,{img_base64}" '
            html_content += f'style="max-width: 100%; height: auto; margin: 10px 0;" '
            html_content += f'alt="LaTeX公式" '
            html_content += f'onerror="this.style.display=&#39;none&#39;; this.parentNode.innerHTML=&#39;&lt;span style=color:#999&gt;[LaTeX公式]&lt;/span&gt;&#39;;">'
            
            # 缓存结果
            _latex_cache[cache_key] = html_content
            
            return html_content
            
        except Exception as e:
            logger.error(f"[_render_latex] 渲染LaTeX失败: {e}")
            # 返回转义的LaTeX作为备用
            escaped_latex = html.escape(latex)
            return f'<pre style="background-color: #f0f0f0; padding: 8px; font-family: monospace; font-size: 0.9em; overflow-x: auto;">{escaped_latex}</pre>'
        
        # 使用 <pre> 标签，添加data-latex属性供KaTeX使用
        html_content = f'<pre class="katex-block" data-latex="{escaped_latex}" style="background-color: #f0f0f0; padding: 8px; font-family: monospace; font-size: 0.9em; overflow-x: auto;">{escaped_latex}</pre>'
        
        return html_content
    
    def _highlight_code(self, code: str, language: str) -> str:
        """
        代码语法高亮
        
        Args:
            code: 代码内容
            language: 编程语言
            
        Returns:
            str: 高亮后的HTML
        """
        try:
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name, TextLexer
            from pygments.formatters import HtmlFormatter
            
            # 获取语言lexer
            try:
                lexer = get_lexer_by_name(language, stripall=True)
            except:
                lexer = TextLexer()
            
            # 使用HTML格式器
            formatter = HtmlFormatter(
                linenos=False,
                cssclass='highlight',
                style='default'
            )
            
            return highlight(code, lexer, formatter)
            
        except ImportError:
            # pygments不可用，返回转义后的代码
            return html.escape(code)
        except Exception as e:
            # 高亮失败，返回转义后的代码
            return html.escape(code)
    
    def _render_table(self, text: str) -> str:
        """
        渲染表格
        
        Args:
            text: 表格文本
            
        Returns:
            str: HTML表格
        """
        try:
            lines = text.strip().split('\n')
            
            # 过滤分隔行
            data_lines = [line for line in lines if not re.match(r'^[\s|:-]+$', line)]
            
            if not data_lines:
                return None
            
            # 解析表格数据
            # 需要特殊处理：LaTeX公式中的|字符不应作为表格分隔符
            rows = []
            for line in data_lines:
                # 首先保护LaTeX公式中的内容
                protected_parts = []
                i = 0
                while i < len(line):
                    # 查找 $...$ 或 $$...$$
                    if line[i] == '$':
                        if i + 1 < len(line) and line[i + 1] == '$':
                            # 块级LaTeX $$...$$
                            end = line.find('$$', i + 2)
                            if end == -1:
                                # 没找到结束的$$，添加剩余内容
                                protected_parts.append(line[i:])
                                break
                            # 提取LaTeX内容，将其中的|替换为占位符
                            latex_content = line[i:end + 2]
                            protected_parts.append(latex_content.replace('|', '%%TABLE_PIPE%%'))
                            i = end + 2
                        else:
                            # 行内LaTeX $...$
                            end = line.find('$', i + 1)
                            if end == -1:
                                # 没找到结束的$，添加剩余内容
                                protected_parts.append(line[i:])
                                break
                            # 提取LaTeX内容，将其中的|替换为占位符
                            latex_content = line[i:end + 1]
                            protected_parts.append(latex_content.replace('|', '%%TABLE_PIPE%%'))
                            i = end + 1
                    else:
                        protected_parts.append(line[i])
                        i += 1
                
                # 重新组合并分割
                protected_line = ''.join(protected_parts)
                cells = [cell.strip().replace('%%TABLE_PIPE%%', '|') for cell in protected_line.split('|')[1:-1]]
                
                if cells:
                    rows.append(cells)
            
            if not rows:
                return None
            
            # 构建HTML表格 - 使用内联样式
            html_parts = ['<div style="overflow-x: auto; margin: 1em 0;"><table style="border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.95em;">']
            
            # 第一行作为表头
            if len(rows) > 0:
                html_parts.append('<thead><tr>')
                for cell in rows[0]:
                    html_parts.append(f'<th style="border: 1px solid #ddd; padding: 8px 12px; background-color: #f5f5f5; font-weight: bold; text-align: left;">{self._inline_format(cell)}</th>')
                html_parts.append('</tr></thead>')
                
                # 其余行作为表体
                if len(rows) > 1:
                    html_parts.append('<tbody>')
                    for row in rows[1:]:
                        html_parts.append('<tr>')
                        for cell in row:
                            html_parts.append(f'<td style="border: 1px solid #ddd; padding: 8px 12px; text-align: left;">{self._inline_format(cell)}</td>')
                        html_parts.append('</tr>')
                    html_parts.append('</tbody>')
            
            html_parts.append('</table></div>')
            return '\n'.join(html_parts)
            
        except Exception as e:
            # 表格解析失败，返回原始文本
            return f'<p>{self._inline_format(text)}</p>'
    
    def _render_image(self, alt: str, url: str) -> str:
        """
        渲染图片
        
        Args:
            alt: 替代文本
            url: 图片URL
            
        Returns:
            str: HTML图片标签
        """
        # 安全检查
        if not self.options.allow_external_images and url.startswith('http'):
            return f'<span style="color: #999; font-style: italic; padding: 4px; background-color: #f5f5f5; border-radius: 3px;">[外部图片: {alt}]</span>'
        
        # 验证URL
        if not url.startswith(('http://', 'https://', 'data:')):
            return f'<span style="color: #999; font-style: italic; padding: 4px; background-color: #f5f5f5; border-radius: 3px;">[无效图片URL]</span>'
        
        max_width = self.options.max_image_width
        
        return f'''
<img 
    src="{url}" 
    alt="{alt}" 
    style="max-width: {max_width}px; height: auto; border-radius: 3px;"
    onerror="this.style.display='none'; this.parentNode.innerHTML='<span style=color: #999; font-style: italic; padding: 4px; background-color: #f5f5f5; border-radius: 3px;>[图片加载失败]</span>';"
>
'''
    
    def _wrap_with_styles(self, html_content: str) -> str:
        """包装HTML内容（QTextBrowser不支持<style>标签，样式已在各元素中内联）"""
        # QTextBrowser不支持<style>标签，所有样式都必须是内联的
        # 这里只做简单的包装，不添加样式
        return f'<div>{html_content}</div>'
    
    def highlight_code(self, code: str, language: str) -> str:
        """
        高亮代码（独立方法）
        
        Args:
            code: 代码内容
            language: 编程语言
            
        Returns:
            str: 高亮后的HTML
        """
        return self._highlight_code(code, language)


# 便捷函数
def render_markdown(markdown_text: str, options: RenderOptions = None) -> str:
    """渲染Markdown文本"""
    renderer = MarkdownRenderer(options)
    return renderer.render(markdown_text)


def render_code(code: str, language: str = '') -> str:
    """渲染代码块"""
    renderer = MarkdownRenderer()
    return renderer._render_code(code, language)


# 测试代码
if __name__ == "__main__":
    print("=" * 50)
    print("Markdown渲染器测试")
    print("=" * 50)
    
    # 创建渲染器
    renderer = MarkdownRenderer()
    
    # 测试文本
    test_markdown = r"""
# 标题一

## 标题二

这是一段**粗体**和*斜体*以及`行内代码`。

- 项目1
- 项目2
  - 子项目

1. 有序列表1
2. 有序列表2

> 这是引用文本

```python
def hello():
    print("Hello, World!")
```

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| D   | E   | F   |

[链接](https://example.com)

![图片](https://via.placeholder.com/150)

行内LaTeX公式：$E = mc^2$

块级LaTeX公式：
$$
\frac{\partial MSE}{\partial w} = -\frac{2}{n}\sum_{i=1}^{n}x_i(y_i - \hat{y}_i)
$$

- [x] 已完成任务
- [ ] 未完成任务
"""

    # 渲染
    html_output = renderer.render(test_markdown)
    
    # 保存到文件
    with open("test_output.html", "w", encoding="utf-8") as f:
        f.write(html_output)
    
    print("\n测试完成！")
    print(f"生成的HTML已保存到: test_output.html")
    print(f"HTML长度: {len(html_output)} 字符")
    
    # 测试代码高亮
    print("\n测试代码高亮:")
    test_code = '''def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''
    highlighted = renderer._highlight_code(test_code, "python")
    print(f"Python代码高亮成功: {'<span' in highlighted}")
    
    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)
