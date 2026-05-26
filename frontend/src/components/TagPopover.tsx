import { useState } from "react";
import { Search, Plus, Check, Tag as TagIcon } from "lucide-react";
import type { Tag, DocumentTag } from "../types/ui";

interface Props {
  allTags: Tag[];
  activeTags: string[]; // tag IDs currently applied
  onToggle: (tagId: string) => void;
  onCreate: (name: string) => void;
  children: React.ReactNode; // trigger element
}

export default function TagPopover({ allTags, activeTags, onToggle, onCreate, children }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = allTags.filter((t) => t.name.includes(search));
  const canCreate = search.trim() && !allTags.some((t) => t.name === search.trim());

  return (
    <div className="relative">
      <div onClick={() => setOpen(!open)}>{children}</div>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-72 rounded-lg border border-gray-200 bg-white shadow-lg">
          <div className="border-b p-3">
            <p className="text-sm font-semibold text-gray-900 mb-2">管理标签</p>
            <div className="flex items-center gap-2 rounded-md border bg-gray-50 px-2.5 py-1.5">
              <Search className="h-3.5 w-3.5 text-gray-400" />
              <input
                className="w-full bg-transparent text-xs outline-none placeholder:text-gray-400"
                placeholder="搜索或创建标签..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="max-h-48 overflow-y-auto p-1.5">
            {filtered.map((tag) => {
              const [bg, fg] = tag.color.split(":");
              const active = activeTags.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  onClick={() => onToggle(tag.id)}
                  className="flex w-full items-center justify-between rounded-md px-2 py-1.5 hover:bg-gray-50"
                >
                  <div className="flex items-center gap-2">
                    <div className={`flex h-4 w-4 items-center justify-center rounded ${active ? "bg-blue-600" : "border border-gray-300"}`}>
                      {active && <Check className="h-2.5 w-2.5 text-white" />}
                    </div>
                    <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: bg, color: fg }}>{tag.name}</span>
                  </div>
                </button>
              );
            })}
          </div>
          {canCreate && (
            <button
              onClick={() => { onCreate(search.trim()); setSearch(""); }}
              className="flex w-full items-center gap-1.5 border-t px-3 py-2.5 text-xs font-medium text-blue-600 hover:bg-gray-50"
            >
              <Plus className="h-3.5 w-3.5" />
              创建新标签「{search.trim()}」
            </button>
          )}
        </div>
      )}
    </div>
  );
}
