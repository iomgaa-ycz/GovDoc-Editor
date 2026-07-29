import type { GovDocument, Tag } from "../types/ui";

const BASE = import.meta.env.VITE_GOVDOC_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, init);
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    // FastAPI 常用 {"detail": "..."} 返回业务错误；只直抛字符串 detail，避免展示原始 JSON。
    if (body) {
      try {
        const parsedBody = JSON.parse(body) as { detail?: unknown };
        if (typeof parsedBody.detail === "string") {
          throw new Error(parsedBody.detail);
        }
      } catch (err) {
        if (err instanceof Error && err.name === "Error") {
          throw err;
        }
      }
    }
    throw new Error(`API ${resp.status}: ${body || resp.statusText}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

/** 使用 XMLHttpRequest 上传单个文件，支持上传进度回调 */
export function uploadSingleDocument(
  file: File,
  onProgress?: (percentage: number) => void,
): Promise<GovDocument[]> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("files", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/v1/documents/upload`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as GovDocument[]);
        } catch {
          reject(new Error("响应解析失败"));
        }
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new Error(body.detail ?? `HTTP ${xhr.status}`));
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      }
    };

    xhr.onerror = () => reject(new Error("网络错误"));
    xhr.onabort = () => reject(new Error("上传已取消"));
    xhr.send(form);
  });
}

export async function listDocuments(params?: {
  status?: string; file_type?: string; tag_id?: string; q?: string;
}): Promise<GovDocument[]> {
  const sp = new URLSearchParams();
  if (params?.status) sp.set("status", params.status);
  if (params?.file_type) sp.set("file_type", params.file_type);
  if (params?.tag_id) sp.set("tag_id", params.tag_id);
  if (params?.q) sp.set("q", params.q);
  const qs = sp.toString();
  return request(`/api/v1/documents/${qs ? `?${qs}` : ""}`);
}

export async function getDocument(id: string): Promise<GovDocument> {
  return request(`/api/v1/documents/${id}`);
}

export async function deleteDocument(id: string): Promise<void> {
  return request(`/api/v1/documents/${id}`, { method: "DELETE" });
}

export async function reconvertDocument(id: string): Promise<{ id: string; status: string }> {
  return request(`/api/v1/documents/${id}/reconvert`, { method: "POST" });
}

export async function batchTagDocuments(documentIds: string[], tagIds: string[]): Promise<{ added: number }> {
  return request("/api/v1/documents/batch-tag", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, tag_ids: tagIds }),
  });
}

export async function removeDocumentTag(docId: string, tagId: string): Promise<void> {
  return request(`/api/v1/documents/${docId}/tags/${tagId}`, { method: "DELETE" });
}

export async function listTags(): Promise<Tag[]> {
  return request("/api/v1/tags/");
}

export async function createTag(name: string, color: string): Promise<Tag> {
  return request("/api/v1/tags/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, color }),
  });
}

export async function deleteTag(id: string): Promise<void> {
  return request(`/api/v1/tags/${id}`, { method: "DELETE" });
}
