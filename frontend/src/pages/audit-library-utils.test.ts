import { describe, expect, it } from "vitest";
import { countUncategorized, isUncategorized, stripExt } from "./audit-library-utils";
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

describe("stripExt", () => {
  it("去掉最后一个扩展名", () => {
    expect(stripExt("a.doc")).toBe("a");
    expect(stripExt("政府采购法.docx")).toBe("政府采购法");
    expect(stripExt("报告.final.pdf")).toBe("报告.final");
  });
  it("无扩展名或前导点文件原样返回", () => {
    expect(stripExt("noext")).toBe("noext");
    expect(stripExt(".env")).toBe(".env");
  });
});
