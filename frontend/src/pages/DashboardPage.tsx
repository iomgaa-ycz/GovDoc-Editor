import { ArrowRight, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getDashboardStats } from "@/api/v3";
import type { DashboardStats, RecentProject } from "@/types/ui";
import { useWorkbench } from "@/context/V3WorkbenchContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/MetricCard";

const AUDIT_STATUS_LABEL: Record<string, string> = { idle: "未开始", running: "审查中", completed: "已完成" };
const AUDIT_STATUS_VARIANT: Record<string, "muted" | "default" | "ok"> = { idle: "muted", running: "default", completed: "ok" };

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const navigate = useNavigate();
  const { auditRuns, setSelectedAuditRunId } = useWorkbench();

  function findLatestAuditRun(projectId: string) {
    return auditRuns.find((r) => r.project_id === projectId);
  }

  function goToAuditResult(projectId: string) {
    const run = findLatestAuditRun(projectId);
    if (!run) return;
    setSelectedAuditRunId(run.id);
    navigate("/audit-results");
  }

  useEffect(() => { getDashboardStats().then(setStats).catch(() => {}); }, []);

  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">工作台总览</span>
      </header>
      <div className="flex-1 space-y-6 p-7">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">项目审查工作台</h2>
            <p className="text-sm text-text-muted">总共 {stats?.checkpoint_count ?? 0} 个审核要点，覆盖 {stats?.recent_projects.length ?? 0} 个项目</p>
          </div>
          <Link to="/ai-review"><Button><Plus className="h-4 w-4" />创建审查任务</Button></Link>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="审核要点" value={stats?.checkpoint_count ?? 0} tone="blue" />
          <MetricCard label="完成审核" value={stats?.completed_audit_count ?? 0} tone="green" />
          <MetricCard label="发现问题" value={stats?.finding_count ?? 0} tone="amber" />
          <MetricCard label="工作底稿" value={stats?.workpaper_count ?? 0} tone="slate" />
        </div>
        <div className="grid grid-cols-3 gap-5 flex-1">
          <Card className="col-span-2">
            <CardHeader><CardTitle>近期审核记录</CardTitle></CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>项目名称</TableHead>
                    <TableHead>审核要点</TableHead>
                    <TableHead>发现问题</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(stats?.recent_projects ?? []).map((p: RecentProject) => {
                    const latestRun = findLatestAuditRun(p.project_id);
                    return (
                      <TableRow key={p.project_id}>
                        <TableCell className="font-medium">{p.name}</TableCell>
                        <TableCell>{p.point_count}</TableCell>
                        <TableCell>{p.issue_count}</TableCell>
                        <TableCell>
                          <Badge variant={AUDIT_STATUS_VARIANT[p.audit_status] ?? "muted"}>
                            {AUDIT_STATUS_LABEL[p.audit_status] ?? p.audit_status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <button
                            disabled={!latestRun}
                            onClick={() => goToAuditResult(p.project_id)}
                            className="text-accent hover:underline disabled:cursor-not-allowed disabled:text-text-muted disabled:no-underline"
                            aria-label={`查看 ${p.name} 的审核结果`}
                            title={latestRun ? "查看审核结果" : "暂无可查看的审核运行"}
                          >
                            <ArrowRight className="h-4 w-4" />
                          </button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {(stats?.recent_projects ?? []).length === 0 && (
                    <TableRow><TableCell colSpan={5} className="text-center text-text-muted py-8">暂无审核记录</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>审查情况</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {(stats?.recent_projects ?? []).map((p: RecentProject) => (
                <div key={p.project_id} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${p.audit_status === "completed" ? "bg-status-ok" : p.audit_status === "running" ? "bg-accent" : "bg-text-muted"}`} />
                    <span className="text-sm text-text-primary">{p.name}</span>
                  </div>
                  <span className="text-xs text-text-muted">{p.issue_count > 0 ? `${p.issue_count} 项问题` : "无问题"}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
