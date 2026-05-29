---
type: plan
node_id: plan:uncategorized-virtual-library-plan
title: "虚拟「未分类」库 + 提取后自动定位 实现计划"
date: 2026-05-29
---

# 虚拟「未分类」库 + 提取后自动定位 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 提取的「孤儿审核点」（不属于任何真实库）在审核点库页面有一个稳定的虚拟「未分类」入口可见，并在提取完成后让用户落到该入口看到新点。

**Architecture:** 后端 `GET /api/v1/checkpoints` 为每条审核点附加 `library_count`（归属真实库数量，一次 group-by 查询）。前端把「未分类」做成与现有「全部审核点」同类的虚拟侧栏视图（`selectedLibraryId === "uncategorized"`），从全量 `checkpoints` 计算 `library_count === 0` 的点，**不写 `CheckpointLibraryItem`、不建库、不写迁移**。一条点被加入任意真实库后 `library_count > 0`，下次刷新自动从「未分类」消失。

**Tech Stack:** 后端 FastAPI + SQLModel + SQLite（pytest）；前端 React + TypeScript（vitest）；E2E `@playwright/cli`。

**关联 design:** `research-wiki/designs/uncategorized-virtual-library.md`

---

## 文件结构

| 文件 | 责任 | 改动 |
|---|---|---|
| `govdoc/api/routes/checkpoints.py` | 列表序列化附 `library_count` | MODIFY |
| `tests/unit/test_checkpoints_route.py` | `library_count` 单测 | MODIFY |
| `frontend/src/types/ui.ts` | `CheckpointItem` 加字段 | MODIFY |
| `frontend/src/pages/AuditLibraryPage.tsx` | 虚拟「未分类」视图 + 只读守卫 + 自动定位 | MODIFY |
| `frontend/src/pages/audit-library-utils.ts` | 纯函数 `countUncategorized`（DRY，供侧栏与测试） | CREATE |
| `frontend/src/pages/audit-library-utils.test.ts` | 纯函数 vitest 单测 | CREATE |
| `frontend/e2e/audit-AL8-ai-extract.js` | E2E 增「未分类」断言 | MODIFY |

---

## Task 1: 后端 — `GET /checkpoints` 附加 `library_count`

**Files:**
- Modify: `govdoc/api/routes/checkpoints.py:29-37`（`_serialize_final`）、`:59-66`（`list_checkpoints`）、`:12`（imports）
- Test: `tests/unit/test_checkpoints_route.py`（新增到 `TestListCheckpoints`）

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_checkpoints_route.py` 的 `class TestListCheckpoints` 内追加：

```python
    def test_library_count_reflects_membership(self, client, engine):
        """归属 1 个库的点 library_count=1；孤儿点为 0。"""
        with Session(engine) as session:
            linked = CheckpointFinal(payload_json='{"title": "已归库"}', approved_by="t")
            orphan = CheckpointFinal(payload_json='{"title": "孤儿"}', approved_by="t")
            session.add(linked)
            session.add(orphan)
            session.flush()
            lib = CheckpointLibrary(name="医疗", created_by="t")
            session.add(lib)
            session.flush()
            session.add(
                CheckpointLibraryItem(library_id=lib.id, checkpoint_final_id=linked.id, added_by="t")
            )
            session.commit()
            linked_id, orphan_id = linked.id, orphan.id

        resp = client.get("/api/v1/checkpoints")
        assert resp.status_code == 200
        counts = {row["id"]: row["library_count"] for row in resp.json()}
        assert counts[linked_id] == 1
        assert counts[orphan_id] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoints_route.py::TestListCheckpoints::test_library_count_reflects_membership -v`
Expected: FAIL，`KeyError: 'library_count'`（响应里没有该字段）。

- [ ] **Step 3: 加 import**

在 `govdoc/api/routes/checkpoints.py` 第 12 行 `from sqlmodel import Session, select` 下方新增：

```python
from sqlalchemy import func
```

- [ ] **Step 4: 改 `_serialize_final` 签名与返回**

把 `govdoc/api/routes/checkpoints.py:29-37` 替换为：

```python
def _serialize_final(
    final: CheckpointFinal, *, library_count: int = 0
) -> dict[str, str | bool | int | None]:
    return {
        "id": final.id,
        "kind": "final",
        "status": "final",
        "payload_json": final.payload_json,
        "approved_by": final.approved_by,
        "archived": final.status == "archived",
        "library_count": library_count,
    }
