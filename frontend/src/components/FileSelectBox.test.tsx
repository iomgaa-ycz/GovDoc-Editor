import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FileSelectBox } from "./FileSelectBox";

function makeFile(name: string): File {
  return new File(["x"], name, { type: "application/octet-stream" });
}

describe("FileSelectBox", () => {
  it("拖入匹配扩展名的文件触发 onSelect", () => {
    const onSelect = vi.fn();
    render(<FileSelectBox title="选择文件" subtitle="s" accept=".md,.doc" onSelect={onSelect} />);
    const file = makeFile("a.doc");
    const zone = screen.getByText("选择文件").closest("label")!;
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(onSelect).toHaveBeenCalledWith(file);
  });

  it("拖入不支持扩展名显示错误且不触发 onSelect", () => {
    const onSelect = vi.fn();
    render(<FileSelectBox title="选择文件" subtitle="s" accept=".md,.doc" onSelect={onSelect} />);
    const zone = screen.getByText("选择文件").closest("label")!;
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile("a.txt")] } });
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByText(/仅支持/)).toBeInTheDocument();
  });

  it("点击选择路径调用 onSelect", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <FileSelectBox title="选择文件" subtitle="s" accept=".md" onSelect={onSelect} />,
    );
    const input = container.querySelector("input[type=file]") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("a.md")] } });
    expect(onSelect).toHaveBeenCalled();
  });
});
