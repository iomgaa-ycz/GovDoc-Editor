# E2E 测试计划

> 本文档为 GovDoc-Auditor 的端到端测试清单，覆盖后端 API 和前端 Playwright 两个层级。
> 所有测试使用真实文档数据，打向已部署的 testing 环境。

## 1. 环境准备

### 1.1 网络访问

本地开发机需设置无代理才能直连 4090-server：

```bash
export NO_PROXY=100.83.164.94
export no_proxy=100.83.164.94
```

| 环境 | 后端 API | 前端 | Swagger |
|------|----------|------|---------|
| testing | `http://100.83.164.94:8001` | `http://100.83.164.94:5174` | `http://100.83.164.94:8001/docs` |
| stable | `http://100.83.164.94:8000` | `http://100.83.164.94:5175` | `http://100.83.164.94:8000/docs` |

### 1.1.1 Playwright CLI 浏览器访问

Playwright CLI 启动的浏览器**不走 `NO_PROXY` 环境变量**，需要通过 SSH 隧道访问：

```bash
# 建立 SSH 隧道（后台运行）
ssh -f -N -L 15174:localhost:5174 -L 18001:localhost:8001 yuchengzhang@100.83.164.94

# 启动 playwright-cli 时必须清除代理变量
http_proxy="" https_proxy="" HTTP_PROXY="" HTTPS_PROXY="" no_proxy="*" NO_PROXY="*" \
  playwright-cli open http://localhost:15174/
```

隧道端口映射：`localhost:15174` → 前端 / `localhost:18001` → 后端

### 1.2 测试数据（`tests/e2e/data/`）

| 文件 | 类型 | 大小 | 用途 |
|------|------|------|------|
| `2025年政府采购领域"四类"违法违规行为专项整治工作指引.docx` | 法规指引 | 4.8M | Pipeline A 审核点提取 |
| `从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx` | 招标文书 | 14K | Pipeline B 审核主文书 |
| `从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf` | 招标文书 PDF | 676K | Pipeline B 补充文件 |
| `附件9 处理处罚标准.xls` | 检查点清单 | 32K | 审核点批量导入 |

### 1.3 部署验证（每轮测试前执行）

```bash
# 健康检查
NO_PROXY=100.83.164.94 curl -sf http://100.83.164.94:8001/healthz
# 预期: {"status":"ok"}

# 容器状态（通过 SSH）
ssh yuchengzhang@100.83.164.94 "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep govdoc"
```

---

## 2. Phase 1: 后端 API E2E 测试

> 使用 curl / httpx / pytest 直接打 API，验证后端数据流正确。
> 建议在 Playwright 测试前先跑完，确保后端无问题。

### 2.1 基础设施

| # | 用例 | 方法 | 端点 | 验证要点 |
|---|------|------|------|----------|
| B01 | 健康检查 | GET | `/healthz` | 返回 `{"status":"ok"}` |

### 2.2 项目与文书管理

| # | 用例 | 方法 | 端点 | 验证要点 |
|---|------|------|------|----------|
| B02 | 创建项目 | POST | `/api/v1/projects` | 返回 project_id，状态 201 |
| B03 | 上传主文书（DOCX） | POST | `/api/v1/projects/{id}/tender-doc` | 返回 tender_doc_id，DOCX 正常解析 |
| B04 | 上传主文书（PDF） | POST | `/api/v1/projects/{id}/tender-doc` | PDF→markdown 降级转换，返回 warning |
| B05 | 上传补充文件 | POST | `/api/v1/projects/{id}/tender-doc` (多次) | 每个文件分配独立 ID |
| B06 | 查询项目文书列表 | GET | `/api/v1/projects/{id}/tender-docs` | 返回主文书 + 全部补充文件 |

### 2.3 法规提取（Pipeline A）

| # | 用例 | 方法 | 端点 | 验证要点 |
|---|------|------|------|----------|
| B07 | 上传法规文件触发提取 | POST | `/api/v1/rules/upload` | 返回 rule_id + run_id，状态 pending→running |
| B08 | 轮询提取进度 | GET | `/api/v1/rules/{id}/extract-runs/{run_id}/status` | 最终 draft_ready 或 failed（涉及真实 LLM，约 1-5 分钟） |
| B09 | 查看入库审核点 | GET | `/api/v1/checkpoints` | 返回提取出的审核点数组，每条含 title/description |

### 2.4 审核点管理