```

> 其余调用处（import/update 响应，约 :435 / :449 / :486）不传 `library_count`，按默认 `0` 返回；前端 `refreshAll()` 会重新拉取列表得到正确值。

- [ ] **Step 5: 改 `list_checkpoints` 计算并传入计数**

把 `govdoc/api/routes/checkpoints.py:59-66` 替换为：

```python
@router.get("")
async def list_checkpoints(include_archived: bool = False):
    with get_db_session() as session:
        finals = session.exec(select(CheckpointFinal)).all()
        visible = _filter_listed_finals(list(finals), include_archived=include_archived)
        counts = dict(
            session.exec(
                select(
                    CheckpointLibraryItem.checkpoint_final_id, func.count()
                ).group_by(CheckpointLibraryItem.checkpoint_final_id)
            ).all()
        )
        payload = [
            _serialize_final(final, library_count=counts.get(final.id, 0))
            for final in visible
        ]
        payload.sort(key=lambda item: item["id"] or "")
        return payload
```

- [ ] **Step 6: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoints_route.py -v`
Expected: 全部 PASS（含新测试与原有列表测试）。

- [ ] **Step 7: 提交**

```bash
git add govdoc/api/routes/checkpoints.py tests/unit/test_checkpoints_route.py
git commit -m "feat(api): checkpoints 列表附加 library_count"
```

---

## Task 2: 前端类型 — `CheckpointItem` 加 `library_count`

**Files:**
- Modify: `frontend/src/types/ui.ts:54-61`

- [ ] **Step 1: 加字段**

把 `frontend/src/types/ui.ts:54-61` 的 `CheckpointItem` 改为：

```typescript
export interface CheckpointItem {
  id: string;
  kind: "final";
  status: string;
  payload_json: string; // JSON-encoded GovCheckpointPayload
  approved_by: string | null;
  archived?: boolean;
  library_count?: number; // 归属真实库数量；缺失时按 0（未分类）处理
}
```

- [ ] **Step 2: 类型检查通过**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新增类型错误。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/types/ui.ts
git commit -m "feat(web): CheckpointItem 增加 library_count 字段"
```

---

## Task 3: 前端纯函数 — `countUncategorized`（DRY + 可测）

**Files:**
- Create: `frontend/src/pages/audit-library-utils.ts`
- Test: `frontend/src/pages/audit-library-utils.test.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/src/pages/audit-library-utils.test.ts`：

```typescript
import { describe, expect, it } from "vitest";
import { countUncategorized, isUncategorized } from "./audit-library-utils";
import type { CheckpointItem } from "@/types/ui";

function cp(id: string, library_count?: number): CheckpointItem {
  return { id, kind: "final", status: "final", payload_json: "{}", approved_by: null, library_count };
}

