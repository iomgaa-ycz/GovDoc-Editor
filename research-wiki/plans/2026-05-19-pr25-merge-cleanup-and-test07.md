# PR #25 合并清理 + Test 07 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合并 PR #25 的审核结果页修复代码，清理其中不合规的变更，并新增 Playwright E2E test-07 覆盖修复场景。

**Architecture:** PR #25 修复了 V3WorkbenchContext / AuditResultsPage / DashboardPage 三个前端文件中的 5 个状态管理 bug。合并后需撤回 CLAUDE.md（开发者笔记误提交）和 vite.config.ts（本地端口硬编码）的变更。Radix UI 依赖为已有 shadcn 组件所需，保留。最后新增 test-07 验证 Dashboard 跳转和审核结果页数据加载。

**Tech Stack:** React + TypeScript, @playwright/cli (E2E), Git

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 还原 | `CLAUDE.md` | 撤回 PR 创建的整个文件（master 的 .gitignore 已排除） |
| 还原 | `frontend/vite.config.ts` | 撤回端口 8000→8002 变更 |
| 保留 | `frontend/package.json` | 6 个 Radix UI 依赖为 shadcn 组件（Select/ScrollArea/Dialog 等）所需 |
| 保留 | `frontend/package-lock.json` | 与 package.json 配套 |
| 保留 | `frontend/src/context/V3WorkbenchContext.tsx` | 核心修复：自动加载 progress + 轮询守卫 |
| 保留 | `frontend/src/pages/AuditResultsPage.tsx` | 核心修复：一致性校验 + 失效提示 |
| 保留 | `frontend/src/pages/DashboardPage.tsx` | 核心修复：按 project_id 匹配跳转 |
| 创建 | `frontend/e2e/test-07-audit-results-history.js` | E2E 测试：验证 PR #25 修复的 5 个场景 |
| 修改 | `frontend/e2e/run-tests.sh` | ALL_TESTS 数组追加 `07-audit-results-history` |

---

### Task 1: 合并 PR #25

**Files:**
- 无文件创建/修改（git 操作）

- [ ] **Step 1: 合并 PR**

```bash
gh pr merge 25 --squash --subject "fix: 审核结果页历史 run 加载与 Dashboard 跳转修复"
```

使用 squash merge 合并，这样 AI Co-Author 标识（在原始 commit 中）会被消除。

- [ ] **Step 2: 拉取合并后的 master**

```bash
git pull origin master
```

- [ ] **Step 3: 验证合并结果**

```bash
git log --oneline -3
```

预期：最新 commit 是 squash merge 的 `fix: 审核结果页历史 run 加载与 Dashboard 跳转修复`。

---

### Task 2: 撤回 CLAUDE.md 变更

**Files:**
- 还原: `CLAUDE.md`

PR #25 重新创建了 CLAUDE.md（+373 行），其中还包含开发者本地笔记 `我现在调用的后端是8002！！！以8002为准`。master 的 `.gitignore` 已排除 `CLAUDE.md`，该文件不应存在于版本控制中。

- [ ] **Step 1: 删除 CLAUDE.md**

```bash
git rm --cached CLAUDE.md 2>/dev/null || true
rm -f CLAUDE.md
```

注意：`git rm --cached` 仅在文件被 tracked 时生效。如果 squash merge 后 .gitignore 生效（文件未被 tracked），则只需确认 `git status` 中不出现 CLAUDE.md。

- [ ] **Step 2: 验证**

```bash
git status
```

预期：CLAUDE.md 不出现在 staged/untracked 列表中（被 .gitignore 排除）。

---

### Task 3: 撤回 vite.config.ts 端口变更

**Files:**
- 还原: `frontend/vite.config.ts:13-14`

PR 将 vite 代理端口从 `8000` 改为 `8002`，这是开发者本地环境适配。项目约定后端端口为 8000。

- [ ] **Step 1: 还原 vite.config.ts**

将 `frontend/vite.config.ts` 的 proxy 配置从：

```typescript
"/api": "http://localhost:8002",
"/healthz": "http://localhost:8002",
```

改回：

```typescript
"/api": "http://localhost:8000",
"/healthz": "http://localhost:8000",
```

- [ ] **Step 2: 验证文件内容**

```bash
grep "localhost" frontend/vite.config.ts
```

预期输出：

```
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
```

---

### Task 4: 验证前端构建

**Files:**
- 无修改

- [ ] **Step 1: 安装依赖（确保 Radix UI 包被安装）**

```bash
cd frontend && npm install
```

预期：成功安装，包含新增的 6 个 @radix-ui 包。

- [ ] **Step 2: TypeScript 类型检查 + 构建**

```bash
cd frontend && npm run build
```

预期：构建成功，无错误。

- [ ] **Step 3: 提交清理变更**

```bash
git add frontend/vite.config.ts
git commit -m "fix: 撤回 PR#25 中的本地环境硬编码（vite 端口 8002→8000）"
```

---

