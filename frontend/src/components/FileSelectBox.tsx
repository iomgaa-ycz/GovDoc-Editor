import { useState, type DragEvent } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

/** 解析 accept 字符串为小写扩展名数组（".md,.pdf" -> [".md", ".pdf"]）。 */
export function parseAccept(accept: string): string[] {
  return accept
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

/** 文件扩展名是否命中 accept 白名单（白名单为空则放行）。 */
function matchesAccept(file: File, accept: string): boolean {
  const exts = parseAccept(accept);
  if (exts.length === 0) return true;
  const name = file.name.toLowerCase();
  return exts.some((ext) => name.endsWith(ext));
}

/**
 * 文件选择 / 拖拽上传框。
 *
 * 同时支持点击选择与拖拽；拖入不在 accept 白名单的扩展名时显示内联错误。
 *
 * 参数:
 *   title: 主标题
 *   subtitle: 副标题（通常列出支持格式）
 *   accept: 逗号分隔扩展名白名单，同时用作 input accept 与拖拽过滤
 *   onSelect: 选中（或拖入）一个有效文件时回调
 */
export function FileSelectBox({
  title,
  subtitle,
  accept,
  onSelect,
}: {
  title: string;
  subtitle: string;
  accept: string;
  onSelect: (file: File | null) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0] ?? null;
    if (!file) return;
    if (matchesAccept(file, accept)) {
      setError(null);
      onSelect(file);
    } else {
      setError(`仅支持 ${accept} 格式`);
    }
  }

  return (
    <div className="space-y-1.5">
      <label
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-card border border-dashed bg-surface px-4 py-8 text-center transition-colors hover:border-accent hover:bg-accent-light",
          dragging && "border-accent bg-accent-light",
        )}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <Upload className="mb-2 h-5 w-5 text-text-muted" />
        <span className="text-sm font-medium text-text-primary">{title}</span>
        <span className="mt-1 text-xs text-text-muted">{subtitle}</span>
        <input
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(event) => {
            setError(null);
            onSelect(event.target.files?.[0] ?? null);
          }}
        />
      </label>
      {error && <p className="text-xs text-status-err">{error}</p>}
    </div>
  );
}
