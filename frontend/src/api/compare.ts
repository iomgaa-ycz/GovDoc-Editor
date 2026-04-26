import { request } from "./v3";

export type CompareCategoryId = "paragraph" | "sentence" | "segment";

export interface CompareCategory {
  id: CompareCategoryId;
  label: string;
  color: string;
}

export interface CompareSummary {
  firstFileName: string;
  secondFileName: string;
  firstParagraphCount: number;
  secondParagraphCount: number;
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
  name: string;
  blockCount: number;
  blocks: CompareDocumentBlock[];
}

export interface CompareOccurrenceSegment {
  blockId: string;
  blockIndex: number;
  start: number;
  end: number;
}

export interface CompareOccurrence {
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
  firstOccurrences: CompareOccurrence[];
  secondOccurrences: CompareOccurrence[];
  firstCount: number;
  secondCount: number;
}

export interface CompareResponse {
  reviewId: string;
  summary: CompareSummary;
  documents: {
    first: CompareDocument;
    second: CompareDocument;
  };
  matches: CompareMatch[];
  categories: CompareCategory[];
  downloads: {
    first: string;
    second: string;
  };
  artifacts: {
    reviewDir: string;
    firstDownloadName: string;
    secondDownloadName: string;
  };
}

function resolveBaseUrl(): string {
  return import.meta.env.VITE_GOVDOC_API_BASE_URL || "";
}

export function compareDocxFiles(
  firstFile: File,
  secondFile: File,
): Promise<CompareResponse> {
  const form = new FormData();
  form.append("first_file", firstFile);
  form.append("second_file", secondFile);
  return request("/api/v1/compare", {
    method: "POST",
    body: form,
  });
}

export function buildCompareDownloadUrl(path: string): string {
  return `${resolveBaseUrl()}${path}`;
}
