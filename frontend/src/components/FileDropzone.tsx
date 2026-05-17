import { Upload } from "lucide-react";
import { useState, type DragEvent } from "react";
import { cn } from "@/lib/utils";

export function FileDropzone({ title, subtitle, accept, multiple, onSelect }: {
  title: string;
  subtitle: string;
  accept?: string;
  multiple?: boolean;
  onSelect: (files: File[]) => void;
}) {
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragging(false);
    onSelect(Array.from(e.dataTransfer.files));
  }

  return (
    <label
      className={cn(
        "flex flex-col items-center gap-2 rounded-card border-2 border-dashed p-6 cursor-pointer transition-colors hover:border-accent hover:bg-accent-light/50",
        dragging && "border-accent bg-accent-light/50",
      )}
      onDragEnter={(e) => { e.preventDefault(); setDragging(true); }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input className="sr-only" type="file" accept={accept} multiple={multiple} onChange={(e) => { onSelect(Array.from(e.target.files || [])); e.target.value = ""; }} />
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-light">
        <Upload className="h-5 w-5 text-accent" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-text-primary">{title}</p>
        <p className="text-xs text-text-muted">{subtitle}</p>
      </div>
    </label>
  );
}
