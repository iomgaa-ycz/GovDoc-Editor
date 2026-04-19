/**
 * CheckpointPicker
 * ----------------
 * AIReviewPage「任务设置」卡片下半段：多选待审核点 + 启动审核按钮。
 *
 * 设计要点：
 *   1. 纯展示组件：不调用 useWorkbench / useAuditRun；容器经 props 注入
 *      checkpoints / 选中集合 / handler / busy 态，保持可测试、可复用。
 *   2. 文案与 DOM 结构（含 inline style）与拆分前 AIReviewPage 逐字一致，
 *      以兼容现有行为护栏测试（启动审核按钮名称/disabled 行为）。
 *   3. 外层 `{tenderDoc && !auditProgress && ...}` 条件仍由容器持有；本组件
 *      只关心"已决定要渲染审核点选择时"的 UI。
 */

import { Play } from "lucide-react";

import type { CheckpointItem, GovCheckpointPayload } from "../types/ui";
import { Button, Field } from "./Ui";

/** 已审批 final 审核点（parsed 字段为非空 payload）*/
export type FinalCheckpoint = CheckpointItem & { parsed: GovCheckpointPayload };

export interface CheckpointPickerProps {
  /** 候选审核点列表 */
  checkpoints: FinalCheckpoint[];
  /** 当前勾选的审核点 ID 列表 */
  selectedIds: string[];
  /** 切换单个审核点选中态 */
  onToggle: (id: string) => void;
  /** 点击「启动审核」时的回调 */
  onStart: () => void;
  /** 正在调用 createAuditRun */
  startingAudit: boolean;
}

export function CheckpointPicker(props: CheckpointPickerProps) {
  const { checkpoints, selectedIds, onToggle, onStart, startingAudit } = props;

  // 与拆分前保持一致：选中数为 0 或 busy 时 disabled
  const disabled = selectedIds.length === 0 || startingAudit;

  return (
    <>
      <Field label="选择审核点">
        <div style={{ display: "grid", gap: 6, maxHeight: 200, overflow: "auto" }}>
          {checkpoints.map((cp) => (
            <label key={cp.id} style={{ display: "flex", gap: 8, alignItems: "center", cursor: "pointer", fontSize: 13 }}>
              <input
                type="checkbox"
                checked={selectedIds.includes(cp.id)}
                onChange={() => onToggle(cp.id)}
              />
              {cp.parsed.title}
            </label>
          ))}
        </div>
      </Field>
      <Button
        tone="primary"
        icon={Play}
        onClick={onStart}
        busy={startingAudit}
        disabled={disabled}
      >
        启动审核 ({selectedIds.length} 个审核点)
      </Button>
    </>
  );
}
