"""DOCX 文本提取工具。

该模块直接读取 docx 压缩包中的 WordprocessingML，按正文和表格中的段落顺序提取文本。
"""

from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_TAG = f"{{{WORD_NAMESPACE}}}"


def normalize_text(text: str) -> str:
    """规范化 Word 文本中的空白字符和零宽字符。"""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\u200b\u200c\u200d]", "", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def paragraph_text(paragraph: ET.Element) -> str:
    """提取单个 Word 段落节点中的纯文本。"""
    parts: list[str] = []

    for node in paragraph.iter():
        if node.tag == f"{WORD_TAG}t":
            parts.append(node.text or "")
        elif node.tag == f"{WORD_TAG}tab":
            parts.append("\t")
        elif node.tag in {f"{WORD_TAG}br", f"{WORD_TAG}cr"}:
            parts.append("\n")

    return normalize_text("".join(parts))


def iter_paragraphs(container: ET.Element) -> list[str]:
    """按文档顺序遍历容器中的段落和表格段落。"""
    paragraphs: list[str] = []

    for child in list(container):
        if child.tag == f"{WORD_TAG}p":
            text = paragraph_text(child)
            if text:
                paragraphs.append(text)
        elif child.tag == f"{WORD_TAG}tbl":
            paragraphs.extend(iter_table_paragraphs(child))

    return paragraphs


def iter_table_paragraphs(table: ET.Element) -> list[str]:
    """提取表格中所有单元格内的段落文本。"""
    paragraphs: list[str] = []

    for row in table.findall(f"{WORD_TAG}tr"):
        for cell in row.findall(f"{WORD_TAG}tc"):
            paragraphs.extend(iter_paragraphs(cell))

    return paragraphs


def extract_docx_paragraphs(path: str | Path) -> list[str]:
    """从 DOCX 文件中提取非空正文段落。"""
    file_path = Path(path)

    with zipfile.ZipFile(file_path) as archive:
        try:
            document_xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError(f"{file_path} is not a valid DOCX file.") from exc

    root = ET.fromstring(document_xml)
    body = root.find(f"{WORD_TAG}body")

    if body is None:
        return []

    return iter_paragraphs(body)


def extract_docx_full_text(path: str | Path) -> str:
    """将 DOCX 段落合并为换行分隔的完整文本。"""
    return "\n".join(extract_docx_paragraphs(path))


def _clean_markdown_line(line: str) -> str:
    """清理单行 Markdown 标记，保留可对比文本。"""
    item = line.strip()
    if not item or item.startswith("!["):
        return ""

    if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", item):
        return ""

    item = re.sub(r"^#{1,6}\s*", "", item)
    item = re.sub(r"^>\s*", "", item)
    item = re.sub(r"^[-*+]\s+", "", item)
    item = re.sub(r"^\d+[.)]\s+", "", item)
    item = re.sub(r"^\[[ xX]\]\s+", "", item)
    item = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", item)
    item = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", item)
    item = item.replace("**", "").replace("__", "").replace("`", "")

    if "|" in item:
        cells = [cell.strip() for cell in item.strip("|").split("|")]
        item = " ".join(cell for cell in cells if cell)

    return normalize_text(item)


def extract_markdown_paragraphs(markdown_text: str) -> list[str]:
    """从 Markdown 文本中提取可参与对比的正文段落。

    PDF 经 Scrivai/MonkeyOCR 转换后通常是 Markdown。本函数按空行切块，
    块内按行清理常见 Markdown 标记并合并，避免 OCR 硬换行把同一段拆碎。
    """
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n+", markdown_text.replace("\r", "\n")):
        lines = [_clean_markdown_line(line) for line in block.splitlines()]
        text = normalize_text(" ".join(line for line in lines if line))
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_paragraphs_from_path(path: str | Path) -> list[str]:
    """从无需 OCR 的本地文件直接提取段落。"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_paragraphs(file_path)
    raise ValueError(f"不支持直接提取的文件格式: {suffix}")
