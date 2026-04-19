import { Download, FileDown, Save } from "lucide-react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import { getWorkpaperFinalDocxUrl } from "../api/v3";
import {
  Button,
  Card,
  CardHeader,
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
    workpaperSaveStatus,
    finalizeStatus,
    loadWorkpaper,
    setWorkpaperHtml,
    finalizeWorkpaper,
  } = useWorkbench();

  async function handleSelectRun(id: string) {
    setSelectedAuditRunId(id || null);
    if (id) {
      await loadWorkpaper(id);
    }
  }

  async function handleSave() {
    // Workpaper auto-saves on edit; this is a manual trigger
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

  return (
    <>
      <PageHero
        eyebrow="结果与工作底稿"
        title="工作底稿编辑"
        description="查看和编辑审核生成的工作底稿。"
        actions={
          <div className="hero-side">
            <SelectInput
              value={selectedAuditRunId ?? ""}
              onChange={(e) => handleSelectRun(e.target.value)}
              style={{ minWidth: 200 }}
            >
              <option value="">选择审核运行</option>
              {auditRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 8)}... ({r.status})
                </option>
              ))}
            </SelectInput>
          </div>
        }
      />

      <div className="document-layout">
        {/* Main: editor */}
        <div className="center-column">
          <Card>
            {activeAuditRun ? (
              <WorkpaperEditor value={workpaperHtml} onChange={setWorkpaperHtml} />
            ) : (
              <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
                请先选择一个审核运行
              </div>
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
                disabled={!activeAuditRun}
                style={{ width: "100%" }}
              >
                保存草稿
              </Button>
              <Button
                tone="secondary"
                icon={Download}
                onClick={handleExport}
                disabled={!activeAuditRun || finalizeStatus !== "finalized"}
                style={{ width: "100%" }}
              >
                导出 Word
              </Button>
              <Button
                tone="secondary"
                icon={FileDown}
                onClick={handleFinalize}
                disabled={!activeAuditRun || finalizeStatus === "finalizing"}
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
