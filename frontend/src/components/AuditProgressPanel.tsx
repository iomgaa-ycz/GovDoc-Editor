/**
 * AuditProgressPanel
 * ------------------
 * AIReviewPage 中 / 右两列的"审核进度视图"聚合组件，包含：
 *   1. 中列：审核进度卡（ProgressBar + MetricCard × 4）与运行日志卡（LogConsole）
 *   2. 右列：审核点进度列表（per-point-run + 重试按钮） / 无数据 EmptyState
 *
 * 设计要点：
 *   1. 纯展示组件：不调用 useWorkbench；容器经 props 注入 auditProgress / logs /
 *      finalCheckpoints 派生的 helper / retry handler / 点击 point-run 的回调。
 *   2. 列容器 CSS 类名（center-column / right-column）由本组件持有，以保持
 *      triple-layout 在 AIReviewPage 中的 DOM 结构与拆分前一致。
 *   3. 文案与所有 class/ARIA 与拆分前逐字一致，以兼容行为护栏测试（MetricCard
 *      label/value 结构、审核进度 / 审核点进度 两个 card title 等）。
 *   4. 已知遗留：最外层是 <button>，内部的「重试」Button 也会渲染为 <button>；
 *      该嵌套 button 问题属 P1a 范围外的历史坑（plan 注明不修），保留现状。
 */

import { RefreshCw } from "lucide-react";

import type { AuditPointRun, AuditRunProgress, CheckpointItem, GovCheckpointPayload, LogEntry } from "../types/ui";
import { parseFindingJson, verdictToStatus } from "../adapters/backendToUi";
import { Button, Card, CardHeader, EmptyState, LogConsole, MetricCard, ProgressBar, StatPill } from "./Ui";

/** 已审批 final 审核点（parsed 字段为非空 payload）*/
export type FinalCheckpoint = CheckpointItem & { parsed: GovCheckpointPayload };

export interface AuditProgressPanelProps {
  /** 当前审核进度（null 时显示 EmptyState） */
  auditProgress: AuditRunProgress | null;
  /** 运行日志列表（长度 0 时隐藏日志卡） */
  logs: LogEntry[];
  /** final 审核点列表，用于把 point_run 映射回展示标题 */
  finalCheckpoints: FinalCheckpoint[];
  /** 触发重试单个 point run */
  retryPointRun: (pointRunId: string) => void;
  /** 点击某个 point run（用于打开详情 Modal） */
  onPointRunClick: (pointRunId: string) => void;
}

export function AuditProgressPanel(props: AuditProgressPanelProps) {
  const { auditProgress, logs, finalCheckpoints, retryPointRun, onPointRunClick } = props;

  // 与拆分前派生口径一致
  const completedCount = auditProgress?.point_runs.filter((pr) => pr.status === "completed").length ?? 0;
  const failedCount = auditProgress?.point_runs.filter((pr) => pr.status === "failed").length ?? 0;
  const pendingCount = auditProgress?.point_runs.filter(
    (pr) => pr.status === "pending" || pr.status === "running",
  ).length ?? 0;
  const total = auditProgress?.total_count ?? 0;

  return (
    <>
      {/* Center: Progress */}
      <div className="center-column">
        <Card>
          <CardHeader title="审核进度" />
          {auditProgress ? (
            <>
              <ProgressBar value={total > 0 ? (completedCount / total) * 100 : 0} />
              <div className="metric-grid">
                <MetricCard label="总计" value={total} tone="blue" />
                <MetricCard label="已完成" value={completedCount} tone="green" />
                <MetricCard label="失败" value={failedCount} tone="amber" />
                <MetricCard label="待处理" value={pendingCount} />
              </div>
            </>
          ) : (
            <EmptyState title="尚未启动" description="请在左侧配置任务后启动审核。" />
          )}
        </Card>

        {logs.length > 0 && (
          <Card>
            <CardHeader title="运行日志" />
            <LogConsole logs={logs} />
          </Card>
        )}
      </div>

      {/* Right: Point status list */}
      <div className="right-column">
        <Card>
          <CardHeader title="审核点进度" />
          {auditProgress && auditProgress.point_runs.length > 0 ? (
            <div className="review-point-list">
              {auditProgress.point_runs.map((pr: AuditPointRun) => {
                const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
                const title = cp?.parsed?.title ?? pr.checkpoint_final_id.slice(0, 8);
                const status = verdictToStatus(
                  parseFindingJson(pr.finding_json),
                  pr.status,
                );
                const statusClass =
                  status === "running" ? "review-point-item--running"
                  : status === "passed" ? "review-point-item--passed"
                  : status === "error" ? "review-point-item--failed"
                  : "";
                return (
                  <button
                    key={pr.id}
                    className={`review-point-item ${statusClass}`}
                    type="button"
                    onClick={() => onPointRunClick(pr.id)}
                  >
                    <div className="review-point-copy">
                      <strong>{title}</strong>
                      <span>
                        <StatPill status={status} />
                      </span>
                    </div>
                    {status === "error" && (
                      <Button
                        size="sm"
                        tone="ghost"
                        icon={RefreshCw}
                        onClick={(e) => { e.stopPropagation(); retryPointRun(pr.id); }}
                      >
                        重试
                      </Button>
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            <EmptyState title="无审核点" description="启动审核后这里将显示每个审核点的状态。" />
          )}
        </Card>
      </div>
    </>
  );
}
