import { Plus, Upload } from "lucide-react";
import { useState } from "react";

import { useWorkbench } from "../context/V3WorkbenchContext";
import type { GovCheckpointPayload, CheckpointItem } from "../types/ui";
import { parseCheckpointPayload, checkpointToDisplay } from "../adapters/backendToUi";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  FileDropzone,
  IconAction,
  InlineNotice,
  PageHero,
  StatPill,
  TextInput,
  TextArea,
} from "../components/Ui";
import { Modal } from "../components/Modal";

export function AuditLibraryPage() {
  const {
    apiConnected,
    checkpoints,
    extractStatus,
    extractError,
    uploadRuleAndExtract,
    updateCheckpoint,
    deleteCheckpoint,
  } = useWorkbench();

  const [mode, setMode] = useState<"list" | "upload">("list");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Edit modal
  const [editingCheckpoint, setEditingCheckpoint] = useState<CheckpointItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");

  // Delete confirm
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const parsed = checkpoints.map((c) => {
    const p = parseCheckpointPayload(c.payload_json);
    return { item: c, payload: p };
  }).filter((c) => c.payload != null);

  const draftCount = checkpoints.filter((c) => c.kind === "draft").length;
  const finalCount = checkpoints.filter((c) => c.kind === "final").length;

  // ── Upload flow ──

  async function handleUpload() {
    if (!uploadTitle || !uploadFile) return;
    setUploading(true);
    try {
      await uploadRuleAndExtract(uploadTitle, uploadFile);
    } finally {
      setUploading(false);
    }
  }

  // ── Edit flow ──

  function openEdit(item: CheckpointItem) {
    const p = parseCheckpointPayload(item.payload_json);
    if (!p) return;
    setEditingCheckpoint(item);
    setEditTitle(p.title);
    setEditDescription(p.description);
  }

  async function saveEdit() {
    if (!editingCheckpoint) return;
    const p = parseCheckpointPayload(editingCheckpoint.payload_json);
    if (!p) return;
    const updated: GovCheckpointPayload = { ...p, title: editTitle, description: editDescription };
    await updateCheckpoint(editingCheckpoint.id, updated);
    setEditingCheckpoint(null);
  }

  async function confirmDelete() {
    if (!deletingId) return;
    await deleteCheckpoint(deletingId);
    setDeletingId(null);
  }

  // ── Render ──

  return (
    <>
      <PageHero
        eyebrow="审核点库"
        title="审核点管理"
        description="上传法规文件提取审核点，或查看和管理已有审核点。"
        actions={
          mode === "list" ? (
            <Button icon={Upload} onClick={() => setMode("upload")}>上传法规提取</Button>
          ) : (
            <Button tone="secondary" onClick={() => setMode("list")}>返回列表</Button>
          )
        }
      />

      {!apiConnected && (
        <InlineNotice tone="warning" message="后端 API 未连通，部分功能不可用。" />
      )}

      {mode === "list" ? (
        <div className="stack-gap">
          {/* Overview */}
          <div className="library-overview-grid">
            <Card>
              <CardHeader title="终审审核点" />
              <strong style={{ fontSize: 28 }}>{finalCount}</strong>
            </Card>
            <Card>
              <CardHeader title="草稿审核点" />
              <strong style={{ fontSize: 28 }}>{draftCount}</strong>
            </Card>
            <Card>
              <CardHeader title="总计" />
              <strong style={{ fontSize: 28 }}>{checkpoints.length}</strong>
            </Card>
          </div>

          {/* Checkpoint list */}
          {parsed.length === 0 ? (
            <EmptyState
              title="暂无审核点"
              description="请点击「上传法规提取」开始创建审核点。"
            />
          ) : (
            <div className="point-preview-list">
              {parsed.map(({ item, payload }) => (
                <div key={item.id} className="point-preview-item">
                  <div className="point-preview-copy">
                    <strong>{payload!.title}</strong>
                    <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                      {payload!.category} · {payload!.severity} · <StatPill status={item.kind === "final" ? "passed" : "pending"}>{item.kind === "final" ? "终审" : "草稿"}</StatPill>
                    </span>
                    <p>{payload!.description}</p>
                  </div>
                  <div className="point-preview-actions">
                    <IconAction label="编辑" icon="edit" onClick={() => openEdit(item)} />
                    <IconAction label="删除" icon="delete" onClick={() => setDeletingId(item.id)} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Upload mode */
        <div className="stack-gap">
          <Card>
            <CardHeader title="上传法规文件" description="上传法规/制度文件，AI 将自动提取审核点。" />
            <div className="modal-form">
              <Field label="法规标题">
                <TextInput
                  placeholder="例如：政府采购法实施条例"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                />
              </Field>
              <Field label="文件">
                {uploadFile ? (
                  <div className="file-chip-list">
                    <div className="file-chip">
                      <div>
                        <strong>{uploadFile.name}</strong>
                        <span>{(uploadFile.size / 1024).toFixed(1)} KB</span>
                      </div>
                      <button className="icon-button" type="button" onClick={() => setUploadFile(null)}>
                        ×
                      </button>
                    </div>
                  </div>
                ) : (
                  <FileDropzone
                    title="选择法规文件"
                    subtitle="支持 .md, .txt, .pdf, .docx"
                    accept=".md,.txt,.pdf,.docx"
                    onSelect={(files) => setUploadFile(files[0] ?? null)}
                  />
                )}
              </Field>
              {extractStatus && extractStatus !== "draft_ready" && (
                <InlineNotice
                  tone={extractStatus === "failed" ? "warning" : "info"}
                  message={
                    extractStatus === "pending"
                      ? "等待处理..."
                      : extractStatus === "running"
                        ? "正在提取审核点..."
                        : extractError ?? "处理失败"
                  }
                />
              )}
              {extractStatus === "draft_ready" && (
                <InlineNotice tone="success" message="提取完成，审核点已生成。" />
              )}
              <div className="footer-actions">
                <Button
                  tone="primary"
                  icon={Plus}
                  busy={uploading}
                  disabled={!uploadTitle || !uploadFile || uploading || extractStatus === "running"}
                  onClick={handleUpload}
                >
                  开始抽取
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Edit modal */}
      <Modal
        open={editingCheckpoint != null}
        title="编辑审核点"
        onClose={() => setEditingCheckpoint(null)}
        footer={
          <>
            <Button tone="secondary" onClick={() => setEditingCheckpoint(null)}>取消</Button>
            <Button onClick={saveEdit}>保存</Button>
          </>
        }
      >
        <Field label="标题">
          <TextInput value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
        </Field>
        <Field label="描述">
          <TextArea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
        </Field>
      </Modal>

      {/* Delete confirm */}
      <Modal
        open={deletingId != null}
        title="确认删除"
        subtitle="删除后无法恢复。"
        onClose={() => setDeletingId(null)}
        footer={
          <>
            <Button tone="secondary" onClick={() => setDeletingId(null)}>取消</Button>
            <Button tone="danger" onClick={confirmDelete}>确认删除</Button>
          </>
        }
      >
        <p>确定要删除这个审核点吗？</p>
      </Modal>
    </>
  );
}