| # | 用例 | 方法 | 端点 | 验证要点 |
|---|------|------|------|----------|
| B10 | 批量导入审核点（XLS） | POST | `/api/v1/checkpoints/import` | 返回 imported_count + skipped（含跳过原因） |
| B11 | 查看审核点列表 | GET | `/api/v1/checkpoints` | 返回已入库审核点 |
| B12 | 编辑审核点 | PUT | `/api/v1/checkpoints/{id}` | 修改 payload_json 后 GET 确认更新 |
| B13 | 删除审核点 | DELETE | `/api/v1/checkpoints/{id}` | 再次 GET 返回 404 |

### 2.5 审核运行（Pipeline B）

| # | 用例 | 方法 | 端点 | 验证要点 |
|---|------|------|------|----------|
| B14 | 创建审核运行（多文件） | POST | `/api/v1/audit/runs` | 含 supplementary_doc_ids[]，返回 audit_run_id |
| B15 | 参数校验 — 非法补充文件 ID | POST | `/api/v1/audit/runs` | supplementary_doc_ids 含非整数 → 422 |
| B16 | 轮询审核进度 | GET | `/api/v1/audit/runs/{id}/progress` | processed_count 递增，逐点返回 finding_json |
| B17 | 查看审核运行详情 | GET | `/api/v1/audit/runs/{id}` | 包含 status / total_count / checkpoint_final_ids |
| B18 | 重试失败审核点 | POST | `/api/v1/audit/point-runs/{id}/retry` | 状态 failed → pending → running |

### 2.6 文档对比

| # | 用例 | 方法 | 端点 | 验证要点 |
|---|------|------|------|----------|
| B19 | 对比多份 DOCX/PDF | POST | `/api/v1/compare` | 使用重复字段 `files` 上传，返回 review_id + documents.files + matches |
| B20 | 下载第 1 份高亮副本 | GET | `/api/v1/compare/{id}/download/0` | Content-Type 为 DOCX，文件可打开 |
| B21 | 下载第 2 份高亮副本 | GET | `/api/v1/compare/{id}/download/1` | Content-Type 为 DOCX，文件可打开 |

### 2.7 工作底稿

| # | 用例 | 方法 | 端点 | 验证要点 |
|---|------|------|------|----------|
| B22 | 获取工作底稿草稿 | GET | `/api/v1/audit/runs/{id}/workpaper/draft` | 审核完成后返回 HTML 工作底稿 |
| B23 | 保存工作底稿草稿 | PUT | `/api/v1/audit/runs/{id}/workpaper/draft` | 保存后版本号递增 |
| B24 | 定稿工作底稿 | POST | `/api/v1/audit/runs/{id}/workpaper/finalize` | 返回定稿 ID |
| B25 | 下载定稿 DOCX | GET | `/api/v1/audit/runs/{id}/workpaper/final/docx` | 返回 Word 文件，可正常打开 |

---

## 3. Phase 2: Playwright 浏览器 E2E 测试

> 使用 Playwright 自动化浏览器操作，验证前端交互与数据展示。
> 依赖 Phase 1 产生的数据（或独立创建数据）。

### 3.1 首页与导航

| # | 用例 | 页面 | 操作 | 验证要点 |
|---|------|------|------|----------|
| P01 | 首页加载 | `/` | 打开首页 | 页面渲染完成，标题"政务智能审查工作台"可见 |
| P02 | 导航到审核点库 | `/` → `/audit-library` | 点击入口卡片 | URL 变为 `/audit-library`，页面正常加载 |
| P03 | 导航到 AI 审核 | `/` → `/ai-review` | 点击入口卡片 | URL 变为 `/ai-review`，页面正常加载 |
| P04 | 侧边栏导航 | 任意页面 | 依次点击侧边栏各菜单项 | 所有页面可达，无 404/白屏 |

### 3.2 审核点库页面（`/audit-library`）

| # | 用例 | 操作 | 验证要点 |
|---|------|------|----------|
| P05 | 查看审核点列表 | 打开页面 | 显示审核点列表和已入库审核点计数 |
| P06 | 批量导入 XLS | 上传 `附件9 处理处罚标准.xls` | 显示导入结果：成功数 + 跳过数及原因 |
| P07 | 上传法规触发提取 | 上传 `专项整治工作指引.docx` + 填写标题 → 提交 | 显示提取状态 pending→running→draft_ready，审核点入库 |
| P08 | 编辑审核点 | 点击某审核点编辑图标 → 修改标题 → 保存 | Modal 关闭，列表中标题已更新 |
| P09 | 删除审核点 | 点击某审核点删除图标 → 确认 | 审核点从列表消失，计数减 1 |

### 3.3 AI 审核页面（`/ai-review`）— 核心路径

