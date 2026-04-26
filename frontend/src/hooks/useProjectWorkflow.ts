/**
 * useProjectWorkflow
 * ------------------
 * 封装"新建项目 + 上传招标文书"两段工作流的本地 UI 状态与 handler。
 *
 * 设计要点：
 *   1. 本 hook 从 useWorkbench() 内部读取 createProject / uploadAuditInputDocs / activeProject，
 *      调用方无需再手动串联 context。
 *   2. 业务副作用（网络 I/O）仍由 context 负责；hook 仅管理 busy 标志与输入态。
 */

import { useCallback, useEffect, useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";

export interface ProjectWorkflow {
  /** 新项目名称输入框当前值 */
  newProjectName: string;
  /** 更新新项目名称 */
  setNewProjectName: (v: string) => void;
  /** 待上传的主招标文书（未选择时为 null） */
  mainTenderFile: File | null;
  /** 更新待上传主招标文书 */
  setMainTenderFile: (f: File | null) => void;
  /** 待上传附件列表 */
  supplementaryFiles: File[];
  /** 更新待上传附件列表 */
  setSupplementaryFiles: (files: File[]) => void;
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
  const { activeProject, createProject, uploadAuditInputDocs } = useWorkbench();

  const [newProjectName, setNewProjectName] = useState<string>("");
  const [creating, setCreating] = useState<boolean>(false);
  const [mainTenderFile, setMainTenderFile] = useState<File | null>(null);
  const [supplementaryFiles, setSupplementaryFiles] = useState<File[]>([]);
  const [uploadingTender, setUploadingTender] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // 切换文件时清空上传错误
  const setTenderFile = useCallback(
    (f: File | null) => {
      setTenderFileRaw(f);
      if (f !== null) setUploadError(null);
    },
    [],
  );

  // 切换项目时清空上传错误
  useEffect(() => {
    setUploadError(null);
  }, [activeProject?.id]);

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
    if (!activeProject || !mainTenderFile) return;
    setUploadingTender(true);
    setUploadError(null);
    try {
      await uploadAuditInputDocs(activeProject.id, mainTenderFile, supplementaryFiles);
      setMainTenderFile(null);
      setSupplementaryFiles([]);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploadingTender(false);
    }
  }

  return {
    newProjectName,
    setNewProjectName,
    mainTenderFile,
    setMainTenderFile,
    supplementaryFiles,
    setSupplementaryFiles,
    creating,
    uploadingTender,
    uploadError,
    handleCreateProject,
    handleUploadTender,
  };
}
