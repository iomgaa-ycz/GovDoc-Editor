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