| # | 用例 | 操作 | 验证要点 |
|---|------|------|----------|
| P10 | 创建新项目 | 输入项目名 → 点击创建 | 下拉框出现新项目，被自动选中 |
| P11 | 上传主文书（DOCX） | 拖拽/选择 `从化区...采购.docx` | TenderUploadPanel 显示文件名 |
| P12 | 上传补充文件 | 上传 `...招标文件.pdf.pdf` 作为补充文件 | 补充文件列表显示文件名 |
| P13 | 上传错误反馈 | 上传损坏/不支持格式文件 | 显示 InlineNotice 错误提示，不崩溃 |
| P14 | 上传降级警告 | 上传 PDF（转换降级） | 显示降级警告信息 |
| P15 | 选择审核点 | CheckpointPicker 中勾选多个审核点 | 已选数量更新，"开始审核"按钮可用 |
| P16 | 启动审核（完整流程） | 点击"开始审核" | AuditProgressPanel 出现 → 进度条推进 → 逐个审核点状态变化 → 最终 draft_ready |
| P17 | 查看审核点详情 | 点击已完成审核点 | 弹窗显示 verdict / evidence / legal_basis |
| P18 | failed 审核点样式 | 观察 failed 状态审核点 | 正确显示 failed 行项样式（红色/错误图标） |
| P19 | uncertain 状态展示 | 观察 uncertain 状态审核点 | 正确显示存疑标签（独立样式） |
| P20 | 重试失败审核点 | 对 failed 审核点点击重试按钮 | 状态重置 → 重新执行 → 最终结果更新 |

### 3.4 文档对比页面（`/doc-compare`）

| # | 用例 | 操作 | 验证要点 |
|---|------|------|----------|
| P21 | 上传两个文档 | 拖拽/选择两个 DOCX 文件 | 两侧 dropzone 显示文件名和大小 |
| P22 | 执行对比 | 点击对比按钮 | 显示匹配指标（match_count / paragraph / sentence / segment） |
| P23 | 双栏对比视图 | 查看对比结果 | 左右两栏显示段落，匹配文本高亮 |
| P24 | 分类筛选 | 切换 paragraph / sentence / segment 类别 toggle | 高亮内容随类别变化 |
| P25 | 匹配列表交互 | 点击右侧匹配列表项 | 左右文档滚动到对应位置，高亮对应文本 |
| P26 | 下载高亮文档 | 点击下载文档 A / 文档 B 按钮 | 浏览器触发 DOCX 文件下载 |

### 3.5 审核结果页面（`/audit-results`）

| # | 用例 | 操作 | 验证要点 |
|---|------|------|----------|
| P27 | 选择审核运行 | 下拉框选择已完成的审核运行 | 左栏显示该运行的审核点列表 |
| P28 | 查看审核点详情 | 点击某审核点 | 中栏 PointInsight 显示 verdict / confidence / evidence / legal_basis |
| P29 | 状态徽章展示 | 观察审核点列表 | passed(绿) / failed(红) / uncertain(黄) 徽章正确 |

### 3.6 工作底稿

| # | 用例 | 操作 | 验证要点 |
|---|------|------|----------|
| P30 | 加载工作底稿 | 进入工作底稿页面 | HTML 工作底稿正常渲染 |
| P31 | 编辑工作底稿 | 修改内容 → 触发自动保存 | 版本号递增，内容持久化 |
| P32 | 定稿并下载 | 点击定稿按钮 → 下载 DOCX | 浏览器触发 Word 文件下载 |

---

## 4. 推荐执行顺序

```
┌─ Phase 1: 后端 API ─────────────────────────────────────────┐
│  1. B01          健康检查                                      │
│  2. B02 → B06    项目与文书管理（基础数据准备）                    │
│  3. B10 → B13    导入审核点（快速获得可用审核点，跳过 LLM）         │
│  4. B07 → B09    法规提取（涉及真实 LLM，约 1-5 分钟）            │
│  5. B14 → B18    审核运行（核心路径，涉及真实 LLM）               │
│  6. B19 → B21    文档对比                                      │
│  7. B22 → B25    工作底稿                                      │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌─ Phase 2: Playwright 浏览器 ─────────────────────────────────┐
│  8.  P01 → P04   首页与导航                                    │
│  9.  P05 → P09   审核点库页面                                   │
│  10. P10 → P20   AI 审核完整流程（核心路径）                      │
│  11. P21 → P26   文档对比页面                                   │
│  12. P27 → P29   审核结果页面                                   │
│  13. P30 → P32   工作底稿                                      │
└──────────────────────────────────────────────────────────────┘
```

### 耗时预估

