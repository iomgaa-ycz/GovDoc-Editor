import { describe, expect, it, vi } from "vitest";

import { getCompareSummary, type MatchSummaryItem } from "./compare";

describe("compare API", () => {
  it("固定摘要匹配类型契约，编译期校验聚类计数字段", () => {
    // 该字面量主要用于 TypeScript 编译期把关：后端 summary.json 必须继续提供 perFileCounts。
    const summaryItem: MatchSummaryItem = {
      id: "match-1",
      category: "similar",
      label: "近似段落组",
      color: "#9b59b6",
      length: 4,
      fileIndices: [0, 1],
      occurrenceCount: 3,
      preview: "代表段落",
      perFileCounts: { "0": 1, "1": 2 },
    };

    expect(summaryItem.perFileCounts?.["1"]).toBe(2);
  });

  it("getCompareSummary 把当前长度阈值传给后端", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        reviewId: "review-1",
        summary: {
          fileCount: 2,
          files: [],
          commonParagraphCount: 0,
          commonSentenceCount: 0,
          commonSegmentCount: 0,
          commonSimilarCount: 0,
          matchCount: 0,
          minSegmentLength: 16,
        },
        matches: [],
        matchPagination: {
          category: "paragraph",
          page: 2,
          pageSize: 25,
          minLength: 17,
          totalInCategory: 0,
          totalPages: 0,
          categoryCounts: {},
        },
        categories: [],
        downloads: { files: {} },
        artifacts: { reviewDir: "", downloadNames: {} },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getCompareSummary("review-1", "paragraph", 2, 25, 17);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/compare/review-1/summary?category=paragraph&page=2&page_size=25&min_length=17",
      undefined,
    );
  });
});
