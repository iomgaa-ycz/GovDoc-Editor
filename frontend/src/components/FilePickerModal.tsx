import { useEffect, useState } from "react";
import { Search, FileText, File, Check, X, Tag as TagIcon, ChevronDown } from "lucide-react";
import type { GovDocument, Tag } from "../types/ui";
import { listDocuments, listTags } from "../api/documents";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: (ids: string[]) => void;
  mode: "single" | "multi";
  initialSelected?: string[];
}

export default function FilePickerModal({ open, onClose, onConfirm, mode, initialSelected = [] }: Props) {
  const [docs, setDocs] = useState<GovDocument[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set(initialSelected));
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [tagFilter, setTagFilter] = useState<string>("");

  useEffect(() => {
    if (!open) return;
    setSelected(new Set(initialSelected));
    listDocuments({ status: "ready" }).then(setDocs);
    listTags().then(setTags);
  }, [open]);

  const filtered = docs.filter((d) => {
    if (search && !d.filename.toLowerCase().includes(search.toLowerCase())) return false;
    if (typeFilter !== "all" && d.file_type !== typeFilter) return false;
    if (tagFilter && !d.tags.some((t) => t.id === tagFilter)) return false;
    return true;
  });

  const toggle = (id: string) => {
    if (mode === "single") {
      setSelected(new Set([id]));
    } else {
      const next = new Set(selected);
      next.has(id) ? next.delete(id) : next.add(id);
      setSelected(next);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="flex h-[580px] w-[640px] flex-col rounded-xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-5">
          <h3 className="text-base font-semibold text-gray-900">选择文件</h3>
          <button onClick={onClose}><X className="h-5 w-5 text-gray-400" /></button>
        </div>

        {/* Filters */}
        <div className="space-y-3 px-6 py-4">
          <div className="flex items-center gap-2 rounded-lg border bg-gray-50 px-3 py-2">
            <Search className="h-4 w-4 text-gray-400" />
            <input className="w-full bg-transparent text-sm outline-none" placeholder="搜索文件名..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            {["all", "pdf", "docx"].map((t) => (
              <button key={t} onClick={() => setTypeFilter(t)} className={`rounded-md px-3 py-1 text-xs font-medium ${typeFilter === t ? "bg-gray-900 text-white" : "border text-gray-600"}`}>
                {t === "all" ? "全部" : t.toUpperCase()}
              </button>
            ))}
            {tags.length > 0 && (
              <>
                <div className="mx-1 h-5 w-px bg-gray-200" />
                <select className="rounded-md border px-2 py-1 text-xs text-gray-600" value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}>
                  <option value="">全部标签</option>
                  {tags.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </>
            )}
          </div>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-y-auto px-6">
          {filtered.map((d) => {
            const checked = selected.has(d.id);
            return (
              <button key={d.id} onClick={() => toggle(d.id)} className={`flex w-full items-center gap-3 rounded-md px-3 py-2.5 ${checked ? "bg-blue-50" : "hover:bg-gray-50"}`}>
                <div className={`flex h-[18px] w-[18px] items-center justify-center rounded ${checked ? "bg-blue-600" : "border-[1.5px] border-gray-300"}`}>
                  {checked && <Check className="h-3 w-3 text-white" />}
                </div>
                {d.file_type === "pdf" ? <FileText className="h-4 w-4 text-red-500" /> : <File className="h-4 w-4 text-blue-600" />}
                <div className="flex-1 text-left">
                  <p className={`text-sm ${checked ? "font-medium text-blue-800" : "text-gray-800"}`}>{d.filename}</p>
                  <p className="text-xs text-gray-400">{(d.file_size / 1048576).toFixed(1)} MB · {d.created_at.slice(5, 10)}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t px-6 py-4">
          <span className="text-sm text-gray-500">已选择 {selected.size} 个文件</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-md border px-4 py-2 text-sm font-medium text-gray-600">取消</button>
            <button onClick={() => onConfirm([...selected])} disabled={selected.size === 0} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">确认选择</button>
          </div>
        </div>
      </div>
    </div>
  );
}
