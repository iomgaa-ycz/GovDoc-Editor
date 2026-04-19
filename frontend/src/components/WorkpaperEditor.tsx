import { Bold, Heading2, List, Quote } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "./Ui";

export function WorkpaperEditor(props: {
  value: string;
  onChange: (nextValue: string) => void;
}) {
  const editorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!editorRef.current) {
      return;
    }
    if (editorRef.current.innerHTML !== props.value) {
      editorRef.current.innerHTML = props.value;
    }
  }, [props.value]);

  function applyCommand(command: string, value?: string) {
    editorRef.current?.focus();
    document.execCommand(command, false, value);
    props.onChange(editorRef.current?.innerHTML || "");
  }

  return (
    <div className="workpaper-editor">
      <div className="editor-toolbar">
        <Button tone="secondary" size="sm" icon={Bold} onClick={() => applyCommand("bold")}>
          加粗
        </Button>
        <Button
          tone="secondary"
          size="sm"
          icon={Heading2}
          onClick={() => applyCommand("formatBlock", "h2")}
        >
          标题
        </Button>
        <Button
          tone="secondary"
          size="sm"
          icon={Quote}
          onClick={() => applyCommand("formatBlock", "blockquote")}
        >
          引用
        </Button>
        <Button
          tone="secondary"
          size="sm"
          icon={List}
          onClick={() => applyCommand("insertOrderedList")}
        >
          列表
        </Button>
      </div>
      <div
        ref={editorRef}
        className="document-editor"
        contentEditable
        suppressContentEditableWarning
        onInput={(event) => {
          props.onChange((event.target as HTMLDivElement).innerHTML);
        }}
      />
    </div>
  );
}
