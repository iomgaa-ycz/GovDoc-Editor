import { Bold, Heading2, List, Quote } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";

export function WorkpaperEditor({ value, onChange }: { value: string; onChange: (html: string) => void }) {
  const editorRef = useRef<HTMLDivElement>(null);

  function exec(command: string, arg?: string) {
    document.execCommand(command, false, arg);
    if (editorRef.current) onChange(editorRef.current.innerHTML);
  }

  return (
    <div>
      <div className="flex items-center gap-1 border-b px-3 py-2">
        <Button variant="ghost" size="icon" onClick={() => exec("bold")} title="加粗"><Bold className="h-4 w-4" /></Button>
        <Button variant="ghost" size="icon" onClick={() => exec("formatBlock", "H2")} title="标题"><Heading2 className="h-4 w-4" /></Button>
        <Button variant="ghost" size="icon" onClick={() => exec("formatBlock", "BLOCKQUOTE")} title="引用"><Quote className="h-4 w-4" /></Button>
        <Button variant="ghost" size="icon" onClick={() => exec("insertOrderedList")} title="有序列表"><List className="h-4 w-4" /></Button>
      </div>
      <div
        ref={editorRef}
        contentEditable
        className="min-h-[500px] p-10 text-sm leading-relaxed text-text-primary focus:outline-none"
        dangerouslySetInnerHTML={{ __html: value }}
        onInput={() => { if (editorRef.current) onChange(editorRef.current.innerHTML); }}
      />
    </div>
  );
}
