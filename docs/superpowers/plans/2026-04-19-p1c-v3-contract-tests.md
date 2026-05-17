# P1c · v3.ts 契约测试 + 前端测试基建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 一次性引入 vitest + @testing-library/react + MSW 前端测试基建，并为 `frontend/src/api/v3.ts::request()` 编写 8+ 契约测试。本项自身就是 P1a 的护栏。

**Architecture:** vitest 原生支持 Vite，零额外配置；MSW 拦截 fetch 请求。

**Tech Stack:** vitest, @testing-library/react, @testing-library/jest-dom, msw@^2.x, jsdom, @testing-library/user-event

**依赖：** Umbrella 分支已建立；可与 P0/P1b 并行。**本项必须先于 P1a merge 入 umbrella。**

---

## Task 0: 建立子分支

- [ ] **Step 1**

```bash
git checkout feat/tech-debt-cleanup
git pull --ff-only 2>/dev/null || true
git checkout -b feat/p1c-v3-contract-tests
```

---

## Task 1: 添加前端测试依赖

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: 安装 devDeps**

```bash
cd frontend
npm install --save-dev \
    vitest@^2.0.0 \
    @vitest/ui@^2.0.0 \
    @testing-library/react@^16.0.0 \
    @testing-library/jest-dom@^6.5.0 \
    @testing-library/user-event@^14.5.0 \
    jsdom@^25.0.0 \
    msw@^2.4.0
cd ..
```

Expected: `package.json` 的 `devDependencies` 新增 7 项，`package-lock.json` 更新

- [ ] **Step 2: 在 `frontend/package.json` 的 `scripts` 加入测试命令**

读 package.json 然后追加：
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:ui": "vitest --ui"
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: 引入 vitest + testing-library + MSW 前端测试基建依赖"
```

---

## Task 2: 配置 vitest

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tests/setup.ts`

- [ ] **Step 1: 建立 `frontend/vitest.config.ts`**

```typescript
/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
    include: ["tests/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

- [ ] **Step 2: 建立 `frontend/tests/setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

// MSW 生命周期
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

- [ ] **Step 3: 验证配置可加载**

```bash
cd frontend
npx vitest --run --reporter=verbose 2>&1 | head -20
cd ..
```

Expected: vitest 启动报错"No test files"（因为还没写），但不会有 config load 错误

- [ ] **Step 4: 提交**

```bash
git add frontend/vitest.config.ts frontend/tests/setup.ts
git commit -m "test: 配置 vitest + jsdom + MSW setup"
```

---

## Task 3: 建立 MSW handlers 基础结构

**Files:**
- Create: `frontend/tests/mocks/server.ts`
- Create: `frontend/tests/mocks/handlers.ts`

- [ ] **Step 1: `frontend/tests/mocks/server.ts`**

```typescript
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

- [ ] **Step 2: `frontend/tests/mocks/handlers.ts`（默认空，每个 test 可 override）**

```typescript
import { http, HttpResponse } from "msw";

/**
 * 默认 MSW handlers。
 *
 * 每个测试用 `server.use(...)` 覆盖具体端点，避免互相污染。
 * 这里留一组极简默认 handler，供未 override 的测试兜底。
 */
