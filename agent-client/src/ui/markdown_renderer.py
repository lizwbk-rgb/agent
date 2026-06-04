"""
Markdown渲染器模块

支持Markdown解析、代码语法高亮、表格渲染、URL图片渲染
"""

import re
import html
from typing import Optional
from dataclasses import dataclass


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
    
    def __init__(self, options: RenderOptions = None):
        """
        初始化渲染器
        
        Args:
            options: 渲染选项
        """
        self.options = options or RenderOptions()
        self._lexer = None
    
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
        
        # 解析并渲染
        html_parts = []
        
        # 处理代码块（需要优先处理）
        text = self._process_code_blocks(text, html_parts)
        
        # 按段落分割处理
        paragraphs = self._split_paragraphs(text)
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
            
            # 检测段落类型
            html_content = self._process_paragraph(paragraph)
            if html_content:
                html_parts.append(html_content)
        
        # 组装HTML
        return self._postprocess(html_parts)
    
    def _preprocess(self, text: str) -> str:
        """预处理文本"""
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 处理HTML实体
        text = html.escape(text, quote=False)
        
        return text
    
    def _postprocess(self, html_parts: list) -> str:
        """后处理HTML"""
        # 组装
        html_content = '\n'.join(html_parts)
        
        # 添加样式
        styled_html = self._wrap_with_styles(html_content)
        
        return styled_html
    
    def _process_code_blocks(self, text: str, html_parts: list) -> str:
        """处理代码块"""
        # 匹配围栏代码块 ```language\ncode\n```
        pattern = r'```(\w*)\n(.*?)```'
        
        def replace_code_block(match):
            language = match.group(1) or ''
            code = match.group(2)
            
            # 渲染代码
            code_html = self._render_code(code, language)
            html_parts.append(code_html)
            
            return ''  # 移除已处理的代码块
        
        return re.sub(pattern, replace_code_block, text, flags=re.DOTALL)
    
    def _split_paragraphs(self, text: str) -> list:
        """分割段落"""
        # 按空行分割
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _process_paragraph(self, paragraph: str) -> str:
        """处理单个段落"""
        # 检测标题
        if paragraph.startswith('# '):
            return f'<h1>{self._inline_format(paragraph[2:])}</h1>'
        elif paragraph.startswith('## '):
            return f'<h2>{self._inline_format(paragraph[3:])}</h2>'
        elif paragraph.startswith('### '):
            return f'<h3>{self._inline_format(paragraph[4:])}</h3>'
        elif paragraph.startswith('#### '):
            return f'<h4>{self._inline_format(paragraph[5:])}</h4>'
        
        # 检测引用
        if paragraph.startswith('> '):
            content = self._inline_format(paragraph[2:])
            return f'<blockquote>{content}</blockquote>'
        
        # 检测列表
        list_match = re.match(r'^(\d+)\.\s+(.+)$', paragraph)
        if list_match:
            return f'<ol><li>{self._inline_format(list_match.group(2))}</li></ol>'
        
        ul_match = re.match(r'^[-*+]\s+(.+)$', paragraph)
        if ul_match:
            return f'<ul><li>{self._inline_format(ul_match.group(1))}</li></ul>'
        
        # 检测表格
        if self.options.render_tables and '|' in paragraph:
            table_html = self._render_table(paragraph)
            if table_html:
                return table_html
        
        # 检测水平线
        if re.match(r'^[-=*_]{3,}$', paragraph):
            return '<hr>'
        
        # 检测任务列表
        task_match = re.match(r'^[-*+]\s+\[[ x]\]\s+(.+)$', paragraph, re.IGNORECASE)
        if task_match:
            checked = 'checked' if '[x]' in paragraph.lower() else ''
            return f'<ul><li><input type="checkbox" {checked} disabled>{task_match.group(1)}</li></ul>'
        
        # 普通段落
        return f'<p>{self._inline_format(paragraph)}</p>'
    
    def _inline_format(self, text: str) -> str:
        """处理行内格式"""
        # 粗体和斜体
        # ***text*** 或 ___text___
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'___(.+?)___', r'<strong><em>\1</em></strong>', text)
        
        # 粗体 **text** 或 __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        
        # 斜体 *text* 或 _text_
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
        
        # 删除线 ~~text~~
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
        
        # 行内代码 `code`
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        
        # 链接 [text](url)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
        
        # 图片 ![alt](url)
        if self.options.render_images:
            text = re.sub(
                r'!\[(.+?)\]\((.+?)\)',
                lambda m: self._render_image(m.group(1), m.group(2)),
                text
            )
        
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
        # 高亮代码
        highlighted_code = code
        
        if self.options.code_highlight and language:
            highlighted_code = self._highlight_code(code, language)
        else:
            # 转义HTML
            highlighted_code = html.escape(code)
        
        # 添加行号
        if self.options.line_numbers:
            lines = code.split('\n')
            numbered_lines = []
            for i, line in enumerate(lines, 1):
                highlighted_line = self._highlight_code(line, language) if self.options.code_highlight and language else html.escape(line)
                numbered_lines.append(f'<span class="line-number">{i}</span><span class="line-content">{highlighted_line}</span>')
            highlighted_code = '\n'.join(numbered_lines)
        
        # 构建HTML
        lang_label = language.upper() if language else ''
        
        html_content = f'''
<div class="code-block">
    <div class="code-header">
        <span class="language">{lang_label}</span>
        <button class="copy-btn" onclick="copyCode(this)">复制</button>
    </div>
    <pre class="code-content"><code class="language-{language}">{highlighted_code}</code></pre>
</div>
'''
        
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
            rows = []
            for line in data_lines:
                cells = [cell.strip() for cell in line.split('|')[1:-1]]  # 去掉首尾空元素
                if cells:
                    rows.append(cells)
            
            if not rows:
                return None
            
            # 构建HTML表格
            html_parts = ['<div class="table-container"><table>']
            
            # 第一行作为表头
            if len(rows) > 0:
                html_parts.append('<thead><tr>')
                for cell in rows[0]:
                    html_parts.append(f'<th>{self._inline_format(cell)}</th>')
                html_parts.append('</tr></thead>')
                
                # 其余行作为表体
                if len(rows) > 1:
                    html_parts.append('<tbody>')
                    for row in rows[1:]:
                        html_parts.append('<tr>')
                        for cell in row:
                            html_parts.append(f'<td>{self._inline_format(cell)}</td>')
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
            return f'<span class="image-placeholder">[外部图片: {alt}]</span>'
        
        # 验证URL
        if not url.startswith(('http://', 'https://', 'data:')):
            return f'<span class="image-placeholder">[无效图片URL]</span>'
        
        max_width = self.options.max_image_width
        
        return f'''
<img 
    src="{url}" 
    alt="{alt}" 
    class="markdown-image"
    style="max-width: {max_width}px; height: auto;"
    onerror="this.style.display='none'; this.parentNode.innerHTML='<span class=image-placeholder>[图片加载失败]</span>';"
>
'''
    
    def _wrap_with_styles(self, html_content: str) -> str:
        """添加CSS样式"""
        css = '''
<style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        background-color: #fff;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
    }
    
    h1 { font-size: 2em; margin: 0.67em 0; }
    h2 { font-size: 1.5em; margin: 0.75em 0; }
    h3 { font-size: 1.17em; margin: 0.83em 0; }
    h4 { font-size: 1em; margin: 1.12em 0; }
    
    p { margin: 1em 0; }
    
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    
    code {
        background-color: #f5f5f5;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 0.9em;
    }
    
    pre {
        background-color: #f5f5f5;
        padding: 1em;
        border-radius: 6px;
        overflow-x: auto;
        margin: 1em 0;
    }
    
    blockquote {
        border-left: 4px solid #ddd;
        margin: 1em 0;
        padding: 0.5em 1em;
        background-color: #f9f9f9;
    }
    
    ul, ol {
        margin: 1em 0;
        padding-left: 2em;
    }
    
    li { margin: 0.5em 0; }
    
    hr {
        border: none;
        border-top: 1px solid #ddd;
        margin: 2em 0;
    }
    
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1em 0;
    }
    
    th, td {
        border: 1px solid #ddd;
        padding: 8px 12px;
        text-align: left;
    }
    
    th {
        background-color: #f5f5f5;
        font-weight: bold;
    }
    
    .table-container {
        overflow-x: auto;
        margin: 1em 0;
    }
    
    .code-block {
        margin: 1em 0;
        border-radius: 6px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .code-header {
        background-color: #f5f5f5;
        padding: 8px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #ddd;
    }
    
    .language {
        font-size: 0.85em;
        color: #666;
        font-weight: bold;
    }
    
    .copy-btn {
        background-color: #007bff;
        color: white;
        border: none;
        padding: 4px 8px;
        border-radius: 3px;
        cursor: pointer;
        font-size: 0.85em;
    }
    
    .copy-btn:hover { background-color: #0056b3; }
    
    .code-content {
        margin: 0;
        padding: 12px;
        background-color: #1e1e1e;
        color: #d4d4d4;
        overflow-x: auto;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 0.9em;
        line-height: 1.5;
    }
    
    .markdown-image {
        display: block;
        margin: 1em auto;
    }
    
    .image-placeholder {
        display: inline-block;
        padding: 4px 8px;
        background-color: #f0f0f0;
        border: 1px solid #ddd;
        border-radius: 3px;
        color: #999;
    }
    
    /* Pygments样式 */
    .highlight { background-color: #f8f8f8; }
    .highlight .hll { background-color: #ffffcc; }
    .highlight .c { color: #408080; font-style: italic; }
    .highlight .err { border: 1px solid #FF0000; }
    .highlight .k { color: #008000; font-weight: bold; }
    .highlight .o { color: #666666; }
    .highlight .ch { color: #408080; font-style: italic; }
    .highlight .cm { color: #408080; font-style: italic; }
    .highlight .cp { color: #BC7A00; }
    .highlight .cpf { color: #408080; font-style: italic; }
    .highlight .c1 { color: #408080; font-style: italic; }
    .highlight .cs { color: #408080; font-style: italic; }
    .highlight .gd { color: #A00000; }
    .highlight .ge { color: #000080; font-style: italic; }
    .highlight .gr { color: #FF0000; }
    .highlight .gh { color: #000080; font-weight: bold; }
    .highlight .gi { color: #008000; }
    .highlight .go { color: #888888; }
    .highlight .gp { color: #000080; font-weight: bold; }
    .highlight .grr { color: #FF0000; }
    .highlight .w { color: #bbbbbb; }
    .highlight .mf { color: #6600EE; font-weight: bold; }
    .highlight .mh { color: #6600EE; }
    .highlight .mi { color: #6600EE; font-weight: bold; }
    .highlight .mo { color: #6600EE; font-weight: bold; }
    .highlight .mq { color: #BA2121; }
    .highlight .nl { color: #767600; }
    .highlight .nc { color: #0000FF; font-weight: bold; }
    .highlight .nt { color: #008000; font-weight: bold; }
    .highlight .nn { color: #0000FF; }
    .highlight .no { color: #880000; }
    .highlight .nb { color: #008000; }
    .highlight .nv { color: #19177C; }
    .highlight .na { color: #7D9029; }
    .highlight .ns { color: #BB6688; }
    .highlight .nd { color: #AA22FF; }
    .highlight .ne { color: #D2413A; font-weight: bold; }
    .highlight .nf { color: #0000FF; }
    .highlight .nl { color: #0000FF; }
    .highlight .nn { color: #0000FF; }
    .highlight .nt { color: #008000; font-weight: bold; }
    .highlight .nv { color: #19177C; }
    .highlight .ow { color: #AA22FF; font-weight: bold; }
    .highlight .w { color: #bbbbbb; }
    .highlight .mb { color: #6600EE; font-weight: bold; }
    .highlight .mf { color: #6600EE; font-weight: bold; }
    .highlight .mh { color: #6600EE; }
    .highlight .mi { color: #6600EE; font-weight: bold; }
    .highlight .mo { color: #6600EE; font-weight: bold; }
    .highlight .sb { color: #BB2222; }
    .highlight .sc { color: #BB2222; }
    .highlight .sd { color: #BB2222; font-style: italic; }
    .highlight .s2 { color: #BB2222; }
    .highlight .se { color: #BB2222; font-weight: bold; }
    .highlight .sh { color: #BB2222; }
    .highlight .si { color: #BB6688; font-weight: bold; }
    .highlight .sx { color: #008000; }
    .highlight .sr { color: #BB6688; }
    .highlight .s1 { color: #BB2222; }
    .highlight .ss { color: #19177C; }
</style>
<script>
    function copyCode(btn) {
        const code = btn.parentElement.nextElementSibling.textContent;
        navigator.clipboard.writeText(code).then(() => {
            btn.textContent = '已复制';
            setTimeout(() => btn.textContent = '复制', 2000);
        });
    }
</script>
'''
        
        return f'{css}<div class="markdown-content">{html_content}</div>'
    
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
    test_markdown = """
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
