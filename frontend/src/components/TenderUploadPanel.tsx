/**
 * TenderUploadPanel
 * -----------------
 * AIReviewPage「任务设置」卡片的前半段：项目选择 / 新建项目 / 招标文书上传 /
 * 上传成功提示。
 *
 * 设计要点：
 *   1. 纯展示组件：不直接调用 useWorkbench，所有状态与 handler 由调用方
 *      （AIReviewPage 容器）经 props 传入，保持组件可测试、可复用。
 *   2. 文案与 DOM 结构与拆分前 AIReviewPage 保持逐字一致，以兼容现有行为
 *      护栏测试（tests/pages/AIReviewPage.test.tsx）。
 *   3. 条件分支：
 *        - `activeProject && !tenderDoc` → 渲染上传区
 *        - `tenderDoc` → 渲染成功提示
 *      与原实现一致。
 */

import type { ChangeEvent } from "react";

import type { Project, TenderDoc } from "../types/ui";
import { Button, Field, FileDropzone, InlineNotice, SelectInput, TextInput } from "./Ui";

export interface TenderUploadPanelProps {
  /** 可选项目列表 */
  projects: Project[];
  /** 当前活动项目（决定上传/成功提示的展示） */
  activeProject: Project | undefined;
  /** 当前选中的项目 ID（SelectInput 受控值） */
  selectedProjectId: string | null;
  /** 切换选中项目 */
  setSelectedProjectId: (id: string | null) => void;
  /** 当前活动项目已上传的招标文书（未上传时为 undefined） */
  tenderDoc: TenderDoc | undefined;
  /** 新项目名称输入框值 */
  newProjectName: string;
  /** 更新新项目名称 */
  setNewProjectName: (v: string) => void;
  /** 正在创建项目 */
  creating: boolean;
  /** 触发创建项目 */
  handleCreateProject: () => void;
  /** 待上传的招标文书 File（未选择时为 null） */
  tenderFile: File | null;
  /** 更新待上传文件 */
  setTenderFile: (f: File | null) => void;
  /** 正在上传招标文书 */
  uploadingTender: boolean;
  /** 触发上传招标文书 */
  handleUploadTender: () => void;
}

export function TenderUploadPanel(props: TenderUploadPanelProps) {
  const {
    projects,
    activeProject,
    selectedProjectId,
    setSelectedProjectId,
    tenderDoc,
    newProjectName,
    setNewProjectName,
    creating,
    handleCreateProject,
    tenderFile,
    setTenderFile,
    uploadingTender,
    handleUploadTender,
  } = props;

  return (
    <>
      <Field label="项目">
        <SelectInput
          value={selectedProjectId ?? ""}
          onChange={(e: ChangeEvent<HTMLSelectElement>) =>
            setSelectedProjectId(e.target.value || null)
          }
        >
          <option value="">选择项目</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </SelectInput>
      </Field>
      <Field label="新项目名称">
        <div style={{ display: "flex", gap: 8 }}>
          <TextInput
            placeholder="输入项目名称"
            value={newProjectName}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setNewProjectName(e.target.value)}
            style={{ flex: 1 }}
          />
          <Button size="sm" tone="secondary" onClick={handleCreateProject} busy={creating} disabled={!newProjectName}>新建</Button>
        </div>
      </Field>

      {activeProject && !tenderDoc && (
        <>
          <Field label="上传招标文书">
            {tenderFile ? (
              <div className="file-chip-list">
                <div className="file-chip">
                  <div>
                    <strong>{tenderFile.name}</strong>
                    <span>{(tenderFile.size / 1024).toFixed(1)} KB</span>
                  </div>
                </div>
              </div>
            ) : (
              <FileDropzone
                title="选择招标文书"
                subtitle="支持 .pdf, .docx, .md"
                accept=".pdf,.docx,.md,.txt"
                onSelect={(files) => setTenderFile(files[0] ?? null)}
              />
            )}
          </Field>
          {tenderFile && (
            <Button tone="primary" onClick={handleUploadTender} busy={uploadingTender}>
              上传文书
            </Button>
          )}
        </>
      )}

      {tenderDoc && (
        <InlineNotice tone="success" message={`文书已上传: ${tenderDoc.filename}`} />
      )}
    </>
  );
}
