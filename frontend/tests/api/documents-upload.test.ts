/**
 * uploadSingleDocument() 单元测试。
 *
 * 该函数使用 XMLHttpRequest（为获取上传进度），故用 FakeXHR 替身替换
 * 全局 XMLHttpRequest，手动驱动 onprogress / onload / onerror 事件，
 * 覆盖：成功解析、进度回调、HTTP 错误（含 detail）、响应解析失败、网络错误。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uploadSingleDocument } from "@/api/documents";

interface ProgressLike {
  loaded: number;
  total: number;
  lengthComputable: boolean;
}

/** XMLHttpRequest 测试替身：记录请求并暴露手动触发事件的辅助方法 */
class FakeXHR {
  static instances: FakeXHR[] = [];

  upload: { onprogress: ((e: ProgressLike) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  status = 0;
  responseText = "";
  method = "";
  url = "";
  body: unknown = null;

  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }

  send(body: unknown): void {
    this.body = body;
    FakeXHR.instances.push(this);
  }

  /* ---- 测试辅助 ---- */
  emitProgress(loaded: number, total: number, lengthComputable = true): void {
    this.upload.onprogress?.({ loaded, total, lengthComputable });
  }

  finish(status: number, responseText: string): void {
    this.status = status;
    this.responseText = responseText;
    this.onload?.();
  }

  static last(): FakeXHR {
    return FakeXHR.instances[FakeXHR.instances.length - 1];
  }
}

describe("uploadSingleDocument", () => {
  beforeEach(() => {
    FakeXHR.instances = [];
    // msw 将 XMLHttpRequest 定义为只读属性，故用 stubGlobal 注入替身
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function makeFile(name = "a.pdf"): File {
    return new File(["data"], name, { type: "application/pdf" });
  }

  it("2xx 返回解析后的文档数组，并以 POST + FormData 发往上传端点", async () => {
    const p = uploadSingleDocument(makeFile("招标文件.pdf"));
    const xhr = FakeXHR.last();

    expect(xhr.method).toBe("POST");
    expect(xhr.url).toMatch(/\/api\/v1\/documents\/upload$/);
    expect(xhr.body).toBeInstanceOf(FormData);
    expect((xhr.body as FormData).get("files")).toBeInstanceOf(File);

    xhr.finish(200, JSON.stringify([{ id: "doc-1" }]));
    await expect(p).resolves.toEqual([{ id: "doc-1" }]);
  });

  it("回调上传进度（四舍五入），lengthComputable=false 时不回调", async () => {
    const onProgress = vi.fn();
    const p = uploadSingleDocument(makeFile(), onProgress);
    const xhr = FakeXHR.last();

    xhr.emitProgress(50, 200); // 25%
    xhr.emitProgress(1, 3); // 33%（四舍五入）
    xhr.emitProgress(10, 10, false); // 不可计算 → 不回调

    expect(onProgress).toHaveBeenCalledTimes(2);
    expect(onProgress).toHaveBeenNthCalledWith(1, 25);
    expect(onProgress).toHaveBeenNthCalledWith(2, 33);

    xhr.finish(201, "[]");
    await expect(p).resolves.toEqual([]);
  });

  it("非 2xx + JSON {detail} 抛出 detail 文案", async () => {
    const p = uploadSingleDocument(makeFile());
    FakeXHR.last().finish(400, JSON.stringify({ detail: "文件格式不支持" }));
    await expect(p).rejects.toThrow("文件格式不支持");
  });

  it("非 2xx + 非 JSON 响应抛出 HTTP <status>", async () => {
    const p = uploadSingleDocument(makeFile());
    FakeXHR.last().finish(502, "<html>Bad Gateway</html>");
    await expect(p).rejects.toThrow("HTTP 502");
  });

  it("2xx 但响应非合法 JSON 抛出『响应解析失败』", async () => {
    const p = uploadSingleDocument(makeFile());
    FakeXHR.last().finish(200, "not-json");
    await expect(p).rejects.toThrow("响应解析失败");
  });

  it("网络错误抛出『网络错误』", async () => {
    const p = uploadSingleDocument(makeFile());
    FakeXHR.last().onerror?.();
    await expect(p).rejects.toThrow("网络错误");
  });
});
