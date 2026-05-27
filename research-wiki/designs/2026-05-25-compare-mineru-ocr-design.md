# 对比模块 MinerU OCR 后端集成设计

## 概述

将文档对比模块的 PDF 转 Markdown 后端从 GLM-OCR（云端）切换为 MinerU（本地 Python 库），解决对比场景下 GLM-OCR 串行 + 速率限制导致的速度瓶颈。主审查管道不受影响，继续使用 GLM-OCR。

## 驱动力

| 因素 | GLM-OCR（现状） | MinerU（目标） |
|------|-----------------|---------------|
| 运行方式 | 云端 API | 本地 Python 库 |
| 并发限制 | 受 API 速率限制，当前 `max_workers=1` | 无 API 限制，可按 CPU/GPU 并发 |
| 网络依赖 | 需要 NO_PROXY 豁免 | 无网络调用 |
| 对比场景痛点 | 多文件批量转换极慢（3600s 超时） | 本地运算，速度大幅提升 |

## 设计方案：对等双 DocumentStore

### 核心原则

两个 DocumentStore 实例是**对等的一等公民**——同一个类、相同的能力（`save_raw`、`get_or_convert`、SHA256 缓存），只是配置参数不同。不存在"主 + 辅"的概念。

### 架构

```
主管道（审查）:
  upload PDF → DocumentStore(storage_root, ocr_backend="glm")
            → scrivai.to_markdown(ocr_backend="glm")  [云端 GLM-OCR]
            → {storage_root}/prepared/{sha}.md

对比模块:
  upload PDF → DocumentStore(compare_storage_root, ocr_backend="mineru")
            → scrivai.to_markdown(ocr_backend="mineru")  [本地 MinerU]
            → {compare_storage_root}/prepared/{sha}.md
```

两个实例使用不同的 `storage_root`，`prepared/` 目录自然隔离，无缓存冲突。

### 前置条件

- scrivai 升级到 `>=0.2.1`（内置 MinerU 后端支持）
- MinerU Python 包已安装（scrivai 0.2.1 的依赖自动拉取）

## 变更清单

### 1. `pyproject.toml` [MODIFY]

scrivai 依赖版本从 `>=0.2.0` 升级到 `>=0.2.1`。

### 2. `govdoc/config.py` [MODIFY]

`CompareConfig` 新增 `ocr_backend: str = "mineru"` 字段。

### 3. `govdoc.yaml` [MODIFY]

`compare:` 块新增 `ocr_backend: mineru` 配置行。

### 4. `govdoc/runtime.py` [MODIFY]

新增 `get_compare_document_store()` 工厂函数（`@lru_cache` 单例），使用 `cfg.compare.ocr_backend` 和独立的 `storage_root / "compare_prepared"` 目录。

### 5. `govdoc/compare/service.py` [MODIFY]

`_extract_pdf_paragraphs()` 中的 `get_document_store()` 替换为 `get_compare_document_store()`。

### 6. `tests/unit/test_document_store.py` [MODIFY]

新增测试：两个不同 `ocr_backend` 的 DocumentStore 实例缓存互不干扰。

## 不做的事情

- 不改 DocumentStore 类本身
- 不改主管道（审查）的 OCR 后端配置
- 不改 `_extract_pdf_paragraphs` 的超时/并发逻辑
- 不新增 MinerU 特定的环境变量

## 被否决的方案

### 方案 B：DocumentStore 缓存 key 加入后端标识

缓存 key 从 `{sha}.md` → `{sha}_{backend}.md`。修改了共享代码（DocumentStore 类），增加了测试表面积，且两个独立实例根本不需要共享 `prepared/` 目录。

### 方案 C：对比模块直接调 scrivai.to_markdown

绕过 DocumentStore 直接调用。丢失 SHA256 缓存（同一 PDF 每次重新转换），且与主管道的职责组织不一致。

## 验证计划

| 步骤 | 命令 / 方法 | 预期 |
|------|------------|------|
| 依赖升级 | `pip install -e .` + `pip show scrivai` | 版本 ≥ 0.2.1 |
| 配置加载 | `python -c "from govdoc.runtime import get_config; print(get_config().compare.ocr_backend)"` | 输出 `mineru` |
| 单元测试 | `pytest tests/unit/ -v` | 全部通过 |
| 端到端 | 上传 2 份 PDF 执行对比 | MinerU 成功转换 |
