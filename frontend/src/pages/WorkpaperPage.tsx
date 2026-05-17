import { Download, FileDown, FileText, Save } from "lucide-react";
import { Link } from "react-router-dom";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { getWorkpaperFinalDocxUrl } from "@/api/v3";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { WorkpaperEditor } from "@/components/WorkpaperEditor";
import { EmptyState } from "@/components/EmptyState";

export function WorkpaperPage() {
  const {
    activeAuditRun, auditRuns, selectedAuditRunId, setSelectedAuditRunId,
    workpaperHtml, workpaperJson, workpaperSaveStatus, finalizeStatus,
    loadWorkpaper, setWorkpaperHtml, finalizeWorkpaper,
  } = useWorkbench();

  async function handleSelectRun(id: string) {
    setSelectedAuditRunId(id || null);
    if (id) await loadWorkpaper(id);
  }

  function handleExport() {
    if (!activeAuditRun) return;
    window.open(getWorkpaperFinalDocxUrl(activeAuditRun.id), "_blank");
  }

  if (!activeAuditRun && auditRuns.length === 0) {
    return (
      <div className="flex flex-col h-screen">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <span className="text-base font-semibold text-text-primary">工作底稿</span>
        </header>
        <div className="flex-1 flex items-center justify-center">
          <EmptyState
            icon={<FileText className="h-7 w-7 text-accent" />}
            title="暂无工作底稿"
            description="完成一次审查任务后，系统将自动生成工作底稿"
            action={
              <div className="flex gap-3">
                <Link to="/ai-review"><Button>创建审查任务</Button></Link>
                <Link to="/audit-results"><Button variant="secondary">查看历史记录</Button></Link>
              </div>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <div className="flex items-center gap-3">
          <span className="text-base font-semibold text-text-primary">工作底稿</span>
          <Select value={selectedAuditRunId ?? ""} onValueChange={handleSelectRun}>
            <SelectTrigger className="w-48"><SelectValue placeholder="选择审核运行" /></SelectTrigger>
            <SelectContent>
              {auditRuns.map((r) => <SelectItem key={r.id} value={r.id}>{r.project_name || r.id.slice(0, 8)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm"><Save className="h-4 w-4" /> 保存</Button>
          <Button variant="secondary" size="sm" disabled={finalizeStatus === "finalizing"} onClick={() => activeAuditRun && finalizeWorkpaper(activeAuditRun.id)}>
            <FileDown className="h-4 w-4" /> {finalizeStatus === "finalizing" ? "定稿中..." : "定稿"}
          </Button>
          <Button size="sm" disabled={finalizeStatus !== "finalized"} onClick={handleExport}>
            <Download className="h-4 w-4" /> 导出 Word
          </Button>
        </div>
      </header>
      <div className="flex flex-1 overflow-hidden p-6 gap-5">
        <Card className="flex-1 overflow-auto">
          {activeAuditRun ? (
            <WorkpaperEditor value={workpaperHtml} onChange={setWorkpaperHtml} />
          ) : (
            <div className="flex items-center justify-center h-full text-text-muted text-sm">请先选择一个审核运行</div>
          )}
        </Card>
        <div className="w-72 shrink-0 space-y-4">
          <Card>
            <CardHeader><CardTitle>文档信息</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-muted">保存状态</span>
                <Badge variant={workpaperSaveStatus === "saved" ? "ok" : workpaperSaveStatus === "error" ? "err" : "muted"}>
                  {workpaperSaveStatus === "saving" ? "保存中" : workpaperSaveStatus === "saved" ? "已保存" : workpaperSaveStatus === "error" ? "保存失败" : "未保存"}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">定稿状态</span>
                <Badge variant={finalizeStatus === "finalized" ? "ok" : finalizeStatus === "error" ? "err" : "muted"}>
                  {finalizeStatus === "finalizing" ? "定稿中" : finalizeStatus === "finalized" ? "已定稿" : finalizeStatus === "error" ? "定稿失败" : "未定稿"}
                </Badge>
              </div>
              {workpaperJson && (
                <div className="flex justify-between">
                  <span className="text-text-muted">发现数量</span>
                  <span>{workpaperJson.findings.length} 条</span>
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>使用说明</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-text-muted leading-relaxed">工作底稿由 AI 自动生成，支持富文本编辑。编辑内容会自动保存。定稿后可导出为 Word 文档。</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
