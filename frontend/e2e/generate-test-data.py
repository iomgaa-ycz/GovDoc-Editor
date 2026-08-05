#!/usr/bin/env python3
"""e2e 测试 fixture 生成器。

在 frontend/e2e/.test-data/ 下生成最小测试文件，消除对 ../real_data 的依赖。
用法：source activate govdoc-auditor-v3 && python3 e2e/generate-test-data.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, ".test-data")
os.makedirs(OUT, exist_ok=True)


def gen_pdf():
    """生成最小合法 PDF（含中文文本占位）。"""
    # 手写 PDF 结构 —— 单页，内容 "E2E Test"
    objects = []
    offsets = []
    body = b"%PDF-1.4\n"

    # 1: Catalog
    offsets.append(len(body))
    obj = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    body += obj

    # 2: Pages
    offsets.append(len(body))
    obj = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    body += obj

    # 4: Font
    offsets.append(len(body))
    obj = b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    body += obj

    # 5: stream content
    stream = b"BT /F1 12 Tf 100 700 Td (E2E Test PDF) Tj ET"
    offsets.append(len(body))
    obj = (
        b"5 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream
        + b"\nendstream\nendobj\n"
    )
    body += obj

    # 3: Page (referencing font F1 = obj 4, contents = obj 5)
    offsets.insert(2, len(body))
    obj = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>\n"
        b"endobj\n"
    )
    body += obj

    # xref
    xref_off = len(body)
    body += b"xref\n0 6\n"
    body += b"0000000000 65535 f \n"
    for off in offsets:
        body += f"{off:010d} 00000 n \n".encode()

    body += b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
    body += b"startxref\n" + str(xref_off).encode() + b"\n%%EOF\n"

    path = os.path.join(OUT, "E2E测试招标文件.pdf")
    with open(path, "wb") as f:
        f.write(body)
    print(f"  ✓ {path} ({len(body)} bytes)")


def gen_docx():
    """生成最小 DOCX（含中文段落）。"""
    from docx import Document

    doc = Document()
    doc.add_paragraph("E2E测试声明函内容")
    path = os.path.join(OUT, "E2E测试声明函.docx")
    doc.save(path)
    size = os.path.getsize(path)
    print(f"  ✓ {path} ({size} bytes)")


def gen_xlsx():
    """生成审核点导入 XLSX（表头含 checkpoint_import.py 要求的关键词）。

    列结构：大类(0) | 违法违规问题(1) | 表现形式(2) | 处理依据(3) | 处罚依据(4)
    """
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    # 表头 —— checkpoint_import.py 识别的关键词
    ws.append(["大类", "违法违规问题", "表现形式", "处理依据", "处罚依据"])
    # 数据行
    ws.append([
        "E2E测试类别",
        "E2E测试违规问题1",
        "E2E测试表现形式描述1",
        "E2E测试处理依据1",
        "E2E测试处罚依据1",
    ])
    ws.append([
        "E2E测试类别",
        "E2E测试违规问题2",
        "E2E测试表现形式描述2",
        "E2E测试处理依据2",
        "E2E测试处罚依据2",
    ])
    path = os.path.join(OUT, "E2E测试审核点.xlsx")
    wb.save(path)
    size = os.path.getsize(path)
    print(f"  ✓ {path} ({size} bytes)")


def gen_md():
    """生成法规 Markdown 文件（AL8 AI 提取用）。"""
    content = """\
# E2E测试法规指引

## 第一条 采购规范性要求
采购人应当按照规定编制采购文件，确保采购活动公开、公平、公正。

## 第二条 违规行为处理
对违反政府采购规定的单位和个人，依法给予行政处罚。
"""
    path = os.path.join(OUT, "E2E测试法规指引.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ {path} ({len(content.encode('utf-8'))} bytes)")


def gen_dummy_doc():
    """生成假 .doc 文件（AL10 仅测试 UI 回显，不提交后端处理）。"""
    path = os.path.join(OUT, "E2E测试法规指引.doc")
    # 写入最小占位内容 —— 后端会尝试转换，但 AL10 不会提交
    with open(path, "wb") as f:
        f.write(b"E2E dummy doc placeholder")
    print(f"  ✓ {path} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    print(f"生成 e2e fixture 到 {OUT}/")
    gen_pdf()
    gen_docx()
    gen_xlsx()
    gen_md()
    gen_dummy_doc()
    print("完成。")