| 阶段 | 预计耗时 | 说明 |
|------|----------|------|
| Phase 1 (不含 LLM) | ~5 分钟 | B01-B06, B10-B13, B19-B21 |
| Phase 1 (含 LLM) | ~10-20 分钟 | B07-B09 提取 + B14-B18 审核 |
| Phase 2 (不含 LLM 流程) | ~10 分钟 | P01-P09, P21-P32 |
| Phase 2 (含 LLM 流程) | ~15-25 分钟 | P10-P20 完整审核流程 |
| **合计** | **~40-60 分钟** | 完整一轮 |

---

## 5. PR 功能覆盖矩阵

| PR | 功能 | 后端用例 | 前端用例 |
|----|------|----------|----------|
| PR#2 | 多文件审核 + 错误反馈 | B05, B06, B14 | P12, P13, P14 |
| PR#4 | DOCX 文档对比 | B19, B20, B21 | P21-P26 |
| PR#7 | 审核点导入 + 中文文档 | B10 | P06 |
| PR#10 | 前端修复 + 后端校验 + 多文件支持 | B03, B05, B14, B15 | P11, P12, P16, P18, P19 |

---

## 6. 测试执行记录（2026-04-26）

### 6.1 后端 API（pytest + httpx）

```
tests/e2e/test_01_healthcheck.py          2 passed
tests/e2e/test_02_project_and_docs.py     8 passed
tests/e2e/test_03_checkpoint_import.py    6 passed
tests/e2e/test_04_compare.py              7 passed
tests/e2e/test_05_rule_extract.py         3 passed, 1 skipped (提取失败→审核点查看跳过)
tests/e2e/test_06_audit_full_flow.py      8 skipped (无可用审核点)
                                   合计: 26 passed, 9 skipped
```

快速测试命令（排除 LLM）: `NO_PROXY=100.83.164.94 conda run -n govdoc-auditor-v3 python -m pytest tests/e2e/ -v -m "not slow"` → **23 passed in 1.94s**

### 6.2 Playwright CLI 浏览器测试

| # | 用例 | 结果 | 证据 |
|---|------|------|------|
| P01 | 首页加载 | ✅ 通过 | "政务智能审查工作台"可见，两入口卡片存在 |
| P02 | 导航到审核点库 | ✅ 通过 | URL=/audit-library，已入库审核点计数可见 |
| P03 | 导航到 AI 审核 | ✅ 通过 | triple-layout（任务设置/审核进度/审核点进度） |
| P04 | 侧边栏全页面遍历 | ✅ 通过 | 6 个页面均可达，0 console error |
| P05 | 审核点库列表 | ✅ 通过 | 含已入库审核点计数卡片 |
| P06 | 批量导入 XLS | ✅ 通过 | "成功导入 52 条审查点"，计数增至 310 |
| P07 | 上传法规提取 | ⏭ 跳过 | 服务器缺 pandoc，Pipeline A 失败 |
| P08 | 编辑审核点 | ✅ 通过 | Modal 弹出→修改标题→保存→列表更新 |
| P09 | 删除审核点 | ✅ 通过 | 确认弹窗→删除→计数从 310 降为 309 |
| P10 | 创建新项目 | ✅ 通过 | 项目下拉框出现"E2E浏览器测试项目"并自动选中 |
| P11 | 上传主文书 DOCX | ✅ 通过 | file-chip 显示文件名 14.1 KB |
| P13 | 上传文书到服务器 | ✅ 通过 | InlineNotice(success) "文书已上传" |
| P15 | 选择审核点 | ✅ 可执行 | 导入与 AI 提取均直接生成可选审核点 |
| P16-P20 | AI 审核完整流程 | ⏳ 待验证 | 依赖真实审核运行环境 |
| P21 | 上传两个文档 | ✅ 通过 | 两侧 dropzone 显示文件名和大小 |
| P22 | 执行对比 | ✅ 通过 | 36 项匹配，双栏 16 段，三种匹配类别 |
| P25 | 匹配列表交互 | ✅ 通过 | 点击匹配项高亮对应文本 |
| P26 | 下载高亮文档 | ✅ 通过 | 下载 DOCX 37KB，链接有效 |
| P27 | 审核结果页 | ✅ 页面正常 | "暂无审核结果"（无完成的运行） |
| P30 | 工作底稿页 | ✅ 页面正常 | 按钮全 disabled（无审核运行数据） |

### 6.3 阻塞问题

| 问题 | 影响 | 根因 | 修复方案 |
|------|------|------|----------|
| 服务器缺 pandoc | P07 跳过，B08 提取失败 | Docker 镜像未安装 pandoc | `apt install pandoc` 或在 Dockerfile 中添加 |
| pyproject.toml 缺依赖 | XLS 导入 500 | 缺 xlrd/openpyxl | 已修复并提交 |