export const handlers = [
  // 默认 healthcheck 返回 200（未来 P1a 可能需要）
  http.get("*/healthz", () => HttpResponse.json({ status: "ok" })),
];
```

- [ ] **Step 3: 提交**

```bash
git add frontend/tests/mocks/
git commit -m "test: 添加 MSW server + 基础 handlers"
```

---

## Task 4: 编写 `request()` 契约测试（8+ case）

**Files:**
- Create: `frontend/tests/api/v3.test.ts`

- [ ] **Step 1: 先阅读 `frontend/src/api/v3.ts::request()` 的签名与逻辑**

Run: `cat frontend/src/api/v3.ts | head -60`

**实际签名（已核实）**：
```typescript
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = resolveBaseUrl();                          // 从 import.meta.env.VITE_GOVDOC_API_BASE_URL 读取，默认 ""
  const res = await fetch(`${base}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
```

要点：
- `init` 是原生 `RequestInit`（不是自定义 options）
- 没有内置 query string 支持——调用方自己拼 `?key=value`
- 错误响应抛 `Error("API {status}: {body}")`
- 204 返回 undefined
- 其他 2xx 返回 `res.json()` 结果
- API 路径**是 `/api/v1/*`**，不是 v3（v3 只是文件名）

- [ ] **Step 2: 创建 `frontend/tests/api/v3.test.ts`**

因为 `resolveBaseUrl()` 读 `import.meta.env.VITE_GOVDOC_API_BASE_URL`，在 vitest 下该变量默认空串，fetch 会用**相对路径**。MSW 用通配符 `*` 匹配任意 origin（jsdom 默认 `http://localhost/`）。

```typescript
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";

import {
  request,
  createProject,
  getAuditRunProgress,
  listProjects,
} from "@/api/v3";


describe("v3.ts :: request() contract", () => {
  // 1. baseURL 为空时使用相对路径，fetch 基于 document origin
  it("相对路径请求成功（baseURL 空时）", async () => {
    server.use(
      http.get("*/api/v1/projects", () => HttpResponse.json([]))
    );
    const result = await request<unknown[]>("/api/v1/projects");
    expect(result).toEqual([]);
  });

  // 2. RequestInit 的 method 与 headers 透传
  it("POST 请求 method/headers/body 被透传", async () => {
    let capturedBody: unknown = null;
    let capturedContentType: string | null = null;
    server.use(
      http.post("*/api/v1/projects", async ({ request: req }) => {
        capturedContentType = req.headers.get("content-type");
        capturedBody = await req.json();
        return HttpResponse.json({ id: "p_new", name: "x", created_by: "t" });
      })
    );
    await request("/api/v1/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "x" }),
    });
    expect(capturedContentType).toBe("application/json");
    expect(capturedBody).toEqual({ name: "x" });
  });

  // 3. 成功响应解析为 JSON
  it("200 响应 res.json() 被返回", async () => {
    server.use(
      http.get("*/api/v1/projects/p1", () =>
        HttpResponse.json({ id: "p1", name: "项目一", created_by: "t" })
      )
    );
    const result = await request<{ id: string; name: string }>("/api/v1/projects/p1");
    expect(result.id).toBe("p1");
    expect(result.name).toBe("项目一");
  });

  // 4. 401 抛 Error 且消息含 status 与 body
  it("401 响应抛出 Error('API 401: ...')", async () => {
    server.use(
      http.get("*/api/v1/projects/p1", () =>
        new HttpResponse("unauthorized", { status: 401 })
      )
    );
    await expect(request("/api/v1/projects/p1")).rejects.toThrow(/API 401/);
  });

  // 5. 500 抛 Error
  it("500 响应抛出 Error('API 500: ...')", async () => {
    server.use(
      http.get("*/api/v1/projects/p1", () =>
        new HttpResponse("server err", { status: 500 })
      )
    );
    await expect(request("/api/v1/projects/p1")).rejects.toThrow(/API 500/);
  });

  // 6. 错误响应 body 为空时 fallback 到 statusText
  it("错误响应空 body 时使用 res.statusText", async () => {
    server.use(
      http.get("*/api/v1/projects/p1", () =>
        new HttpResponse("", { status: 502, statusText: "Bad Gateway" })
      )
    );
    await expect(request("/api/v1/projects/p1")).rejects.toThrow(/Bad Gateway/);
  });

  // 7. fetch reject（网络错误）原样抛出
  it("网络错误（fetch reject）原样抛出", async () => {
    server.use(
      http.get("*/api/v1/projects/p1", () => HttpResponse.error())
    );
    await expect(request("/api/v1/projects/p1")).rejects.toThrow();
  });

  // 8. 204 No Content 返回 undefined
  it("204 响应返回 undefined", async () => {
    server.use(
      http.delete("*/api/v1/checkpoints/c1", () =>
        new HttpResponse(null, { status: 204 })
      )
    );
    const result = await request("/api/v1/checkpoints/c1", { method: "DELETE" });
    expect(result).toBeUndefined();
  });
});


describe("v3.ts :: 具体 API 函数的契约（抽样）", () => {
  // 9. createProject(name, createdBy) 发正确请求
  it("createProject 发 POST /api/v1/projects 带 snake_case body", async () => {
    let capturedBody: unknown = null;
    server.use(
      http.post("*/api/v1/projects", async ({ request: req }) => {
        capturedBody = await req.json();
        return HttpResponse.json({ id: "p_new", name: "新项目", created_by: "alice" });
      })
    );
    const result = await createProject("新项目", "alice");
    expect(capturedBody).toEqual({ name: "新项目", created_by: "alice" });
    expect(result.id).toBe("p_new");
  });

  // 10. listProjects 返回列表
  it("listProjects GET /api/v1/projects", async () => {
    server.use(
      http.get("*/api/v1/projects", () =>
        HttpResponse.json([
          { id: "p1", name: "A", created_by: "t" },
          { id: "p2", name: "B", created_by: "t" },
        ])
      )
    );
    const result = await listProjects();
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("p1");
  });

  // 11. getAuditRunProgress GET /api/v1/audit/runs/:id/progress
  it("getAuditRunProgress GET 正确路径", async () => {
    server.use(
      http.get("*/api/v1/audit/runs/ar1/progress", () =>
        HttpResponse.json({ processed: 2, total: 5, status: "running" })
      )
    );
    const result = await getAuditRunProgress("ar1");
    expect(result.processed).toBe(2);
    expect(result.total).toBe(5);
  });
});
```

⚠️ **执行时注意**：
- `AuditRunProgress` 类型的实际字段可能和这里写的不同，参照 `frontend/src/types/ui.ts` 的真实定义
- 若 `listProjects` 返回对象结构不是 `Project[]` 而是 `{ items: Project[] }` 等，按实际 `types/ui.ts` 调整

- [ ] **Step 3: 跑测试**

```bash
cd frontend && npm test
cd ..
```

Expected: 10 case 全绿

- [ ] **Step 4: 提交**

```bash
git add frontend/tests/api/v3.test.ts
git commit -m "test: 添加 v3.ts request 契约测试 10 case"
```

---

## Task 5: tsconfig 更新 + gitignore

**Files:**
- Modify: `frontend/tsconfig.json` 或 `tsconfig.app.json`
- Modify: `.gitignore`

- [ ] **Step 1: 确保 tsconfig 包含 tests/ 目录**

检查 `frontend/tsconfig.app.json`（或 `tsconfig.json`）的 `include` 字段。若未含 `tests`，添加：

```json
{
  "include": ["src", "tests"]
}
```

- [ ] **Step 2: .gitignore 确认已覆盖 vitest 产出**

```bash
grep -E "coverage|\.vitest" .gitignore || echo "需要补"
```

若没覆盖，追加：
```
# Frontend test artifacts
frontend/coverage/
frontend/.vitest/
```

- [ ] **Step 3: 跑 tsc 确认无错**

```bash
cd frontend && npx tsc -b
cd ..
```

Expected: 零 error

- [ ] **Step 4: 提交**

```bash
git add frontend/tsconfig*.json .gitignore
git commit -m "chore: 同步 tsconfig 与 .gitignore 以覆盖前端测试目录"
```

---

## Task 6: 推 PR + 合入 umbrella

- [ ] **Step 1**

```bash
git push -u origin feat/p1c-v3-contract-tests
```

- [ ] **Step 2: 开 PR**

PR 描述模板：
```
## 目的
P1c · 一次性引入前端测试基建 + v3.ts::request() 契约测试

## 变更
- 新增 7 个 devDeps: vitest, @testing-library/react, @testing-library/jest-dom,
  @testing-library/user-event, jsdom, msw, @vitest/ui
- frontend/vitest.config.ts: 配置 jsdom + setup.ts
- frontend/tests/setup.ts: MSW 生命周期
- frontend/tests/mocks/server.ts + handlers.ts: MSW 基础结构
- frontend/tests/api/v3.test.ts: 10 case 覆盖 URL 拼接 / query / body / 成功 / 401 / 500 / 网络错 / 204

## 作为 P1a 护栏
本 PR 合入后，P1a AIReviewPage 拆分可复用 MSW handlers 做 render test。

## DoD
- [x] npm test 全绿
- [x] tsc -b 零 error
- [x] mocks/ 可被 P1a 复用
```

- [ ] **Step 3: CI 绿 + review → merge**

```bash
git checkout feat/tech-debt-cleanup
git merge --no-ff feat/p1c-v3-contract-tests -m "Merge P1c · 前端测试基建 + v3.ts 契约测试"
```

- [ ] **Step 4: 回滚演练**

按 umbrella index plan 执行。

---

## P1c DoD 汇总

- [ ] `npm test` 全绿
- [ ] `tsc -b` 零 error
- [ ] 10 case 覆盖 request() 契约
- [ ] MSW handlers 可被后续 render test 复用（P1a 会用）
- [ ] 回滚演练通过
