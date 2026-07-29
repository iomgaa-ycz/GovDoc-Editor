import { request } from "./v3";

export type CompareCategoryId = "paragraph" | "sentence" | "similar";

export interface CompareCategory {
  id: CompareCategoryId;
  label: string;
  color: string;
}

export interface CompareFileMeta {
  fileIndex: number;
  name: string;
  suffix: string;
  paragraphCount: number;
  blockCount: number;
}

export interface CompareSummary {
  fileCount: number;
  files: CompareFileMeta[];
  commonParagraphCount: number;
  commonSentenceCount: number;
  commonSegmentCount: number;
  commonSimilarCount: number;
  matchCount: number;
  minSegmentLength: number;
}

export interface CompareBlockSegment {
  text: string;
  matchIds: string[];
  categories: CompareCategoryId[];
  primaryMatchId: string | null;
}

export interface CompareDocumentBlock {
  id: string;
  index: number;
  text: string;
  segments: CompareBlockSegment[];
}

export interface CompareDocument {
  fileIndex: number;
  name: string;
  suffix: string;
  blockCount: number;
  blocks: CompareDocumentBlock[];
}

export interface CompareSubmitResponse {
  reviewId: string;
  status: string;
}

export interface CompareRunStatus {
  reviewId: string;
  status: string;
  fileCount: number;
  fileNames: string[];
  progress: {
    phase: string;
    step?: string;
    current?: number;
    total?: number;
  } | null;
  error: string | null;
  createdAt: string;
  completedAt: string | null;
}

function resolveBaseUrl(): string {
  return import.meta.env.VITE_GOVDOC_API_BASE_URL || "";
}

export async function compareDocuments(documentIds: string[]): Promise<CompareSubmitResponse> {
  return request("/api/v1/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

export function getCompareStatus(reviewId: string): Promise<CompareRunStatus> {
  return request(`/api/v1/compare/${reviewId}/status`);
}

export function listCompareRuns(): Promise<CompareRunStatus[]> {
  return request("/api/v1/compare");
}

export function buildCompareDownloadUrl(path: string): string {
  return `${resolveBaseUrl()}${path}`;
}

// --- 分层加载类型 ---

export interface MatchSummaryItem {
  id: string;
  category: CompareCategoryId;
  label: string;
  color: string;
  length: number;
  fileIndices: number[];
  occurrenceCount: number;
  preview: string;
  perFileCounts?: Record<string, number>;
}

export interface MatchPagination {
  category: CompareCategoryId;
  page: number;
  pageSize: number;
  minLength: number;
  totalInCategory: number;
  totalPages: number;
  categoryCounts: Record<string, number>;
}

export interface CompareSummaryResponse {
  reviewId: string;
  summary: CompareSummary;
  matches: MatchSummaryItem[];
  matchPagination: MatchPagination;
  categories: CompareCategory[];
  downloads: { files: Record<string, string> };
  artifacts: { reviewDir: string; downloadNames: Record<string, string> };
}

export interface FileContext {
  fileIndex: number;
  name: string;
  totalBlocks: number;
  matchBlockIndex: number;
  blocks: CompareDocumentBlock[];
}

export interface CompareContextResponse {
  match: MatchSummaryItem & { text?: string };
  fileContexts: FileContext[];
}

// --- 分层加载 API ---

export function getCompareSummary(
  reviewId: string,
  category?: CompareCategoryId,
  page = 1,
  pageSize = 100,
  minLength = 0,
): Promise<CompareSummaryResponse> {
  const cat = category || "paragraph";
  const params = new URLSearchParams({
    category: cat,
    page: String(page),
    page_size: String(pageSize),
    min_length: String(Math.max(0, Math.floor(minLength))),
  });
  return request(`/api/v1/compare/${reviewId}/summary?${params.toString()}`);
}

export function getCompareContext(
  reviewId: string,
  matchId: string,
  surrounding = 3,
): Promise<CompareContextResponse> {
  return request(
    `/api/v1/compare/${reviewId}/context?matchId=${encodeURIComponent(matchId)}&surrounding=${surrounding}`,
  );
}

export function retryCompareRun(reviewId: string): Promise<CompareSubmitResponse> {
  return request(`/api/v1/compare/${reviewId}/retry`, { method: "POST" });
}
