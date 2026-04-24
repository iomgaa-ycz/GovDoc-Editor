/**
 * useProjectWorkflow
 * ------------------
 * 封装"新建项目 + 上传招标文书"两段工作流的本地 UI 状态与 handler。
 *
 * 设计要点：
 *   1. 本 hook 从 useWorkbench() 内部读取 createProject / uploadTenderDoc / activeProject，
 *      调用方无需再手动串联 context。
 *   2. 业务副作用（网络 I/O）仍由 context 负责；hook 仅管理 busy 标志与输入态。
 *   3. 对 AIReviewPage 调用端保持零语义差异：返回字段名沿用原 state/ handler 命名。
 */

import { useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";

export interface ProjectWorkflow {
  /** 新项目名称输入框当前值 */
  newProjectName: string;
  /** 更新新项目名称 */
  setNewProjectName: (v: string) => void;
  /** 待上传的招标文书（未上传时为 null） */
  tenderFile: File | null;
  /** 更新待上传文件 */
  setTenderFile: (f: File | null) => void;
  /** 正在调用 createProject */
  creating: boolean;
  /** 正在调用 uploadTenderDoc */
  uploadingTender: boolean;
  /** 上传失败的错误消息（无错误时为 null） */
  uploadError: string | null;
  /** 触发新建项目；空名直接 no-op */
  handleCreateProject: () => Promise<void>;
  /** 触发上传招标文书；无活动项目或无文件直接 no-op */
  handleUploadTender: () => Promise<void>;
}

export function useProjectWorkflow(): ProjectWorkflow {
  const { activeProject, createProject, uploadTenderDoc } = useWorkbench();

  const [newProjectName, setNewProjectName] = useState<string>("");
  const [creating, setCreating] = useState<boolean>(false);
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [uploadingTender, setUploadingTender] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function handleCreateProject(): Promise<void> {
    if (!newProjectName) return;
    setCreating(true);
    try {
      await createProject(newProjectName);
      setNewProjectName("");
    } finally {
      setCreating(false);
    }
  }

  async function handleUploadTender(): Promise<void> {
    if (!activeProject || !tenderFile) return;
    setUploadingTender(true);
    setUploadError(null);
    try {
      await uploadTenderDoc(activeProject.id, tenderFile);
      setTenderFile(null);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploadingTender(false);
    }
  }

  return {
    newProjectName,
    setNewProjectName,
    tenderFile,
    setTenderFile,
    creating,
    uploadingTender,
    uploadError,
    handleCreateProject,
    handleUploadTender,
  };
}
