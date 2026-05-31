import { useRef, useState, type DragEvent } from "react";
import { CloudUpload, Upload, X, FileText } from "lucide-react";
import { Progress } from "./ui/progress";

export interface FileProgress {
  percentage: number;
  done: boolean;
  error: string | null;
}

/**
 * 待上传文件项：稳定 id + 文件对象。
 * id 在加入队列时一次性生成，与数组下标解耦——删除中间某项后，
 * 其余文件的进度/错误信息（按 id 索引）不会串位。
 */
export interface PendingFile {
  id: string;
  file: File;
}

interface Props {
  /** 待上传文件队列（由父组件管理） */
  pendingFiles: PendingFile[];
  /** 向队列中添加文件 */
  onAddFiles: (files: File[]) => void;
  /** 从队列中移除指定 id 的文件 */
  onRemoveFile: (id: string) => void;
  /** 点击「开始上传」按钮 */
  onUpload: () => void;
  /** 是否正在上传中 */
  uploading: boolean;
  /** 每个文件的上传进度，key 为文件稳定 id */
  fileProgresses: Record<string, FileProgress>;
}

const ACCEPT = ".pdf,.docx,.doc";

/** 格式化文件大小 */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadBar({
  pendingFiles,
  onAddFiles,
  onRemoveFile,
  onUpload,
  uploading,
  fileProgresses,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (uploading) return;
    const files = Array.from(e.dataTransfer.files).filter((f) =>
      ACCEPT.split(",").some((ext) => f.name.toLowerCase().endsWith(ext)),
    );
    if (files.length) onAddFiles(files);
  };

  const handleSelect = () => {
    if (uploading) return;
    const files = inputRef.current?.files;
    if (files?.length) onAddFiles(Array.from(files));
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="space-y-3">
      {/* 拖拽上传区 */}
      <div
        className={`flex items-center justify-between rounded-xl border-[1.5px] px-5 py-4 transition-colors ${
          uploading ? "border-blue-200 bg-blue-50/30 opacity-60" : dragging ? "border-blue-500 bg-blue-50" : "border-blue-300 bg-blue-50/50"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
            <CloudUpload className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-blue-800">
              {uploading ? "正在上传中，请等待完成…" : "拖拽 PDF 或 Word 文件到此处"}
            </p>
            <p className="text-xs text-blue-400">支持批量添加，单个文件最大 200 MB</p>
          </div>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Upload className="h-3.5 w-3.5" />
          选择文件
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={handleSelect}
        />
      </div>

      {/* 待上传文件列表 */}
      {pendingFiles.length > 0 && (
        <div className="rounded-xl border bg-white shadow-card">
          <div className="px-5 py-3 border-b">
            <p className="text-sm font-medium text-text-primary">
              待上传文件（{pendingFiles.length}）
            </p>
          </div>

          <div className="divide-y max-h-64 overflow-y-auto">
            {pendingFiles.map(({ id, file }) => {
              const progress = fileProgresses[id];
              const isUploading = uploading && progress != null;
              const isDone = progress?.done;
              const hasError = progress?.error;

              return (
                <div key={id} className="flex items-center gap-3 px-5 py-2.5">
                  <FileText
                    className={`h-4 w-4 shrink-0 ${
                      hasError
                        ? "text-red-500"
                        : isDone
                          ? "text-green-600"
                          : "text-blue-500"
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-primary truncate">{file.name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-text-muted">{formatSize(file.size)}</span>
                      {isUploading && !isDone && (
                        <>
                          <span className="text-xs text-blue-600 font-medium">
                            {progress.percentage}%
                          </span>
                          <Progress
                            value={progress.percentage}
                            className="h-1.5 flex-1"
                          />
                        </>
                      )}
                      {isDone && (
                        <span className="text-xs text-green-600 font-medium">上传完成</span>
                      )}
                      {hasError && (
                        <span className="text-xs text-red-600 font-medium">{progress.error}</span>
                      )}
                    </div>
                  </div>
                  {/* 未上传时可删除 */}
                  {!uploading && (
                    <button
                      onClick={() => onRemoveFile(id)}
                      className="shrink-0 rounded p-1 text-text-muted hover:bg-red-50 hover:text-red-500"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* 底部操作栏 */}
          {!uploading && (
            <div className="flex justify-end px-5 py-3 border-t bg-gray-50/50 rounded-b-xl">
              <button
                onClick={onUpload}
                className="flex items-center gap-1.5 rounded-md bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                <Upload className="h-3.5 w-3.5" />
                开始上传（{pendingFiles.length} 个文件）
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
