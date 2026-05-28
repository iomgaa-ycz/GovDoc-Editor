import type { GovDocument, Tag } from "../types/ui";

const BASE = import.meta.env.VITE_GOVDOC_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, init);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${resp.status}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export async function uploadDocuments(files: File[]): Promise<GovDocument[]> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return request("/api/v1/documents/upload", { method: "POST", body: form });
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