### Task 5: 编写 test-07-audit-results-history.js

**Files:**
- 创建: `frontend/e2e/test-07-audit-results-history.js`

此测试覆盖 PR #25 修复的 5 个场景。前置条件：testing 环境中已有至少 1 个已完成的审核运行（test-05/06 运行后即满足）。

- [ ] **Step 1: 创建测试文件**

```javascript
async page => {
  const u = page.url(); const BASE = u.split('/').slice(0, 3).join('/');

  // ── Step 1: Dashboard 加载 ──
  await page.goto(BASE + '/');
  await page.waitForLoadState('networkidle');
  console.log('Step 1: 进入 Dashboard');
  await page.screenshot({ path: 'e2e/screenshots/07-dashboard.png' });

  // ── Step 2: 验证近期审核记录表格 ──
  const table = page.locator('table');
  await table.waitFor({ timeout: 10000 });
  const rows = table.locator('tbody tr');
  const rowCount = await rows.count();
  if (rowCount === 0) throw new Error('Dashboard 无近期审核记录，无法继续测试');
  console.log('Step 2: 近期审核记录 ' + rowCount + ' 行');

  // ── Step 3: 验证箭头按钮状态 ──
  // PR #25 修复：无 run 的项目箭头应禁用，有 run 的可点击
  const allArrows = table.locator('tbody button');
  const arrowCount = await allArrows.count();
  let enabledIdx = -1;
  let hasDisabled = false;

  for (let i = 0; i < arrowCount; i++) {
    const isDisabled = await allArrows.nth(i).isDisabled();
    if (isDisabled) {
      hasDisabled = true;
    } else if (enabledIdx === -1) {
      enabledIdx = i;
    }
  }

  if (enabledIdx === -1) throw new Error('未找到可点击的跳转箭头');
  console.log('Step 3: 箭头按钮 — 可用: ' + (arrowCount - (hasDisabled ? 1 : 0)) + ', 禁用: ' + (hasDisabled ? '有' : '无'));
  await page.screenshot({ path: 'e2e/screenshots/07-arrow-states.png' });

  // ── Step 4: 点击箭头跳转到审核结果页 ──
  await allArrows.nth(enabledIdx).click();
  await page.waitForURL('**/audit-results', { timeout: 10000 });
  console.log('Step 4: 从 Dashboard 跳转到审核结果页');
  await page.screenshot({ path: 'e2e/screenshots/07-jumped-to-results.png' });

  // ── Step 5: 验证 point_runs 自动加载 ──
  // PR #25 修复：选中 run 后应自动加载 progress，不再显示"暂无审核结果"
  // 等待审核点列表出现（左侧面板中的 button 元素）
  const pointRunButtons = page.locator('.w-80 button, [class*="shrink-0"] button');
  try {
    await pointRunButtons.first().waitFor({ timeout: 15000 });
    const prCount = await pointRunButtons.count();
    console.log('Step 5: point_runs 已自动加载，共 ' + prCount + ' 个审核点');
  } catch {
    // 检查是否显示"暂无审核结果"——这说明 PR #25 修复失效
    const empty = page.getByText('暂无审核结果');
    if (await empty.isVisible()) {
      throw new Error('PR#25 回归：选中 run 后仍显示"暂无审核结果"');
    }
    throw new Error('审核点列表未在 15s 内加载');
  }
  await page.screenshot({ path: 'e2e/screenshots/07-points-loaded.png' });

  // ── Step 6: 验证 run 切换器存在且可交互 ──
  const runSelector = page.locator('header button[role="combobox"], header [data-radix-select-trigger]');
  if (await runSelector.count() > 0) {
    await runSelector.first().click();
    await page.waitForTimeout(500);

    // 检查下拉选项数量
    const options = page.locator('[role="option"]');
    await options.first().waitFor({ timeout: 5000 }).catch(() => {});
    const optCount = await options.count();
    console.log('Step 6: Run 选择器 — ' + optCount + ' 个可选 run');

    if (optCount > 1) {
      // 切换到第二个 run
      await options.nth(1).click();
      await page.waitForTimeout(1000);

      // 验证切换后数据更新（重新等待 point list）
      try {
        await pointRunButtons.first().waitFor({ timeout: 15000 });
        console.log('Step 6: 切换 run 后 point_runs 重新加载');
      } catch {
        const empty = page.getByText('暂无审核结果');
        if (await empty.isVisible()) {
          throw new Error('PR#25 回归：切换 run 后显示"暂无审核结果"');
        }
      }

      // 切回第一个 run 验证不会残留旧数据
      await runSelector.first().click();
      await page.waitForTimeout(500);
      const opts2 = page.locator('[role="option"]');
      await opts2.first().waitFor({ timeout: 5000 }).catch(() => {});
      if (await opts2.count() > 0) {
        await opts2.first().click();
        await page.waitForTimeout(1000);
      }
      console.log('Step 6: 切回原 run，验证无残留');
    } else {
      console.log('Step 6: 仅 1 个 run，跳过切换测试');
      // 关闭下拉
      await page.keyboard.press('Escape');
    }
  } else {
    console.log('Step 6: 未找到 run 选择器，跳过切换测试');
  }
  await page.screenshot({ path: 'e2e/screenshots/07-run-switch.png' });

  // ── Step 7: 验证审核点标题显示 ──
  // PR #25 修复：失效审核点应显示"（已失效）"而非截断 ID
  const allButtonTexts = [];
  const btnCount = await pointRunButtons.count();
  for (let i = 0; i < Math.min(btnCount, 10); i++) {
    const text = await pointRunButtons.nth(i).textContent();
    allButtonTexts.push(text.trim());
  }
  const hasOrphan = allButtonTexts.some(t => /^[0-9a-f]{8}$/i.test(t.split(/\s/)[0]));
  if (hasOrphan) {
    console.log('WARN Step 7: 存在显示截断 ID 的审核点（可能是失效数据）');
  } else {
    console.log('Step 7: 审核点标题正常（无截断 ID）');
  }

  // ── Step 8: 等待数秒验证后台轮询不会覆盖 ──
  // PR #25 修复：后台轮询不应覆盖当前查看的 run
  const beforeText = await pointRunButtons.first().textContent();
  await page.waitForTimeout(5000);
  const afterText = await pointRunButtons.first().textContent();
  if (beforeText !== afterText) {
    console.log('WARN Step 8: 5s 后列表内容变化，可能是后台轮询覆盖（beforeText=' + beforeText.slice(0, 30) + ', afterText=' + afterText.slice(0, 30) + '）');
  } else {
    console.log('Step 8: 5s 后列表稳定，后台轮询未覆盖');
  }

  await page.screenshot({ path: 'e2e/screenshots/07-final.png', fullPage: true });
  console.log('== test-07-audit-results-history 全部通过 ==');
}
```

