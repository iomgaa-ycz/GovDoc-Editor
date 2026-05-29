import type { CheckpointItem } from "@/types/ui";

/** 虚拟「未分类」库的保留 selectedLibraryId。 */
export const UNCATEGORIZED_ID = "uncategorized";

/** 一条审核点是否未归任何真实库（library_count 缺失按 0 处理）。 */
export function isUncategorized(item: CheckpointItem): boolean {
  return (item.library_count ?? 0) === 0;
}

/** 统计未分类（孤儿）审核点数量。 */
export function countUncategorized(checkpoints: CheckpointItem[]): number {
  return checkpoints.filter(isUncategorized).length;
}

/** 去掉文件名的最后一个扩展名；无扩展名或前导点（如 .env）时原样返回。 */
export function stripExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}
