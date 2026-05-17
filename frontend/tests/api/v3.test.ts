/**
 * v3.ts request() + API 函数契约测试。
 *
 * 覆盖：
 *   Group A — request() 内部契约（URL 拼接、init 透传、200 / 401 / 500 / 空体 / 网络错 / 204）
 *   Group B — 导出 API 函数采样（createProject POST 体、listProjects GET、getAuditRunProgress 形状）
 *
 * 设计原则：
 *   - 每条 case 自包含，仅在本 case 内 server.use(...) 覆盖端点
 *   - jsdom 默认 origin = http://localhost/，handler 一律使用 "* /path" 前缀（msw 通配符）
 *   - 直接断言 thrown Error.message 形如 `API <status>: <body|statusText>`
 */

import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import {
  createProject,
  getAuditRunProgress,
  listProjects,
  request,
} from "@/api/v3";
import type { AuditRunProgress, Project } from "@/types/ui";

/* ──────────────────────────────────────────────────────────────
 * Group A — request() 内部契约
 * ────────────────────────────────────────────────────────────── */

describe("request() — URL 与方法", () => {
  it("默认拼接 base + path 并发起 GET 请求", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    server.use(
      http.get("*/api/v1/ping", ({ request: req }) => {
        capturedUrl = req.url;
        capturedMethod = req.method;
        return HttpResponse.json({ ok: true });
      }),
    );

    const data = await request<{ ok: boolean }>("/api/v1/ping");

    expect(data).toEqual({ ok: true });
    expect(capturedMethod).toBe("GET");
    expect(capturedUrl).toMatch(/\/api\/v1\/ping$/);
  });

  it("RequestInit.method 透传至 fetch（POST）", async () => {
    let capturedMethod = "";
    server.use(
      http.post("*/api/v1/things", ({ request: req }) => {
        capturedMethod = req.method;
        return HttpResponse.json({ created: true });
      }),
    );

    await request<{ created: boolean }>("/api/v1/things", { method: "POST" });

    expect(capturedMethod).toBe("POST");
  });

  it("RequestInit.headers 透传（Content-Type 等）", async () => {
    let capturedContentType: string | null = null;
    server.use(
      http.post("*/api/v1/headers-check", ({ request: req }) => {
        capturedContentType = req.headers.get("content-type");
        return HttpResponse.json({});
      }),
    );

    await request("/api/v1/headers-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ x: 1 }),
    });

    expect(capturedContentType).toBe("application/json");
  });

  it("RequestInit.body 透传（JSON 字符串体）", async () => {
    let capturedBody: unknown = null;
    server.use(
      http.post("*/api/v1/body-check", async ({ request: req }) => {
        capturedBody = await req.json();
        return HttpResponse.json({});
      }),
    );

    await request("/api/v1/body-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "alpha", n: 2 }),
    });

    expect(capturedBody).toEqual({ name: "alpha", n: 2 });
  });
});

describe("request() — 成功响应解码", () => {
  it("200 OK 时解析 JSON 主体并返回", async () => {
    server.use(
      http.get("*/api/v1/json-ok", () =>
        HttpResponse.json({ id: "p-1", name: "demo" }),
      ),
    );

    const data = await request<{ id: string; name: string }>("/api/v1/json-ok");

    expect(data).toEqual({ id: "p-1", name: "demo" });
  });

  it("204 No Content 返回 undefined（不尝试解析 body）", async () => {
    server.use(
      http.delete(
        "*/api/v1/no-content",
        () => new HttpResponse(null, { status: 204 }),
      ),
    );

    const data = await request<void>("/api/v1/no-content", { method: "DELETE" });

    expect(data).toBeUndefined();
  });
});

