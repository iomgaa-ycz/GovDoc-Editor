/**
 * TenderUploadPanel
 * -----------------
 * AIReviewPage「任务设置」卡片的前半段：项目选择 / 新建项目 / 招标文书上传 /
 * 上传成功提示。
 *
 * 设计要点：
 *   1. 纯展示组件：不直接调用 useWorkbench，所有状态与 handler 由调用方
 *      （AIReviewPage 容器）经 props 传入，保持组件可测试、可复用。
 *   2. 区分主招标文书与补充文件，上传语义由容器注入。
 */

import { Trash2 } from "lucide-react";
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
  /** 当前活动项目已上传的主招标文书（未上传时为 undefined） */
  mainDoc: TenderDoc | undefined;
  /** 当前活动项目已上传的附件列表 */
  supplementaryDocs: TenderDoc[];
  /** 新项目名称输入框值 */
  newProjectName: string;
  /** 更新新项目名称 */
  setNewProjectName: (v: string) => void;
  /** 正在创建项目 */
  creating: boolean;
  /** 触发创建项目 */
  handleCreateProject: () => void;
  /** 待上传的主招标文书 File（未选择时为 null） */
  mainTenderFile: File | null;
  /** 更新待上传主文书 */
  setMainTenderFile: (f: File | null) => void;
  /** 待上传附件列表 */
  supplementaryFiles: File[];
  /** 更新待上传附件列表 */
  setSupplementaryFiles: (files: File[]) => void;
  /** 正在上传招标文书 */
  uploadingTender: boolean;
  /** 触发上传招标文书 */
  handleUploadTender: () => void;
  /** 上传失败的错误消息 */
  uploadError: string | null;
}

export function TenderUploadPanel(props: TenderUploadPanelProps) {
  const {
    projects,
    activeProject,
    selectedProjectId,
    setSelectedProjectId,
    mainDoc,
    supplementaryDocs,
    newProjectName,
    setNewProjectName,
    creating,
    handleCreateProject,
    mainTenderFile,
    setMainTenderFile,
    supplementaryFiles,
    setSupplementaryFiles,
    uploadingTender,
    handleUploadTender,
    uploadError,
  } = props;

  function fileKey(file: File) {
    return `${file.name}-${file.size}-${file.lastModified}`;
  }

  function handleSelectSupplementaryFiles(files: File[]) {
    const seen = new Set<string>();
    const merged = [...supplementaryFiles, ...files].filter((file) => {
      const key = fileKey(file);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    setSupplementaryFiles(merged);
  }

  function removeSupplementaryFile(target: File) {
    const targetKey = fileKey(target);
    setSupplementaryFiles(
      supplementaryFiles.filter((file) => fileKey(file) !== targetKey),
    );
  }

  function DeleteFileButton(props: { label: string; onDelete: () => void | Promise<void> }) {
    return (
      <button
        className="icon-button"
        type="button"
        aria-label={props.label}
        title={props.label}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          void props.onDelete();
        }}
      >
        <Trash2 size={14} />
      </button>
    );
  }

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

      {activeProject && (
        <>
          <Field label="上传主招标文书">
            {mainDoc ? (
              <div className="file-chip-list">
                <div className="file-chip">
                  <div>
                    <strong>{mainDoc.filename}</strong>
                    <span>已上传</span>
                  </div>
                </div>
              </div>
            ) : mainTenderFile ? (
              <div className="file-chip-list">
                <div className="file-chip">
                  <div>
                    <strong>{mainTenderFile.name}</strong>
                    <span>{(mainTenderFile.size / 1024).toFixed(1)} KB</span>
                  </div>
                  <DeleteFileButton
                    label="移除待上传主文书"
                    onDelete={() => setMainTenderFile(null)}
                  />
                </div>
              </div>
            ) : (
              <FileDropzone
                title="选择招标文书"
                subtitle="支持 .pdf, .docx, .md"
                accept=".pdf,.docx,.md,.txt"
                onSelect={(files) => setMainTenderFile(files[0] ?? null)}
              />
            )}
          </Field>
          <Field label="上传补充文件 / 变更公告 / 答疑纪要">
            {supplementaryDocs.length > 0 || supplementaryFiles.length > 0 ? (
              <div className="file-chip-list">
                {supplementaryDocs.map((doc) => (
                  <div className="file-chip" key={doc.id}>
                    <div>
                      <strong>{doc.filename}</strong>
                      <span>已上传附件</span>
                    </div>
                  </div>
                ))}
                {supplementaryFiles.map((file) => (
                  <div className="file-chip" key={fileKey(file)}>
                    <div>
                      <strong>{file.name}</strong>
                      <span>{(file.size / 1024).toFixed(1)} KB</span>
                    </div>
                    <DeleteFileButton
                      label={`移除待上传补充文件 ${file.name}`}
                      onDelete={() => removeSupplementaryFile(file)}
                    />
                  </div>
                ))}
              </div>
            ) : null}
            <FileDropzone
              title="选择补充文件"
              subtitle="可多选，支持 .pdf, .docx, .md"
              accept=".pdf,.docx,.md,.txt"
              multiple
              onSelect={handleSelectSupplementaryFiles}
            />
          </Field>

          {(mainTenderFile || supplementaryFiles.length > 0) && (
            <Button tone="primary" onClick={handleUploadTender} busy={uploadingTender}>
              上传文书
            </Button>
          )}
          {uploadError && <InlineNotice tone="error" message={uploadError} />}
        </>
      )}

      {mainDoc && (
        <>
          <InlineNotice
            tone="success"
            message={`文书已上传: ${mainDoc.filename}${supplementaryDocs.length > 0 ? `，附件 ${supplementaryDocs.length} 个` : ""}`}
          />
          {mainDoc.warnings && mainDoc.warnings.length > 0 && (
            <InlineNotice tone="warning" message={mainDoc.warnings.join("；")} />
          )}
        </>
      )}
    </>
  );
}
