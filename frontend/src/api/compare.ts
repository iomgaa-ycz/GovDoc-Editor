import { request } from "./v3";

export type CompareCategoryId = "paragraph" | "sentence" | "segment";

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

export interface CompareOccurrenceSegment {
  fileIndex: number;
  blockId: string;
  blockIndex: number;
  start: number;
  end: number;
}

export interface CompareOccurrence {
  fileIndex: number;
  start: number;
  end: number;
  segments: CompareOccurrenceSegment[];
}

export interface CompareMatch {
  id: string;
  category: CompareCategoryId;
  label: string;
  color: string;
  text: string;
  length: number;
  fileIndices: number[];
  occurrences: Record<string, CompareOccurrence[]>;
  perFileCounts: Record<string, number>;
  fileCount: number;
  occurrenceCount: number;
}

export interface CompareResponse {
  reviewId: string;
  summary: CompareSummary;
  documents: {
    files: CompareDocument[];
  };
  matches: CompareMatch[];
  categories: CompareCategory[];
  downloads: {
    files: Record<string, string>;
  };
  artifacts: {
    reviewDir: string;
    downloadNames: Record<string, string>;
  };
}

function resolveBaseUrl(): string {
  return import.meta.env.VITE_GOVDOC_API_BASE_URL || "";
}

export function compareFiles(files: File[]): Promise<CompareResponse> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return request("/api/v1/compare", {
    method: "POST",
    body: form,
  });
}

export function buildCompareDownloadUrl(path: string): string {
  return `${resolveBaseUrl()}${path}`;
}