describe("request() — 错误响应映射", () => {
  it("401 + 文本 body → 抛 `API 401: <body>`", async () => {
    server.use(
      http.get(
        "*/api/v1/unauth",
        () =>
          new HttpResponse("invalid token", {
            status: 401,
            headers: { "Content-Type": "text/plain" },
          }),
      ),
    );

    await expect(request("/api/v1/unauth")).rejects.toThrow(
      /^API 401: invalid token$/,
    );
  });

  it("500 + JSON 字符串 body → 抛 `API 500: <body 原文>`", async () => {
    const errPayload = JSON.stringify({ detail: "boom" });
    server.use(
      http.get(
        "*/api/v1/server-err",
        () =>
          new HttpResponse(errPayload, {
            status: 500,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    // request 用 res.text() 取 body，故应包含原始 JSON 字符串
    await expect(request("/api/v1/server-err")).rejects.toThrow(
      /^API 500: \{"detail":"boom"\}$/,
    );
  });

  it("空 body 时回退到 statusText（如 503 Service Unavailable）", async () => {
    server.use(
      http.get(
        "*/api/v1/empty-err",
        () =>
          new HttpResponse("", {
            status: 503,
            statusText: "Service Unavailable",
          }),
      ),
    );

    // body 为空 → 拼 statusText；不同 fetch 实现 statusText 可能不同，
    // 但至少必须包含状态码前缀且不为空尾。
    await expect(request("/api/v1/empty-err")).rejects.toThrow(/^API 503: .+/);
  });

  it("网络层错误（HttpResponse.error）应原样抛出", async () => {
    server.use(http.get("*/api/v1/net-down", () => HttpResponse.error()));

    // fetch 在网络层失败时抛 TypeError("Failed to fetch") 或类似。
    // 我们只要求 request() 不吞错。
    await expect(request("/api/v1/net-down")).rejects.toThrow();
  });
});

/* ──────────────────────────────────────────────────────────────
 * Group B — 导出 API 函数采样
 * ────────────────────────────────────────────────────────────── */

describe("listProjects() — GET /api/v1/projects", () => {
  it("命中 GET 端点并返回 Project[]", async () => {
    const fakeProjects: Project[] = [
      {
        id: "proj-1",
        name: "项目甲",
        created_at: "2026-04-19T00:00:00Z",
        created_by: "alice",
      },
      {
        id: "proj-2",
        name: "项目乙",
        created_at: "2026-04-19T01:00:00Z",
        created_by: "bob",
      },
    ];
    server.use(
      http.get("*/api/v1/projects", () => HttpResponse.json(fakeProjects)),
    );

    const got = await listProjects();

    expect(got).toHaveLength(2);
    expect(got[0].id).toBe("proj-1");
    expect(got[1].created_by).toBe("bob");
  });
});

describe("createProject() — POST /api/v1/projects", () => {
  it("以 snake_case 体（name/created_by）发起 POST 并解码返回", async () => {
    let capturedBody: unknown = null;
    let capturedMethod = "";
    server.use(
      http.post("*/api/v1/projects", async ({ request: req }) => {
        capturedMethod = req.method;
        capturedBody = await req.json();
        return HttpResponse.json({
          id: "proj-new",
          name: "新建项目",
          created_at: "2026-04-19T02:00:00Z",
          created_by: "carol",
        });
      }),
    );

    const created = await createProject("新建项目", "carol");

    expect(capturedMethod).toBe("POST");
    expect(capturedBody).toEqual({ name: "新建项目", created_by: "carol" });
    expect(created.id).toBe("proj-new");
    expect(created.name).toBe("新建项目");
  });

  it("后端返回 4xx 时按 request() 错误契约抛出", async () => {
    server.use(
      http.post(
        "*/api/v1/projects",
        () =>
          new HttpResponse("name duplicated", {
            status: 409,
            headers: { "Content-Type": "text/plain" },
          }),
      ),
    );

    await expect(createProject("dup", "carol")).rejects.toThrow(
      /^API 409: name duplicated$/,
    );
  });
});

describe("getAuditRunProgress() — GET /api/v1/audit/runs/{id}/progress", () => {
  it("URL 包含 audit_run_id 且返回 AuditRunProgress 形状", async () => {
    let capturedUrl = "";
    const fakeProgress: AuditRunProgress = {
      audit_run_id: "run-42",
      status: "running",
      total_count: 10,
      processed_count: 4,
      point_runs: [
        {
          id: "pr-1",
          checkpoint_final_id: "cp-1",
          status: "completed",
          error: null,
          finding_json: null,
          started_at: null,
          completed_at: null,
          current_phase: null,
        },
      ],
    };
    server.use(
      http.get(
        "*/api/v1/audit/runs/run-42/progress",
        ({ request: req }) => {
          capturedUrl = req.url;
          return HttpResponse.json(fakeProgress);
        },
      ),
    );

    const got = await getAuditRunProgress("run-42");

    expect(capturedUrl).toMatch(/\/api\/v1\/audit\/runs\/run-42\/progress$/);
    expect(got.audit_run_id).toBe("run-42");
    expect(got.processed_count).toBe(4);
    expect(got.total_count).toBe(10);
    expect(got.point_runs).toHaveLength(1);
    expect(got.point_runs[0].status).toBe("completed");
  });
});
