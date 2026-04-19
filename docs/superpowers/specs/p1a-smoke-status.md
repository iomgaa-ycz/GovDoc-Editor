# P1a · 手工 Smoke 状态声明

**适用分支：** `feat/p1a-aireview-split`
**日期：** 2026-04-19
**状态：** **NOT RUN IN THIS SESSION** —— 浏览器 smoke 需要本地 dev server + 人工操作，当前 agent 执行环境无法驱动真实浏览器交互。

---

## 1. 目标 smoke 步骤（来自 plan Task 9）

1. 启动后端：`conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000`
2. 启动前端：`cd frontend && npm run dev`
3. 浏览器访问 `http://localhost:5173/ai-review`，执行：
   - 创建项目 `smoke-test`
   - 上传 `tests/fixtures/tender_small.docx`
   - 勾选 3 个审核点
   - 启动审计
   - 观察进度区更新

**预期：** 整个流程无 `console.error`，UI 状态与 P1a 之前一致。

---

## 2. 本会话为何未执行

| 因素 | 说明 |
|------|------|
| 环境限制 | Agent 会话无浏览器（无 Chrome DevTools / Playwright 可驱动的持久化 UI） |
| 启动耗时 | `npm run dev` 与 uvicorn 为长驻进程，非一次性命令 |
| 交互性 | 文件上传、按钮点击需要真人判断界面状态 |

---

## 3. 自动化测试对 smoke 的替代覆盖范围

P1a Bundle 1 已建立行为护栏 render test（`frontend/tests/pages/AIReviewPage.test.tsx`），覆盖：

| 已覆盖 | 未覆盖 |
|---|---|
| UI 关键文案渲染（"任务设置"/"选择项目" 等） | 真实点击交互后的动画/过渡 |
| Context consumer 组合（`useWorkbench` 取值） | WebSocket / SSE 实时进度推送 |
| 子组件 props 传递契约 | 视觉回归（布局塌陷、z-index 错位） |
| MSW mock 下的 API 响应 shape | 真实 LLM 后端延时下的 UX |
| React 渲染合法性（无 render 崩溃） | 运行时 React key warning / prop-type warning |
| Modal 打开/关闭分支 | 文件对话框原生 `input[type=file]` 交互 |

**风险剩余：** 视觉回归、运行时 console warning、跨浏览器兼容性 **未被自动化测试捕获**。

---

## 4. 建议

在将 umbrella 分支 `feat/tech-debt-cleanup` 合回 `master` **之前**，由人类运维按第 1 节步骤执行一次完整 smoke：

- [ ] 启动后端 + 前端
- [ ] 完成 5 步浏览器操作
- [ ] 检查 DevTools Console：无 `error` 级别输出
- [ ] 视觉对比：与 P1a 拆分前快照一致
- [ ] 通过后在 PR/merge commit 中备注 "smoke-test: passed by <operator> on <date>"

若 smoke 发现回归，应开 hotfix commit 修复后再合并 master。

---

## 5. 关联文档

- Plan：`docs/superpowers/plans/2026-04-19-p1a-aireview-split.md` Task 9
- 责任地图：`docs/superpowers/specs/p1a-aireview-responsibility-map.md`
- 行为护栏测试：`frontend/tests/pages/AIReviewPage.test.tsx`
