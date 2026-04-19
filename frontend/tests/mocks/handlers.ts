import { http, HttpResponse } from "msw";

/**
 * 默认 MSW handlers。
 * 每个测试用 server.use(...) 覆盖具体端点，避免互相污染。
 */
export const handlers = [
  http.get("*/healthz", () => HttpResponse.json({ status: "ok" })),
];