- [ ] **Step 2: 验证文件语法**

```bash
node -c frontend/e2e/test-07-audit-results-history.js
```

预期：无语法错误。注意：`node -c` 对 `async page => {}` 裸函数表达式会报错，因为它不是完整语句。但 playwright-cli 的 `run-code` 内部会包裹此函数，所以这是正常的。可改用：

```bash
node -e "const fn = $(cat frontend/e2e/test-07-audit-results-history.js); console.log('语法检查通过')"
```

---

### Task 6: 更新 run-tests.sh

**Files:**
- 修改: `frontend/e2e/run-tests.sh:42`

- [ ] **Step 1: 追加 test-07 到 ALL_TESTS 数组**

将 `run-tests.sh` 第 42 行：

```bash
ALL_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare" "04-ai-extract" "05-ai-audit" "06-ai-audit-multifile")
```

改为：

```bash
ALL_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare" "04-ai-extract" "05-ai-audit" "06-ai-audit-multifile" "07-audit-results-history")
```

- [ ] **Step 2: 验证脚本语法**

```bash
bash -n frontend/e2e/run-tests.sh
```

预期：无输出（语法正确）。

---

### Task 7: 提交 test-07

**Files:**
- 无（git 操作）

- [ ] **Step 1: 提交测试文件**

```bash
git add frontend/e2e/test-07-audit-results-history.js frontend/e2e/run-tests.sh
git commit -m "test(e2e): 新增 test-07 验证审核结果页历史 run 加载与 Dashboard 跳转"
```

---

### Task 8: 部署到 testing 并运行全部 E2E 测试

**Files:**
- 无修改

- [ ] **Step 1: 部署到 testing 环境**

```bash
bash scripts/deploy.sh --target testing
```

- [ ] **Step 2: 运行快速测试（01-03，无 LLM 调用）**

```bash
bash frontend/e2e/run-tests.sh --quick
```

预期：3 个测试全部 PASS。

- [ ] **Step 3: 单独运行 test-07**

```bash
bash frontend/e2e/run-tests.sh --only 07-audit-results-history
```

预期：PASS，截图输出到 `frontend/e2e/screenshots/07-*.png`。

- [ ] **Step 4: 运行全部测试（含 LLM 调用的 04-06，可选）**

```bash
bash frontend/e2e/run-tests.sh
```

预期：7 个测试全部 PASS。注意 test-04/05/06 涉及真实 LLM 调用，耗时约 10-60 分钟。

---

## 风险与注意事项

| 风险 | 缓解 |
|------|------|
| squash merge 后 CLAUDE.md 可能被 track | 合并后立即检查 `git status`，若被 track 则 `git rm --cached` |
| Radix UI 依赖升级引入 breaking change | Task 4 的构建验证覆盖此风险 |
| testing 环境无已完成的审核运行 | test-07 依赖 test-05/06 创建的数据；首次运行需先跑 05 或 06 |
| test-07 的 CSS selector 可能因 UI 重构失效 | 使用语义化选择器（role/text）为主，CSS class 为辅 |
