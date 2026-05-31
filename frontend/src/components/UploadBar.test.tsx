/**
 * UploadBar 队列渲染测试。
 *
 * 重点验证「按文件稳定 id（而非数组下标）索引进度/错误」这一契约——
 * 这是修复「删除中间失败文件后，其余文件错误信息串位/丢失」bug 的关键。
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import UploadBar, { type FileProgress, type PendingFile } from "./UploadBar";

function makePending(id: string, name: string): PendingFile {
  return { id, file: new File(["x"], name, { type: "application/pdf" }) };
}

/** 取出仅含图标、无文字的删除按钮（X），顺序与渲染行一致 */
function removeButtons(): HTMLElement[] {
  return screen.getAllByRole("button").filter((b) => b.textContent?.trim() === "");
}

describe("UploadBar 队列渲染", () => {
  it("错误信息按 id 挂到对应文件行，不随下标错位", () => {
    const pendingFiles = [makePending("pf-0", "a.pdf"), makePending("pf-1", "b.pdf")];
    // 仅第二个文件（pf-1）有错误
    const fileProgresses: Record<string, FileProgress> = {
      "pf-1": { percentage: 0, done: false, error: "网络错误" },
    };

    render(
      <UploadBar
        pendingFiles={pendingFiles}
        onAddFiles={vi.fn()}
        onRemoveFile={vi.fn()}
        onUpload={vi.fn()}
        uploading={false}
        fileProgresses={fileProgresses}
      />,
    );

    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.pdf")).toBeInTheDocument();
    expect(screen.getByText("网络错误")).toBeInTheDocument();
  });

  it("点击某行删除按钮回传该行文件的 id", () => {
    const onRemoveFile = vi.fn();
    const pendingFiles = [makePending("pf-0", "a.pdf"), makePending("pf-1", "b.pdf")];

    render(
      <UploadBar
        pendingFiles={pendingFiles}
        onAddFiles={vi.fn()}
        onRemoveFile={onRemoveFile}
        onUpload={vi.fn()}
        uploading={false}
        fileProgresses={{}}
      />,
    );

    const buttons = removeButtons();
    expect(buttons).toHaveLength(2);

    fireEvent.click(buttons[0]);
    expect(onRemoveFile).toHaveBeenCalledWith("pf-0");

    fireEvent.click(buttons[1]);
    expect(onRemoveFile).toHaveBeenCalledWith("pf-1");
  });

  it("上传中隐藏删除按钮与「开始上传」按钮", () => {
    const pendingFiles = [makePending("pf-0", "a.pdf")];
    const fileProgresses: Record<string, FileProgress> = {
      "pf-0": { percentage: 40, done: false, error: null },
    };

    render(
      <UploadBar
        pendingFiles={pendingFiles}
        onAddFiles={vi.fn()}
        onRemoveFile={vi.fn()}
        onUpload={vi.fn()}
        uploading={true}
        fileProgresses={fileProgresses}
      />,
    );

    expect(removeButtons()).toHaveLength(0);
    expect(screen.queryByText(/开始上传/)).not.toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });
});
