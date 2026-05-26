import { useRef, useState, type DragEvent } from "react";
import { CloudUpload, Upload } from "lucide-react";

interface Props {
  onUpload: (files: File[]) => void;
  uploading?: boolean;
}

const ACCEPT = ".pdf,.docx,.doc";

export default function UploadBar({ onUpload, uploading }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files).filter((f) =>
      ACCEPT.split(",").some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    if (files.length) onUpload(files);
  };

  const handleSelect = () => {
    const files = inputRef.current?.files;
    if (files?.length) onUpload(Array.from(files));
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div
      className={`flex items-center justify-between rounded-xl border-[1.5px] px-5 py-4 transition-colors ${
        dragging ? "border-blue-500 bg-blue-50" : "border-blue-300 bg-blue-50/50"
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
          <CloudUpload className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <p className="text-sm font-medium text-blue-800">拖拽 PDF 或 Word 文件到此处上传</p>
          <p className="text-xs text-blue-400">支持批量上传，单个文件最大 200 MB</p>
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
      <input ref={inputRef} type="file" accept={ACCEPT} multiple hidden onChange={handleSelect} />
    </div>
  );
}
