---
type: finding
node_id: finding:multi-file-audit-investigation
title: 多文件审核调查报告
date: 2026-05-13
migrated_from: docs/multi-file-audit-investigation-2026-04-26.md
tags: ["migrated"]
---

# 多文件审核调查报告

> 日期：2026-04-26
> 审计运行 ID：`8852938a8382493b97401cbcdd82cd03`（项目"测试多文件2"）
> 审核点：cp_01（地域性歧视条款）、cp_05（信息公开与合同履行）

## 1. 调查背景

在 `codex/qmd-search-cli` 分支完成 qmd-search CLI 接入后，执行了首次多文件审核（1 主文书 + 3 份补充文件）。本文档记录对多文件数据流的端到端检查结果。

### 受审文档

| 文件 | 角色 | 路径 | 行数 |
|------|------|------|------|
| 从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件 | 主文书 (tender.md) | data/tender.md | ~6000 |
| 分项报价表.pdf | 补充 (supp_0.md) | data/supp_0.md | 18 |
| 江西珉图医药有限公司.pdf | 补充 (supp_1.md) | data/supp_1.md | 5153 |
| 开标一览表.pdf | 补充 (supp_2.md) | data/supp_2.md | 8 |

## 2. 基础架构层检查：通过

| 检查项 | 结果 |
|--------|------|
| workspace `data/` 包含 tender.md + 3 个 supp_*.md | 4 个文件齐全 |
| `documents.json` 正确标记 source_type | main + 3 × supplementary |
| `meta.json` 注入 `GOVDOC_TENDER_COLLECTION` + `GOVDOC_DB_PATH` | 通过 |
| qmd collection 索引了全部 4 个文档 | 4 个 doc_id 均可检索到 |
| qmd-search 返回混合结果（主文书 + 补充文件） | 通过 |

## 3. Agent 行为层检查：有问题

### 3.1 核心发现：Agent 从未直接 Read 任何 supp 文件

| 阶段 | cp_01 Read 目标 | cp_05 Read 目标 |
|------|----------------|----------------|
| plan | checkpoints.json, documents.json, tender.md | checkpoints.json, documents.json |
| execute | plan.json, checkpoints.json, documents.json | plan.json, checkpoints.json, documents.json, tender.md |

两个审核点的 plan + execute 合计约 10 次 Read，目标全是主文书和元数据文件，**从未出现 supp_0.md / supp_1.md / supp_2.md**。

### 3.2 Grep 搜索也只覆盖主文书

cp_05 execute 阶段共执行 10 次 Grep，path 全部指向 `tender.md`，没有一次搜索 `supp_*.md` 或整个 `data/` 目录。

### 3.3 qmd-search 确实返回了补充文件内容

cp_05 execute 阶段 5 次 qmd-search 的命中来源：

| 轮次 | query | 命中 doc_id |
|------|-------|-------------|
| Turn 9 | 合同签订时限 中标通知书 二十日 三十日 | `ce329bc65215`（主）+ `47bc07c89f3a`（supp_1） |
| Turn 11 | 合同公告 备案 信息公告发布媒体 | `ce329bc65215`（主） |
| Turn 12 | 质疑答复 投诉处理 验收程序 代理服务费 | `ce329bc65215`（主）+ `47bc07c89f3a`（supp_1） |
| Turn 19 | 合同签订 自中标通知书发出之日起 | `ce329bc65215`（主）+ `47bc07c89f3a`（supp_1） |
| Turn 20 | 投诉 财政局 投诉处理 监督管理部门 | `ce329bc65215`（主）+ `47bc07c89f3a`（supp_1） |

但返回的 supp_1 chunk 分数极低（0.031–0.033），且内容为乱码重复文本（PDF 解析残留），agent 判断"无实际价值"后直接跳过。

## 4. 根因分析

### 4.1 Prompt 设计缺陷

当前 `pes_overrides.py` 中 plan/execute 阶段的 prompt 逻辑：

```
如果 qmd 不可用 → Read tender.md + 所有 supp_*.md + Grep 搜索
如果 qmd 可用   → 依赖 qmd 返回的 chunk（不再 Read supp 文件）
```

这条分支导致：当 qmd 正常工作时，agent 不会主动去 Read 完整的补充文件。而 qmd 返回的 chunk 只是几百字的片段，无法覆盖 supp_1（5153 行完整投标材料）中的全部内容。

### 4.2 Agent 查询视角单一

agent 的所有 qmd query 都是围绕**主文书的程序性关键词**（合同签订、质疑答复、投诉、代理服务费），从未使用"报价"、"金额"、"投标总价"、"供应商名称"等关键词——而这些才是补充文件（分项报价表、开标一览表）里的独特内容。

agent 虽然读了 `documents.json`（知道有 3 份补充文件），但没有根据补充文件的实际内容调整搜索策略。

### 4.3 qmd 对补充文件的检索质量差

supp_1（江西珉图投标文件）的 chunk 在 qmd 中出现乱码重复：

```
"的行业及个人手中在银行开立、账户或向所涉及的行业及个人手中在银行开立..."
```

这是 PDF 解析后某处残留文本被切成多个 chunk，检索分数 0.031–0.033，对 agent 来说几乎没有参考价值。

## 5. 对审核质量的影响

| 审核点 | 判定 | 补充文件利用情况 | 影响 |
|--------|------|-----------------|------|
| cp_01 地域性歧视 | 不合规 | 未利用（主文书证据已充分） | 低 |
| cp_05 信息公开与合同履行 | 存疑 | **未利用**（分项报价表、开标一览表、投标文件中的报价/供应商信息完全未参考） | **中** |

cp_05 的影响更严重：
- **分项报价表**（supp_0）：包含每项设备的品牌、单价、数量、总价，可用于价格合理性审查
- **开标一览表**（supp_2）：投标总报价 7,288,800 元，与合同金额是否一致需要交叉验证
- **江西珉图投标文件**（supp_1）：完整投标材料（投标函、商务响应、履约计划等），可用于供应商资质、合同条款响应一致性审查

这些内容在当前审核中完全未被参考。

## 6. 建议修复方向

### 6.1 Prompt 层面（`pes_overrides.py`）

**plan 阶段**：在 qmd 检索步骤之后，增加强制遍历补充文件的步骤：

```
3. Read ../data/documents.json
4. 如果存在 source_type=supplementary 的文件，Read 所有 ../data/supp_*.md
5. 结合 qmd 检索结果和补充文件内容，综合制定审核策略
```

**execute 阶段**：在"Read 命中段落"之后，增加交叉验证步骤：

```
5. 如果审核涉及报价、供应商资质、合同条款等需要交叉验证的内容，
   Read 相关的 ../data/supp_*.md 进行对比验证
```

### 6.2 补充文件的 qmd 检索质量

supp_1 的乱码问题来自 PDF 解析环节（`govdoc/parsers/tender_doc.py`），不在本次 qmd-search CLI 的范围内，但需后续排查 PDF → Markdown 的解析质量。

## 7. 附录：审核结果摘要

### cp_01 采购文件设置地域性与行业性歧视条款

- **判定**：不合规
- **核心发现**：评审因素中「综合信用评价(5.0分)」采用「广州公共资源交易信用评价」体系，未注册的外地供应商仅得基准分 93.4 分，构成地域性歧视
- **证据来源**：主文书评审因素章节

### cp_05 信息公开与合同履行合规审查

- **判定**：存疑
- **核心发现**：合同签订时限前后表述不一致（20日 vs 30日）、质疑答复条款未明确承诺7工作日答复、代理服务费引用已废止文件
- **证据来源**：主文书（补充文件完全未被参考）
