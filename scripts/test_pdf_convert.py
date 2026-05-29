"""手动测试 PDF 转换，在 4090 上运行以排查 mineru 模型问题。

用法（在 4090 tmux 中）：
  conda activate govdoc-auditor-v3
  CUDA_VISIBLE_DEVICES=0 python scripts/test_pdf_convert.py
"""

import traceback

PDF_PATH = "/home/pci/Project/GovDoc-Editor-testing/data/storage/raw/1广东宏业建设工程有限公司.pdf"

print("=" * 60)
print("Step 1: 检查 mineru 配置")
print("=" * 60)

import json
from pathlib import Path

mineru_cfg = Path.home() / "mineru.json"
if mineru_cfg.exists():
    cfg = json.loads(mineru_cfg.read_text())
    models_dir = cfg.get("models-dir", {}).get("pipeline", "未配置")
    print(f"  mineru.json 路径: {mineru_cfg}")
    print(f"  pipeline 模型目录: {models_dir}")
    print(f"  模型目录存在: {Path(models_dir).exists() if models_dir != '未配置' else 'N/A'}")
else:
    print(f"  ⚠ mineru.json 不存在: {mineru_cfg}")

print()
print("=" * 60)
print("Step 2: 检查 HuggingFace 缓存")
print("=" * 60)

hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
ms_cache = Path.home() / ".cache" / "modelscope" / "hub"
print(f"  HF 缓存: {hf_cache} (存在: {hf_cache.exists()})")
print(f"  MS 缓存: {ms_cache} (存在: {ms_cache.exists()})")

if hf_cache.exists():
    hf_models = [p.name for p in hf_cache.iterdir() if p.is_dir()]
    print(f"  HF 模型: {hf_models[:10]}")

if ms_cache.exists():
    ms_models = list(ms_cache.rglob("PDF-Extract*"))
    print(f"  MS PDF-Extract: {ms_models[:5]}")

print()
print("=" * 60)
print("Step 3: 直接调用 mineru do_parse（绕过 scrivai）")
print("=" * 60)

try:
    from mineru.cli.common import do_parse

    print("  ✓ mineru.cli.common.do_parse 导入成功")
except ImportError as e:
    print(f"  ✗ mineru 导入失败: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("Step 4: 通过 MarkdownConverter 转换 PDF")
print("=" * 60)

from scrivai import MarkdownConverter

print(f"  PDF: {PDF_PATH}")
print(f"  文件存在: {Path(PDF_PATH).exists()}")
if Path(PDF_PATH).exists():
    print(f"  文件大小: {Path(PDF_PATH).stat().st_size / 1024 / 1024:.1f} MB")

print()
print("  开始转换...")
try:
    with MarkdownConverter(mode="gpu") as conv:
        md = conv.convert(PDF_PATH)
    print(f"  ✓ 转换成功！长度: {len(md)} 字符")
    print(f"  前 300 字符:\n{md[:300]}")
except Exception as e:
    print(f"  ✗ 转换失败: {e}")
    traceback.print_exc()
