import { Download, FileDown, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import { getWorkpaperFinalDocxUrl } from "../api/v3";
import { formatAuditRunOptionLabel } from "../utils/auditRunLabel";
import { AuditRunCurrentInfo } from "../components/AuditRunCurrentInfo";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  InlineNotice,
  PageHero,
  SelectInput,
} from "../components/Ui";
import { WorkpaperEditor } from "../components/WorkpaperEditor";

export function WorkpaperPage() {
  const {
    activeAuditRun,
    auditRuns,
    selectedAuditRunId,
    setSelectedAuditRunId,
    workpaperHtml,
    workpaperJson,
    workpaperSaveStatus,
    finalizeStatus,
    projects,
    auditInputDocs,
    loadWorkpaper,
    clearWorkpaper,
    setWorkpaperHtml,
    saveWorkpaper,
    finalizeWorkpaper,
  } = useWorkbench();

  const [loadingRunId, setLoadingRunId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [requestedRunId, setRequestedRunId] = useState<string | null>(null);

  const handleSelectRun = useCallback(async (id: string) => {
    const nextId = id || null;
    setSelectedAuditRunId(nextId);
    setLoadError(null);
    setRequestedRunId(nextId);

    if (!nextId) {
      setLoadingRunId(null);
      clearWorkpaper();
      return;
    }

    setLoadingRunId(nextId);
    try {
      await loadWorkpaper(nextId);
    } catch {
      setLoadError("该审核运行尚未生成工作底稿。");
    } finally {
      setLoadingRunId((current) => (current === nextId ? null : current));
    }
  }, [clearWorkpaper, loadWorkpaper, setSelectedAuditRunId]);

  async function handleSave() {
    await saveWorkpaper();
  }

  async function handleFinalize() {
    if (!activeAuditRun) return;
    await finalizeWorkpaper(activeAuditRun.id);
  }

  function handleExport() {
    if (!activeAuditRun) return;
    const url = getWorkpaperFinalDocxUrl(activeAuditRun.id);
    window.open(url, "_blank");
  }

  const isLoadingSelectedRun = Boolean(selectedAuditRunId && loadingRunId === selectedAuditRunId);

  useEffect(() => {
    if (!selectedAuditRunId || !activeAuditRun) return;
    if (
      workpaperJson ||
      loadingRunId === selectedAuditRunId ||
      loadError ||
      requestedRunId === selectedAuditRunId
    ) return;
    void handleSelectRun(selectedAuditRunId);
  }, [
    selectedAuditRunId,
    activeAuditRun,
    workpaperJson,
    loadingRunId,
    loadError,
    requestedRunId,
    handleSelectRun,
  ]);

  return (
    <>
      <PageHero
        eyebrow="结果与工作底稿"
        title="工作底稿编辑"
        description="查看和编辑审核生成的工作底稿。"
        actions={
          <div className="audit-run-select">
            <SelectInput
              value={selectedAuditRunId ?? ""}
              onChange={(e) => handleSelectRun(e.target.value)}
              style={{ minWidth: 0 }}
            >
              <option value="">选择审核运行</option>
              {auditRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {formatAuditRunOptionLabel({ run: r, projects, auditInputDocs })}
                </option>
              ))}
            </SelectInput>
          </div>
        }
      />

      <AuditRunCurrentInfo
        run={activeAuditRun}
        projects={projects}
        auditInputDocs={auditInputDocs}
      />

      <div className="document-layout">
        {/* Main: editor */}
        <div className="center-column">
          <Card>
            {!activeAuditRun ? (
              <div style={{ padding: 40 }}>
                <EmptyState title="请选择审核运行" description="选择一次审核运行后，可查看和编辑对应工作底稿。" />
              </div>
            ) : isLoadingSelectedRun ? (
              <div style={{ padding: 40 }}>
                <EmptyState title="正在加载工作底稿" description="正在读取该次审核运行生成的工作底稿。" />
              </div>
            ) : loadError ? (
              <div style={{ padding: 40 }}>
                <EmptyState title="暂无工作底稿" description={loadError} />
              </div>
            ) : (
              <WorkpaperEditor value={workpaperHtml} onChange={setWorkpaperHtml} />
            )}
          </Card>
        </div>

        {/* Sidebar: actions */}
        <div className="document-side">
          <Card>
            <CardHeader title="操作" />
            <div className="stack-gap">
              <Button
                tone="primary"
                icon={Save}
                onClick={handleSave}
                disabled={!activeAuditRun || isLoadingSelectedRun || !workpaperJson}
                style={{ width: "100%" }}
              >
                保存草稿
              </Button>
              <Button
                tone="secondary"
                icon={Download}
                onClick={handleExport}
                disabled={!activeAuditRun || isLoadingSelectedRun || finalizeStatus !== "finalized"}
                style={{ width: "100%" }}
              >
                导出 Word
              </Button>
              <Button
                tone="secondary"
                icon={FileDown}
                onClick={handleFinalize}
                disabled={!activeAuditRun || isLoadingSelectedRun || Boolean(loadError) || finalizeStatus === "finalizing"}
                style={{ width: "100%" }}
              >
                {finalizeStatus === "finalizing" ? "定稿中..." : "定稿"}
              </Button>
            </div>
          </Card>

          {workpaperSaveStatus === "saving" && (
            <InlineNotice tone="info" message="保存中..." />
          )}
          {workpaperSaveStatus === "saved" && (
            <InlineNotice tone="success" message="已保存" />
          )}
          {workpaperSaveStatus === "error" && (
            <InlineNotice tone="warning" message="保存失败" />
          )}
          {finalizeStatus === "finalizing" && (
            <InlineNotice tone="info" message="定稿中，请稍候..." />
          )}
          {finalizeStatus === "finalized" && (
            <InlineNotice tone="success" message="已定稿，可导出 Word。" />
          )}
          {finalizeStatus === "error" && (
            <InlineNotice tone="warning" message="定稿失败" />
          )}

          <Card>
            <CardHeader title="说明" />
            <p className="side-copy">
              工作底稿由 AI 自动生成，支持富文本编辑。编辑后可保存草稿或直接定稿。定稿后可导出 Word 文档。
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}
