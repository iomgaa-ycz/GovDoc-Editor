import { Eye, Loader2, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listAuditRuns } from "@/api/v3";
import { EmptyState } from "@/components/EmptyState";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { AIReviewDrawer } from "@/pages/AIReviewDrawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { AuditRun } from "@/types/ui";

const RUNNING_STATUSES = new Set(["pending", "running", "waiting_retry", "partial_ready"]);
const COMPLETED_STATUSES = new Set(["completed", "draft_ready", "finalized"]);

function progressValue(run: AuditRun): number {
  if (run.total_count <= 0) return 0;
  return Math.round((run.processed_count / run.total_count) * 100);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function runTitle(run: AuditRun): string {
  return run.project_name || `项目 ${run.project_id.slice(0, 8)}`;
}

function runDocLabel(run: AuditRun): string {
  return `文书 ${run.main_document_id.slice(0, 8)}`;
}

export function AIReviewHubPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<AuditRun[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = () => {
    setLoading(true);
    setError(null);
    return listAuditRuns()
      .then(setRuns)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "加载审查任务失败");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    void loadRuns();
  }, []);

  const stats = useMemo(() => {
    const total = runs.length;
    const running = runs.filter((run) => RUNNING_STATUSES.has(run.status as string)).length;
    const completed = runs.filter((run) => COMPLETED_STATUSES.has(run.status as string)).length;
    const failed = runs.filter((run) => (run.status as string) === "failed").length;
    return { total, running, completed, failed };
  }, [runs]);

  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <h1 className="text-base font-semibold text-text-primary">AI 审查</h1>
        <Button onClick={() => setDrawerOpen(true)}>
          <Plus className="h-4 w-4" />
          新建审查
        </Button>
      </header>

      <main className="space-y-6 p-7">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <MetricCard label="总任务" value={stats.total} tone="blue" />
          <MetricCard label="进行中" value={stats.running} tone="amber" />
          <MetricCard label="已完成" value={stats.completed} tone="green" />
          <MetricCard label="失败" value={stats.failed} tone="red" />
        </div>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>审查任务</CardTitle>
              <p className="mt-1 text-sm text-text-muted">按创建时间展示所有 AI 审查任务</p>
            </div>
            {loading && (
              <span className="flex items-center gap-2 text-sm text-text-muted">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载中
              </span>
            )}
          </CardHeader>
          <CardContent className="p-0">
            {error && (
              <div className="mx-5 mb-4 rounded-card border border-status-err-border bg-status-err-bg px-4 py-3 text-sm text-status-err">
                {error}
              </div>
            )}

            {runs.length === 0 && !loading ? (
              <EmptyState
                title="暂无审查任务"
                description="点击右上角新建审查，上传招标文书并选择审查要点。"
                action={
                  <Button onClick={() => setDrawerOpen(true)}>
                    <Plus className="h-4 w-4" />
                    新建审查
                  </Button>
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <div className="min-w-[920px]">
                  <div className="grid grid-cols-[minmax(240px,1fr)_80px_90px_120px_130px_80px] border-b bg-surface px-5 py-2 text-xs font-medium text-text-muted">
                    <div>项目/文书</div>
                    <div>审核点</div>
                    <div>状态</div>
                    <div>进度</div>
                    <div>创建时间</div>
                    <div className="text-right">操作</div>
                  </div>

                  {runs.map((run) => {
                    const status = run.status as string;
                    const value = progressValue(run);
                    const completed = COMPLETED_STATUSES.has(status);
                    const failed = status === "failed";
                    return (
                      <div
                        key={run.id}
                        role="button"
                        tabIndex={0}
                        className="grid w-full grid-cols-[minmax(240px,1fr)_80px_90px_120px_130px_80px] items-center border-b px-5 py-3 text-left transition-colors last:border-b-0 hover:bg-surface"
                        onClick={() => navigate(`/ai-review/${run.id}`)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            navigate(`/ai-review/${run.id}`);
                          }
                        }}
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-text-primary">
                            {runTitle(run)}
                          </p>
                          <p className="mt-0.5 truncate text-xs text-text-muted">
                            {runDocLabel(run)}
                          </p>
                        </div>
                        <div>
                          <Badge variant="outline">{run.total_count}</Badge>
                        </div>
                        <div>
                          {status === "partial_ready" ? (
                            <Badge variant="warn">
                              部分完成 {run.processed_count}/{run.total_count}
                            </Badge>
                          ) : (
                            <StatusBadge status={status} />
                          )}
                        </div>
                        <div className="space-y-1">
                          <Progress
                            value={value}
                            className={cn(
                              completed && "[&>div]:bg-status-ok",
                              failed && "[&>div]:bg-status-err",
                              !completed && !failed && "[&>div]:bg-accent",
                            )}
                          />
                          <p className="text-xs text-text-muted">{value}%</p>
                        </div>
                        <div className="text-sm text-text-secondary">{formatDate(run.created_at)}</div>
                        <div className="flex justify-end">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              navigate(`/ai-review/${run.id}`);
                            }}
                          >
                            <Eye className="h-4 w-4" />
                            查看
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      <AIReviewDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onCreated={() => {
          void loadRuns();
        }}
      />
    </div>
  );
}

export default AIReviewHubPage;
