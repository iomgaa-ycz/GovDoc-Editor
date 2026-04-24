"""文档对比 DOCX 提取器测试。"""

from __future__ import annotations

from pathlib import Path

from docx import Document

from govdoc.compare.extractor import extract_docx_full_text, extract_docx_paragraphs


def _write_docx(path: Path) -> None:
    """写入包含正文段落和表格段落的 DOCX 测试文件。"""
    document = Document()
    document.add_paragraph("  第一段\xa0内容  ")
    document.add_paragraph("第二段")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "表格单元 A"
    table.cell(0, 1).text = "表格单元 B"
    document.save(path)


def test_extract_docx_paragraphs_includes_table_cells(tmp_path: Path) -> None:
    """提取器应按正文顺序返回段落和表格单元格文本。"""
    docx_path = tmp_path / "sample.docx"
    _write_docx(docx_path)

    paragraphs = extract_docx_paragraphs(docx_path)

    assert paragraphs == ["第一段 内容", "第二段", "表格单元 A", "表格单元 B"]


def test_extract_docx_full_text_joins_paragraphs(tmp_path: Path) -> None:
    """完整文本接口应使用换行符连接所有段落。"""
    docx_path = tmp_path / "sample.docx"
    _write_docx(docx_path)

    full_text = extract_docx_full_text(docx_path)

    assert full_text == "第一段 内容\n第二段\n表格单元 A\n表格单元 B"
