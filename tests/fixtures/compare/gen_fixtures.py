"""生成对比 E2E 测试用的 fixture DOCX 文件。"""

from pathlib import Path
from docx import Document

OUT = Path(__file__).parent


def _write(name: str, paragraphs: list[str]) -> None:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(OUT / name)


def gen() -> None:
    # ① 段落级精确匹配
    _write("para_a.docx", [
        "投标人应具有独立承担民事责任的能力。",
        "文件A独有的第二段内容。",
    ])
    _write("para_b.docx", [
        "投标人应具有独立承担民事责任的能力。",
        "文件B独有的第二段内容。",
    ])

    # ② 句子级精确匹配
    _write("sent_a.docx", [
        "采购人可自行选择。供应商不得串通。评标委员会独立评审。",
    ])
    _write("sent_b.docx", [
        "采购人可自行选择。代理机构按规定。评标委员会独立评审。",
    ])

    # ③ 片段级连续匹配
    _write("seg_a.docx", [
        "甲方根据具有良好的商业信誉和健全的财务会计制度的要求执行。",
    ])
    _write("seg_b.docx", [
        "乙方应当具有良好的商业信誉和健全的财务会计制度并提交证明。",
    ])

    # ④ 三级混合
    _write("mix_a.docx", [
        "完全相同的第一段落。",
        "第一句共享。第二句不同A。第三句共享。",
        "前缀具有良好的商业信誉和健全的财务会计制度后缀A。",
        "独有段落A。",
    ])
    _write("mix_b.docx", [
        "完全相同的第一段落。",
        "第一句共享。第二句不同B。第三句共享。",
        "开头具有良好的商业信誉和健全的财务会计制度尾部B。",
        "独有段落B。",
    ])

    # ⑥ 无重复
    _write("unique_a.docx", ["甲方内容。"])
    _write("unique_b.docx", ["乙方内容。"])

    # ⑦ 多文档 N=4
    _write("multi_1.docx", [
        "四文件共享段落。",
        "仅12共享段落。",
        "仅1独有段落。",
    ])
    _write("multi_2.docx", [
        "四文件共享段落。",
        "仅12共享段落。",
        "仅2独有段落。",
    ])
    _write("multi_3.docx", [
        "四文件共享段落。",
        "仅34共享段落。",
        "仅3独有段落。",
    ])
    _write("multi_4.docx", [
        "四文件共享段落。",
        "仅34共享段落。",
        "仅4独有段落。",
    ])

    print(f"已生成 14 个 fixture DOCX 文件到 {OUT}")


if __name__ == "__main__":
    gen()