describe("audit-library-utils", () => {
  it("library_count 为 0 或缺失视为未分类", () => {
    expect(isUncategorized(cp("a", 0))).toBe(true);
    expect(isUncategorized(cp("b"))).toBe(true);
    expect(isUncategorized(cp("c", 2))).toBe(false);
  });

  it("countUncategorized 统计孤儿点数量", () => {
    expect(countUncategorized([cp("a", 0), cp("b"), cp("c", 1)])).toBe(2);
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/pages/audit-library-utils.test.ts`
Expected: FAIL，模块 `./audit-library-utils` 不存在。

- [ ] **Step 3: 写纯函数实现**

新建 `frontend/src/pages/audit-library-utils.ts`：

```typescript
import type { CheckpointItem } from "@/types/ui";

/** 虚拟「未分类」库的保留 selectedLibraryId。 */
export const UNCATEGORIZED_ID = "uncategorized";

/** 一条审核点是否未归任何真实库（library_count 缺失按 0 处理）。 */
export function isUncategorized(item: CheckpointItem): boolean {
  return (item.library_count ?? 0) === 0;
}

/** 统计未分类（孤儿）审核点数量。 */
export function countUncategorized(checkpoints: CheckpointItem[]): number {
  return checkpoints.filter(isUncategorized).length;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/pages/audit-library-utils.test.ts`
Expected: PASS（2 个用例）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/audit-library-utils.ts frontend/src/pages/audit-library-utils.test.ts
git commit -m "feat(web): 新增未分类判定纯函数 audit-library-utils"
```

---

## Task 4: 前端页面 — 虚拟「未分类」侧栏 + 行过滤 + 只读守卫

**Files:**
- Modify: `frontend/src/pages/AuditLibraryPage.tsx`（imports、`loadSelectedLibrary` :163、`rows` :181、`removeSelectedFromCurrentLibrary` :346、侧栏 :565、标题 :605、动作守卫 :622/:627/:632）

- [ ] **Step 1: 引入纯函数与常量**

在 `AuditLibraryPage.tsx` 顶部 import 区（紧随现有 import）新增：

```typescript
import { UNCATEGORIZED_ID, countUncategorized, isUncategorized } from "./audit-library-utils";
```

- [ ] **Step 2: `loadSelectedLibrary` 把未分类按虚拟视图处理**

把 `AuditLibraryPage.tsx:163-167` 的判断改为：

```typescript
  async function loadSelectedLibrary(id = selectedLibraryId) {
    if (id === "all" || id === UNCATEGORIZED_ID) {
      setLibraryDetail(null);
      return;
    }
```

- [ ] **Step 3: `rows` 增加未分类分支**

在 `AuditLibraryPage.tsx:181` 的 `rows` useMemo 内、`if (selectedLibraryId === "all") {` 分支之后新增：

```typescript
    if (selectedLibraryId === UNCATEGORIZED_ID) {
      return parsed
        .filter(({ item }) => isUncategorized(item))
        .map(({ item, payload }) => ({
          key: item.id,
          checkpointFinalId: item.id,
          item,
          payload,
          deleted: false,
        }));
    }
```

- [ ] **Step 4: `removeSelectedFromCurrentLibrary` 守卫加未分类**

把 `AuditLibraryPage.tsx:347` 改为：

```typescript
    if (selectedLibraryId === "all" || selectedLibraryId === UNCATEGORIZED_ID || selectedIds.length === 0) return;
```

- [ ] **Step 5: 计算未分类数量（供侧栏）**

在 `AuditLibraryPage.tsx:160`（`const parsed = ...` 之后）新增：

```typescript
  const uncategorizedCount = useMemo(() => countUncategorized(checkpoints), [checkpoints]);
```

- [ ] **Step 6: 侧栏插入「未分类」虚拟项**

在 `AuditLibraryPage.tsx:565`（「全部审核点」按钮的 `</button>` 之后、`<div className="space-y-1">` 库列表之前）插入：

```tsx
            <button
              className={cn(
                "flex w-full items-center justify-between rounded-btn px-3 py-2 text-left text-sm",
                selectedLibraryId === UNCATEGORIZED_ID ? "bg-accent text-white" : "bg-surface hover:bg-gray-200",
              )}
              onClick={() => setSelectedLibraryId(UNCATEGORIZED_ID)}
            >
              <span className="flex items-center gap-2"><Folder className="h-4 w-4" /> 未分类</span>
              <span>{uncategorizedCount}</span>
            </button>
```

- [ ] **Step 7: 标题/副标题支持未分类**

把 `AuditLibraryPage.tsx:605-612` 的 `<h2>` 与 `<p>` 改为：

```tsx
                <h2 className="text-lg font-semibold">
                  {selectedLibraryId === "all"
                    ? "全部审核点"
                    : selectedLibraryId === UNCATEGORIZED_ID
                      ? "未分类"
                      : activeLibrary?.name ?? "审核点库"}
                </h2>
                <p className="text-sm text-text-muted">
                  {selectedLibraryId === "all"
                    ? `已收录 ${checkpoints.length} 个审查要点`
                    : selectedLibraryId === UNCATEGORIZED_ID
                      ? `${uncategorizedCount} 个未归库审查要点`
                      : `已收录 ${activeLibrary?.checkpoint_count ?? 0} 个审查要点`}
                </p>
```

- [ ] **Step 8: 对未分类禁用「移出/编辑/删除库」**

在 `AuditLibraryPage.tsx:161`（`const activeLibrary = ...` 之后）新增虚拟库判定：

```typescript
  const isVirtualLibrary = selectedLibraryId === "all" || selectedLibraryId === UNCATEGORIZED_ID;
```

把 `:622`、`:627`、`:632` 三处 `{selectedLibraryId !== "all" && (` 全部改为：

```tsx
                {!isVirtualLibrary && (
```

> 「加入库」按钮（`:619`）对未分类**保持可用**——选中孤儿点加入真实库正是让它脱离未分类的正常操作。

- [ ] **Step 9: 类型检查与构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误。

- [ ] **Step 10: 提交**

```bash
git add frontend/src/pages/AuditLibraryPage.tsx
git commit -m "feat(web): 审核点库新增虚拟「未分类」视图（只读）"
```

---

## Task 5: 前端 — 提取完成后自动定位到「未分类」

**Files:**
- Modify: `frontend/src/pages/AuditLibraryPage.tsx`（在 `:176` 现有 useEffect 附近新增一个 effect）

- [ ] **Step 1: 新增 effect 监听提取完成**

在 `AuditLibraryPage.tsx:179`（现有 `useEffect(... [selectedLibraryId])` 之后）新增：

```typescript
  // 提取完成（draft_ready）后定位到「未分类」，用户点「返回列表」即见新提取的点。
  useEffect(() => {
    if (extractStatus === "draft_ready") {
      setSelectedLibraryId(UNCATEGORIZED_ID);
    }
  }, [extractStatus]);
```

> 不改 `mode`：保留「提取完成」成功页；`refreshAll()`（context 内已在 `draft_ready` 调用）更新 `checkpoints` 后，用户点击「返回列表」即落在「未分类」并看到新点。`extractStatus` 已在组件 `:104` 从 context 解构，无需额外改动。

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误。

- [ ] **Step 3: 前端单测回归**

Run: `cd frontend && npm run test`
Expected: 全部 PASS（含 Task 3 新测试）。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/AuditLibraryPage.tsx
git commit -m "feat(web): 提取完成后自动定位到未分类视图"
```

---

## Task 6: E2E — `audit-AL8` 增「未分类」断言

**Files:**
- Modify: `frontend/e2e/audit-AL8-ai-extract.js`（Step 8 之后，约 :141）

- [ ] **Step 1: 在「返回列表行数增加」断言后追加「未分类」校验**

在 `frontend/e2e/audit-AL8-ai-extract.js` 第 141 行 `console.log('PASS: 返回列表成功...')` 之后插入：

```javascript
  // ── Step 9: 校验侧栏「未分类」入口出现且数量 > 0 ──
  console.log('Step 9: 校验「未分类」虚拟库');
  const uncategorized = page.getByText('未分类').first();
  if (!(await uncategorized.isVisible())) throw new Error('侧栏「未分类」入口不可见');
  await uncategorized.click();
  await page.waitForTimeout(1000);
  var uncatRows = await page.locator('table tbody tr').count();
  if (uncatRows <= 0) throw new Error('「未分类」视图为空，提取点未归入未分类');
  await page.screenshot({ path: SS + '-09-uncategorized.png', fullPage: true });
  console.log('PASS: 「未分类」可见且含 ' + uncatRows + ' 条提取点');
```

- [ ] **Step 2: 跑 E2E（testing 环境，真实大文件 + 截图）**

Run:
```bash
cd /home/iomgaa/Projects/GovDoc_Editor && bash frontend/e2e/run-tests.sh --only audit-AL8-ai-extract
```
Expected: `PASS audit-AL8-ai-extract`；截图 `frontend/e2e/screenshots/audit-AL8-09-uncategorized.png` 显示「未分类」选中且列表有提取点。

> 注：本测试 30 分钟内完成（含真实 AI 提取），用 `run_in_background` 跑并轮询日志/截图。

- [ ] **Step 3: 提交**

```bash
git add frontend/e2e/audit-AL8-ai-extract.js
git commit -m "test(e2e): audit-AL8 校验未分类虚拟库"
```

---

## Task 7: 全量回归 + 收尾

- [ ] **Step 1: 后端单测 + 契约测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit tests/contract -q`
Expected: 全绿。

- [ ] **Step 2: 后端 lint**

Run: `source activate govdoc-auditor-v3 && ruff check . --fix && ruff format .`
Expected: 无残留错误。

- [ ] **Step 3: 前端单测**

Run: `cd frontend && npm run test`
Expected: 全绿。

- [ ] **Step 4: 手动核验 testing 现状**

Run（确认存量 5 条孤儿点已自动进入「未分类」，无需迁移）：
```bash
export NO_PROXY="100.82.33.121,localhost,127.0.0.1"
curl -s http://100.82.33.121:8001/api/v1/checkpoints | python3 -c "import sys,json;d=json.load(sys.stdin);print('未分类:', sum(1 for c in d if (c.get('library_count') or 0)==0))"
```
Expected: 未分类数 > 0（含历史孤儿点）。

- [ ] **Step 5: 部署 testing 验证无误后再 stable**

按用户约定：testing 验证通过后，`bash scripts/deploy.sh --target testing` →（确认）→ `--target stable`。

---

## Self-Review

**1. Spec coverage**
- 虚拟「未分类」= 计算视图（design §3）→ Task 1（后端 library_count）+ Task 3/4（前端计算视图）✅
- 不写关联/不建库/不迁移（design §3/§7）→ 全程未触 extract_rules.py / 无 migration ✅
- 只读约束（design §5）→ Task 4 Step 8 禁用移出/编辑/删除 ✅
- 不变式（加入真实库后自动消失）→ `library_count` 实时计算 + Task 1 测试覆盖 ✅
- 提取后自动定位（design §2/§4 锦上添花）→ Task 5 ✅
- 兼容 `library_count` 缺失降级为 0（design §5）→ `isUncategorized` 的 `?? 0` + Task 3 测试 ✅
- 测试计划（design §6）→ 后端单测 Task 1 / 前端纯函数单测 Task 3 / E2E Task 6 ✅

**2. Placeholder scan**：无 TBD/TODO；每个代码步骤均含完整代码。✅

**3. Type consistency**：`UNCATEGORIZED_ID`/`isUncategorized`/`countUncategorized` 在 Task 3 定义，Task 4/5 一致引用；`library_count` 后端 dict 键与前端 `CheckpointItem` 字段名一致。✅
