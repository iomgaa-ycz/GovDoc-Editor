import { describe, expect, it } from "vitest";
import { countUncategorized, isUncategorized } from "./audit-library-utils";
import type { CheckpointItem } from "@/types/ui";

function cp(id: string, library_count?: number): CheckpointItem {
  return { id, kind: "final", status: "final", payload_json: "{}", approved_by: null, library_count };
}

describe("audit-library-utils", () => {
  it("library_count 为 0 或缺失视为未分类", () => {
    expect(isUncategorized(cp("a", 0))).toBe(true);
    expect(isUncategorized(cp("b"))).toBe(true);
    expect(isUncategorized(cp("c", 2))).toBe(false);
  });

  it("countUncategorized 统计孤儿点数量", () => {
    expect(countUncategorized([cp("a", 0), cp("b"), cp("c", 1)])).toBe(2);
  });
});
