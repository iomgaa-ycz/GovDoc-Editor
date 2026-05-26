/**
 * useAuditRun
 * -----------
 * 封装"启动一次审核运行"所需的本地 UI 状态与 handler。
 *
 * 范围说明（比 plan 更窄）：
 *   plan 原始措辞暗含"整体 audit run 生命周期"，但 auditProgress / 轮询 /
 *   total / processed 等状态已由 WorkbenchContext 统一维护。本 hook 只关心
 *   启动前的 UI 决策：
 *     - 勾选哪些审核点（selectedCpIds + toggleCheckpoint）
 *     - 启动中 busy 态（startingAudit）
 *     - 触发 ctx.createAuditRun(...) 的 handler
 *   轮询/进度不在此 hook 内重复实现，避免与 context 双写。
 *
 * 设计要点：
 *   hook 内部从 useWorkbench() 读取 activeProject / auditInputDocs / createAuditRun，
 *   并自行解析当前主文书和附件 ID。
 */

import { useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";

interface AuditInputDocumentRef {
  id: string;
}

interface AuditInputDocs {
  mainDoc?: AuditInputDocumentRef;
  supplementaryDocs: AuditInputDocumentRef[];
}

export interface AuditRunController {
  /** 当前已勾选的审核点 ID 列表 */
  selectedCpIds: string[];
  /** 切换单个审核点的选中态 */
  toggleCheckpoint: (id: string) => void;
  /** 正在调用 createAuditRun */
  startingAudit: boolean;
  /**
   * 触发启动审核；以下任一条件都会直接 no-op：
   *   - 无 activeProject
   *   - 无 mainDoc（当前活动项目尚未上传主文书）
   *   - 未勾选任何审核点
   */
  handleStartAudit: () => Promise<void>;
}

export function useAuditRun(): AuditRunController {
  const { activeProject, auditInputDocs, createAuditRun } = useWorkbench();

  const [selectedCpIds, setSelectedCpIds] = useState<string[]>([]);
  const [startingAudit, setStartingAudit] = useState<boolean>(false);

  function toggleCheckpoint(id: string): void {
    setSelectedCpIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function handleStartAudit(): Promise<void> {
    const inputDocs = activeProject
      ? (auditInputDocs[activeProject.id] as AuditInputDocs | undefined)
      : undefined;
    const mainDoc = inputDocs?.mainDoc;
    const supplementaryDocIds = inputDocs?.supplementaryDocs.map((doc) => doc.id) ?? [];
    if (!activeProject || !mainDoc || selectedCpIds.length === 0) return;
    setStartingAudit(true);
    try {
      await createAuditRun(activeProject.id, mainDoc.id, supplementaryDocIds, selectedCpIds);
    } finally {
      setStartingAudit(false);
    }
  }

  return {
    selectedCpIds,
    toggleCheckpoint,
    startingAudit,
    handleStartAudit,
  };
}
