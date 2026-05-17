# 前端重构：Tailwind CSS + shadcn/ui 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将前端从纯 CSS MVP 重构为基于 Tailwind CSS + shadcn/ui 的内测级 UI，实现 Pencil 设计稿中的全部页面和状态。

**Architecture:** 在现有 Vite + React + TypeScript 基础上，引入 Tailwind CSS 和 shadcn/ui 组件库。迁移期间新旧样式共存：新组件使用 Tailwind utilities，旧组件保留原 CSS，最终清理旧样式文件。布局从顶部导航栏切换为固定左侧深色侧边栏。API 层 (`api/v3.ts`)、状态管理 (`V3WorkbenchContext.tsx`)、适配器 (`backendToUi.ts`) 保持不变。

**Tech Stack:** Vite 5 · React 18 · TypeScript · Tailwind CSS 3 · shadcn/ui · class-variance-authority · clsx · tailwind-merge · Lucide React · Inter + Geist Mono 字体

---

## 文件变更总览

### 创建（新文件）

| 文件路径 | 职责 |
|---------|------|
| `frontend/tailwind.config.ts` | Tailwind 主题配置（设计 token、字体、颜色） |
| `frontend/postcss.config.js` | PostCSS 插件链（tailwindcss + autoprefixer） |
| `frontend/src/lib/utils.ts` | `cn()` 工具函数（clsx + tailwind-merge） |
| `frontend/src/globals.css` | Tailwind 指令 + CSS 变量（shadcn 主题层） |
| `frontend/src/components/ui/button.tsx` | shadcn Button |
| `frontend/src/components/ui/card.tsx` | shadcn Card |
| `frontend/src/components/ui/input.tsx` | shadcn Input |
| `frontend/src/components/ui/textarea.tsx` | shadcn Textarea |
| `frontend/src/components/ui/badge.tsx` | shadcn Badge |
| `frontend/src/components/ui/dialog.tsx` | shadcn Dialog |
| `frontend/src/components/ui/select.tsx` | shadcn Select |
| `frontend/src/components/ui/dropdown-menu.tsx` | shadcn DropdownMenu |
| `frontend/src/components/ui/table.tsx` | shadcn Table |
| `frontend/src/components/ui/progress.tsx` | shadcn Progress |
| `frontend/src/components/ui/scroll-area.tsx` | shadcn ScrollArea |
| `frontend/src/components/ui/separator.tsx` | shadcn Separator |
| `frontend/src/components/ui/tooltip.tsx` | shadcn Tooltip |
| `frontend/src/components/ui/tabs.tsx` | shadcn Tabs |
| `frontend/src/components/Sidebar.tsx` | 深色侧边栏导航组件 |
| `frontend/src/components/StatusBadge.tsx` | 状态徽章（合规/不合规/存疑/pending/running/...） |
| `frontend/src/components/ProgressTimeline.tsx` | 6 步审查进度时间线 |
| `frontend/src/components/FileDropzone.tsx` | 文件拖拽上传组件（Tailwind 版） |
| `frontend/src/components/MetricCard.tsx` | 统计指标卡片 |
| `frontend/src/components/EmptyState.tsx` | 空状态占位组件 |
| `frontend/src/components/PointInsightPanel.tsx` | 审核点详情面板（从旧 PointInsight 重构） |
| `frontend/src/pages/DashboardPage.tsx` | 新版首页仪表盘 |

### 修改（现有文件）

| 文件路径 | 修改内容 |
|---------|---------|
| `frontend/package.json` | 添加 Tailwind/shadcn 依赖，替换字体包 |
| `frontend/tsconfig.json` | 无需修改（已有 `@/*` 路径别名） |
| `frontend/vite.config.ts` | 添加 `resolve.alias` 使 `@/` 映射到 `src/` |
| `frontend/index.html` | 添加 Inter + Geist Mono 字体 preconnect |
| `frontend/src/main.tsx` | 替换字体导入和样式导入 |
| `frontend/src/App.tsx` | 路由保持不变，HomePage → DashboardPage |
| `frontend/src/components/AppShell.tsx` | 完全重写：sidebar + topbar + main 布局 |
| `frontend/src/pages/AuditLibraryPage.tsx` | 完全重写：表格 + 搜索 + 筛选 + 子页面切换 |
| `frontend/src/pages/AIReviewPage.tsx` | 完全重写：Setup/Running 状态切换 |
| `frontend/src/pages/AuditResultsPage.tsx` | 完全重写：左右分栏 + 反馈面板 |
| `frontend/src/pages/WorkpaperPage.tsx` | 完全重写：编辑器 + 侧栏元数据 |
| `frontend/src/pages/DocComparePage.tsx` | 完全重写：上传/对比两种状态 |
| `frontend/src/components/Modal.tsx` | 迁移到 shadcn Dialog |
| `frontend/src/components/PointInsight.tsx` | 迁移到 Tailwind 样式 |
| `frontend/src/components/WorkpaperEditor.tsx` | 迁移到 Tailwind 样式 |
| `frontend/tests/pages/AIReviewPage.test.tsx` | 更新 import 和渲染断言 |

### 删除

| 文件路径 | 原因 |
|---------|------|
| `frontend/src/styles.css` | 被 Tailwind + globals.css 完全替代 |
| `frontend/src/components/Ui.tsx` | 被 shadcn/ui 组件 + 自定义组件替代 |
| `frontend/src/components/AuditProgressPanel.tsx` | 功能合并进 AIReviewPage |
| `frontend/src/components/TenderUploadPanel.tsx` | 功能合并进 AIReviewPage |
| `frontend/src/components/CheckpointPicker.tsx` | 功能合并进 AIReviewPage |
| `frontend/src/pages/HomePage.tsx` | 被 DashboardPage.tsx 替代 |

---

## Task 1: Tailwind CSS + shadcn/ui 基础设施

**Files:**
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/globals.css`
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/index.html`

- [ ] **Step 1: 安装依赖**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npm install tailwindcss@3 postcss autoprefixer class-variance-authority clsx tailwind-merge @radix-ui/react-slot
```

安装字体包（替换 IBM Plex）：

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npm install @fontsource-variable/inter @fontsource/geist-mono && npm uninstall @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono
```

- [ ] **Step 2: 创建 PostCSS 配置**

```js
// frontend/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3: 创建 Tailwind 配置**

```ts
// frontend/tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#F7F8FA",
          card: "#FFFFFF",
        },
        sidebar: {
          DEFAULT: "#0A0F1E",
          hover: "#131B2E",
          active: "#0D1525",
        },
        accent: {
          DEFAULT: "#0062FF",
          hover: "#2563EB",
          light: "#F0F5FF",
        },
        border: {
          DEFAULT: "#E5E7EB",
          light: "#F3F4F6",
        },
        text: {
          primary: "#1A1A1A",
          secondary: "#4B5563",
          muted: "#9CA3AF",
          inverse: "#FFFFFF",
        },
        status: {
          ok: "#16A34A",
          "ok-bg": "#F0FDF4",
          warn: "#D97706",
          "warn-bg": "#FFFBEB",
          err: "#DC2626",
          "err-bg": "#FEF2F2",
          "err-border": "#FECACA",
          info: "#3B82F6",
          "info-bg": "#EFF6FF",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "monospace"],
      },
      borderRadius: {
        btn: "6px",
        card: "8px",
        modal: "12px",
      },
      width: {
        sidebar: "240px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.06)",
        modal: "0 8px 32px rgba(0,0,0,0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 4: 创建全局样式文件**

```css
/* frontend/src/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --radius: 0.5rem;
  }

  body {
    @apply bg-surface text-text-primary font-sans antialiased;
    margin: 0;
  }

  * {
    @apply border-border;
  }
}

@layer utilities {
  .gradient-btn {
    background: linear-gradient(180deg, #2563EB 0%, #0062FF 100%);
  }
}
```

- [ ] **Step 5: 创建 cn() 工具函数**

```ts
// frontend/src/lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 6: 更新 vite.config.ts — 添加路径别名**

```ts
// frontend/vite.config.ts
import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
    },
  },
});
```

- [ ] **Step 7: 更新 main.tsx — 替换字体和样式导入**

```tsx
// frontend/src/main.tsx
import "@fontsource-variable/inter";
import "@fontsource/geist-mono/400.css";
import "./globals.css";
import "./styles.css"; // 旧样式暂时保留，迁移期间共存

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { WorkbenchProvider } from "./context/V3WorkbenchContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <WorkbenchProvider>
        <App />
      </WorkbenchProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 8: 验证构建**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit && npx vite build
```

Expected: 构建成功，无错误。

- [ ] **Step 9: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/tailwind.config.ts frontend/postcss.config.js frontend/src/lib/utils.ts frontend/src/globals.css frontend/vite.config.ts frontend/src/main.tsx frontend/package.json frontend/package-lock.json && git commit -m "feat(frontend): add Tailwind CSS + shadcn/ui infrastructure"
```

---

## Task 2: shadcn/ui 基础组件

**Files:**
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/card.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/textarea.tsx`
- Create: `frontend/src/components/ui/badge.tsx`
- Create: `frontend/src/components/ui/dialog.tsx`
- Create: `frontend/src/components/ui/select.tsx`
- Create: `frontend/src/components/ui/dropdown-menu.tsx`
- Create: `frontend/src/components/ui/table.tsx`
- Create: `frontend/src/components/ui/progress.tsx`
- Create: `frontend/src/components/ui/scroll-area.tsx`
- Create: `frontend/src/components/ui/separator.tsx`
- Create: `frontend/src/components/ui/tooltip.tsx`
- Create: `frontend/src/components/ui/tabs.tsx`

- [ ] **Step 1: 安装 Radix UI 依赖**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npm install @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-select @radix-ui/react-scroll-area @radix-ui/react-separator @radix-ui/react-tooltip @radix-ui/react-tabs @radix-ui/react-progress
```

- [ ] **Step 2: 创建所有 shadcn/ui 组件文件**

使用 shadcn/ui 标准实现。每个组件从 Radix primitive 封装，使用 `cn()` 合并样式。

以下是需要创建的所有组件（均为标准 shadcn/ui 实现，使用项目的 design token）。

`frontend/src/components/ui/button.tsx`:

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-btn text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "gradient-btn text-white shadow-sm hover:opacity-90",
        secondary: "border border-border bg-white text-text-primary hover:bg-surface",
        ghost: "text-text-secondary hover:bg-surface hover:text-text-primary",
        danger: "bg-status-err text-white hover:bg-red-700",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

`frontend/src/components/ui/card.tsx`:

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-card border bg-surface-card shadow-card", className)}
      {...props}
    />
  ),
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-5", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-base font-semibold text-text-primary", className)} {...props} />
  ),
);
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-text-muted", className)} {...props} />
  ),
);
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-5 pt-0", className)} {...props} />
  ),
);
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-5 pt-0", className)} {...props} />
  ),
);
CardFooter.displayName = "CardFooter";

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent };
```

`frontend/src/components/ui/input.tsx`:

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-btn border bg-white px-3 py-1 text-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
```

`frontend/src/components/ui/textarea.tsx`:

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-btn border bg-white px-3 py-2 text-sm placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export { Textarea };
```

`frontend/src/components/ui/badge.tsx`:

```tsx
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-accent-light text-accent",
        ok: "bg-status-ok-bg text-status-ok",
        warn: "bg-status-warn-bg text-status-warn",
        err: "bg-status-err-bg text-status-err",
        muted: "bg-gray-100 text-text-muted",
        outline: "border text-text-secondary",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
```

`frontend/src/components/ui/dialog.tsx`:

```tsx
import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogPortal = DialogPrimitive.Portal;
const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 w-full max-w-lg translate-x-[-50%] translate-y-[-50%] border bg-white shadow-modal rounded-modal duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none">
        <X className="h-4 w-4" />
        <span className="sr-only">关闭</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 p-5 border-b", className)} {...props} />
);
DialogHeader.displayName = "DialogHeader";

const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex justify-end gap-2 p-5 border-t", className)} {...props} />
);
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold text-text-primary", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-text-muted", className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
```

`frontend/src/components/ui/table.tsx`:

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Table = React.forwardRef<HTMLTableElement, React.HTMLAttributes<HTMLTableElement>>(
  ({ className, ...props }, ref) => (
    <div className="relative w-full overflow-auto">
      <table ref={ref} className={cn("w-full caption-bottom text-sm", className)} {...props} />
    </div>
  ),
);
Table.displayName = "Table";

const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
  ),
);
TableHeader.displayName = "TableHeader";

const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tbody ref={ref} className={cn("[&_tr:last-child]:border-0", className)} {...props} />
  ),
);
TableBody.displayName = "TableBody";

const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => (
    <tr ref={ref} className={cn("border-b transition-colors hover:bg-surface/50", className)} {...props} />
  ),
);
TableRow.displayName = "TableRow";

const TableHead = React.forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <th
      ref={ref}
      className={cn("h-10 px-4 text-left align-middle text-xs font-medium text-text-muted [&:has([role=checkbox])]:pr-0", className)}
      {...props}
    />
  ),
);
TableHead.displayName = "TableHead";

const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <td ref={ref} className={cn("px-4 py-3 align-middle [&:has([role=checkbox])]:pr-0", className)} {...props} />
  ),
);
TableCell.displayName = "TableCell";

export { Table, TableHeader, TableBody, TableHead, TableRow, TableCell };
```

`frontend/src/components/ui/progress.tsx`:

```tsx
import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root>
>(({ className, value, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn("relative h-2 w-full overflow-hidden rounded-full bg-gray-100", className)}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full bg-accent transition-all"
      style={{ width: `${value ?? 0}%` }}
    />
  </ProgressPrimitive.Root>
));
Progress.displayName = ProgressPrimitive.Root.displayName;

export { Progress };
```

`frontend/src/components/ui/scroll-area.tsx`:

```tsx
import * as React from "react";
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import { cn } from "@/lib/utils";

const ScrollArea = React.forwardRef<
  React.ElementRef<typeof ScrollAreaPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root>
>(({ className, children, ...props }, ref) => (
  <ScrollAreaPrimitive.Root ref={ref} className={cn("relative overflow-hidden", className)} {...props}>
    <ScrollAreaPrimitive.Viewport className="h-full w-full rounded-[inherit]">
      {children}
    </ScrollAreaPrimitive.Viewport>
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      orientation="vertical"
      className="flex h-full w-2.5 touch-none select-none border-l border-l-transparent p-[1px] transition-colors"
    >
      <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-full bg-border" />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
    <ScrollAreaPrimitive.Corner />
  </ScrollAreaPrimitive.Root>
));
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName;

export { ScrollArea };
```

`frontend/src/components/ui/separator.tsx`:

```tsx
import * as React from "react";
import * as SeparatorPrimitive from "@radix-ui/react-separator";
import { cn } from "@/lib/utils";

const Separator = React.forwardRef<
  React.ElementRef<typeof SeparatorPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>
>(({ className, orientation = "horizontal", decorative = true, ...props }, ref) => (
  <SeparatorPrimitive.Root
    ref={ref}
    decorative={decorative}
    orientation={orientation}
    className={cn(
      "shrink-0 bg-border",
      orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]",
      className,
    )}
    {...props}
  />
));
Separator.displayName = SeparatorPrimitive.Root.displayName;

export { Separator };
```

`frontend/src/components/ui/dropdown-menu.tsx`:

```tsx
import * as React from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/utils";

const DropdownMenu = DropdownMenuPrimitive.Root;
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[8rem] overflow-hidden rounded-card border bg-white p-1 shadow-md",
        className,
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex cursor-pointer select-none items-center gap-2 rounded-btn px-2 py-1.5 text-sm outline-none transition-colors hover:bg-surface focus:bg-surface [&_svg]:size-4",
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

const DropdownMenuSeparator = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-border", className)} {...props} />
));
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName;

export { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator };
```

`frontend/src/components/ui/select.tsx`:

```tsx
import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const Select = SelectPrimitive.Root;
const SelectGroup = SelectPrimitive.Group;
const SelectValue = SelectPrimitive.Value;

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex h-9 w-full items-center justify-between gap-2 rounded-btn border bg-white px-3 py-2 text-sm placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1",
      className,
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="h-4 w-4 opacity-50" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
));
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName;

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = "popper", ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        "relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-card border bg-white shadow-md",
        position === "popper" && "translate-y-1",
        className,
      )}
      position={position}
      {...props}
    >
      <SelectPrimitive.Viewport
        className={cn("p-1", position === "popper" && "h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]")}
      >
        {children}
      </SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
SelectContent.displayName = SelectPrimitive.Content.displayName;

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex w-full cursor-pointer select-none items-center rounded-btn py-1.5 pl-8 pr-2 text-sm outline-none hover:bg-surface focus:bg-surface",
      className,
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="h-4 w-4" />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = SelectPrimitive.Item.displayName;

export { Select, SelectGroup, SelectValue, SelectTrigger, SelectContent, SelectItem };
```

`frontend/src/components/ui/tooltip.tsx`:

```tsx
import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn("z-50 overflow-hidden rounded-btn bg-sidebar px-3 py-1.5 text-xs text-white", className)}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
```

`frontend/src/components/ui/tabs.tsx`:

```tsx
import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("inline-flex h-9 items-center gap-1 rounded-card bg-surface p-1", className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "inline-flex items-center justify-center whitespace-nowrap rounded-btn px-3 py-1 text-sm font-medium text-text-muted transition-all hover:text-text-primary focus-visible:outline-none data-[state=active]:bg-white data-[state=active]:text-text-primary data-[state=active]:shadow-sm",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content ref={ref} className={cn("mt-2 focus-visible:outline-none", className)} {...props} />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

Expected: 无错误。

- [ ] **Step 4: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/components/ui/ frontend/package.json frontend/package-lock.json && git commit -m "feat(frontend): add shadcn/ui base components"
```

---

## Task 3: 自定义业务组件 + 侧边栏布局

**Files:**
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/StatusBadge.tsx`
- Create: `frontend/src/components/MetricCard.tsx`
- Create: `frontend/src/components/EmptyState.tsx`
- Create: `frontend/src/components/FileDropzone.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 StatusBadge 组件**

```tsx
// frontend/src/components/StatusBadge.tsx
import { Badge } from "@/components/ui/badge";
import type { PointRunStatus, VerdictValue } from "@/types/ui";

const STATUS_CONFIG: Record<string, { label: string; variant: "ok" | "warn" | "err" | "default" | "muted" }> = {
  "合规": { label: "合规通过", variant: "ok" },
  "不合规": { label: "不合规", variant: "err" },
  "存疑": { label: "存疑待定", variant: "warn" },
  pending: { label: "等待中", variant: "muted" },
  running: { label: "审查中", variant: "default" },
  completed: { label: "已完成", variant: "ok" },
  failed: { label: "失败", variant: "err" },
  waiting_retry: { label: "待重试", variant: "warn" },
};

export function StatusBadge({ status }: { status: VerdictValue | PointRunStatus | string }) {
  const config = STATUS_CONFIG[status] ?? { label: status, variant: "muted" as const };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
```

- [ ] **Step 2: 创建 MetricCard 组件**

```tsx
// frontend/src/components/MetricCard.tsx
import { cn } from "@/lib/utils";

const TONE_STYLES = {
  blue: "border-l-accent",
  green: "border-l-status-ok",
  amber: "border-l-status-warn",
  red: "border-l-status-err",
  slate: "border-l-text-muted",
} as const;

export function MetricCard({
  label,
  value,
  tone = "blue",
}: {
  label: string;
  value: string | number;
  tone?: keyof typeof TONE_STYLES;
}) {
  return (
    <div className={cn("rounded-card border bg-surface-card p-4 border-l-4", TONE_STYLES[tone])}>
      <p className="text-sm text-text-muted">{label}</p>
      <p className="text-2xl font-bold text-text-primary mt-1">{value}</p>
    </div>
  );
}
```

- [ ] **Step 3: 创建 EmptyState 组件**

```tsx
// frontend/src/components/EmptyState.tsx
import { FileText } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-light mb-4">
        {icon ?? <FileText className="h-7 w-7 text-accent" />}
      </div>
      <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
      <p className="mt-1 text-sm text-text-muted max-w-sm">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

- [ ] **Step 4: 创建 FileDropzone 组件**

```tsx
// frontend/src/components/FileDropzone.tsx
import { Upload } from "lucide-react";
import { useState, type DragEvent } from "react";
import { cn } from "@/lib/utils";

export function FileDropzone({
  title,
  subtitle,
  accept,
  multiple,
  onSelect,
}: {
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
      <input
        className="sr-only"
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(e) => { onSelect(Array.from(e.target.files || [])); e.target.value = ""; }}
      />
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
```

- [ ] **Step 5: 创建 Sidebar 组件**

基于 Pencil 设计稿（侧边栏宽 240px，深色 #0A0F1E 背景，白色/灰色文字）：

```tsx
// frontend/src/components/Sidebar.tsx
import {
  Bot,
  FileText,
  GitCompareArrows,
  LayoutDashboard,
  LibraryBig,
  ScrollText,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "工作台总览", icon: LayoutDashboard },
  { to: "/audit-library", label: "审核点库", icon: LibraryBig },
  { to: "/ai-review", label: "AI 审核", icon: Bot },
  { to: "/audit-results", label: "审核结果", icon: ScrollText },
  { to: "/workpaper", label: "工作底稿", icon: FileText },
  { to: "/compare", label: "文档对比", icon: GitCompareArrows },
];

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-sidebar flex-col bg-sidebar">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent">
          <span className="text-sm font-bold text-white">G</span>
        </div>
        <div>
          <p className="text-sm font-semibold text-white">GovDoc Auditor</p>
          <p className="text-[11px] text-text-muted">智能审查工作台</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2">
        <p className="mb-2 px-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">
          核心功能
        </p>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-btn px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-accent text-white font-medium"
                        : "text-gray-400 hover:bg-sidebar-hover hover:text-white",
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Status bar */}
      <div className="mx-3 mb-3 rounded-btn bg-sidebar-active p-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-status-ok" />
          <span className="text-xs text-gray-400">系统正常运行</span>
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 6: 重写 AppShell 布局**

```tsx
// frontend/src/components/AppShell.tsx
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";

export function AppShell() {
  return (
    <div className="min-h-screen bg-surface">
      <Sidebar />
      <main className="ml-sidebar min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 7: 更新 App.tsx — 路由引入 DashboardPage**

```tsx
// frontend/src/App.tsx
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AuditLibraryPage } from "./pages/AuditLibraryPage";
import { AIReviewPage } from "./pages/AIReviewPage";
import { WorkpaperPage } from "./pages/WorkpaperPage";
import { AuditResultsPage } from "./pages/AuditResultsPage";
import { DocComparePage } from "./pages/DocComparePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/audit-library" element={<AuditLibraryPage />} />
        <Route path="/ai-review" element={<AIReviewPage />} />
        <Route path="/workpaper" element={<WorkpaperPage />} />
        <Route path="/audit-results" element={<AuditResultsPage />} />
        <Route path="/compare" element={<DocComparePage />} />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 8: 创建 DashboardPage 占位**

临时创建一个最小版本的 DashboardPage，确保路由可用（完整实现在 Task 4）：

```tsx
// frontend/src/pages/DashboardPage.tsx
export function DashboardPage() {
  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold text-text-primary">工作台总览</h1>
      <p className="text-sm text-text-muted mt-1">仪表盘建设中...</p>
    </div>
  );
}
```

- [ ] **Step 9: 验证 TypeScript 编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

- [ ] **Step 10: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/components/Sidebar.tsx frontend/src/components/StatusBadge.tsx frontend/src/components/MetricCard.tsx frontend/src/components/EmptyState.tsx frontend/src/components/FileDropzone.tsx frontend/src/components/AppShell.tsx frontend/src/App.tsx frontend/src/pages/DashboardPage.tsx && git commit -m "feat(frontend): add sidebar layout, custom business components, DashboardPage placeholder"
```

---

## Task 4: Dashboard 页面

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`

基于 Pencil 设计稿 `Screen/Dashboard`：顶栏标题 + 4 个统计卡片 + 近期审核列表表格 + 审查情况侧栏。

- [ ] **Step 1: 完整实现 DashboardPage**

```tsx
// frontend/src/pages/DashboardPage.tsx
import { ArrowRight, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getDashboardStats } from "@/api/v3";
import type { DashboardStats, RecentProject } from "@/types/ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/MetricCard";

const AUDIT_STATUS_LABEL: Record<string, string> = {
  idle: "未开始",
  running: "审查中",
  completed: "已完成",
};

const AUDIT_STATUS_VARIANT: Record<string, "muted" | "default" | "ok"> = {
  idle: "muted",
  running: "default",
  completed: "ok",
};

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    getDashboardStats().then(setStats).catch(() => {});
  }, []);

  return (
    <div className="flex flex-col">
      {/* Topbar */}
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">工作台总览</span>
      </header>

      {/* Page content */}
      <div className="flex-1 space-y-6 p-7">
        {/* Welcome + action */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">项目审查工作台</h2>
            <p className="text-sm text-text-muted">总共 {stats?.checkpoint_count ?? 0} 个审核要点，覆盖 {stats?.recent_projects.length ?? 0} 个项目</p>
          </div>
          <Link to="/ai-review">
            <Button>
              <Plus className="h-4 w-4" />
              创建审查任务
            </Button>
          </Link>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="审核要点" value={stats?.checkpoint_count ?? 0} tone="blue" />
          <MetricCard label="完成审核" value={stats?.completed_audit_count ?? 0} tone="green" />
          <MetricCard label="发现问题" value={stats?.finding_count ?? 0} tone="amber" />
          <MetricCard label="工作底稿" value={stats?.workpaper_count ?? 0} tone="slate" />
        </div>

        {/* Bottom sections */}
        <div className="grid grid-cols-3 gap-5 flex-1">
          {/* Recent audits table */}
          <Card className="col-span-2">
            <CardHeader>
              <CardTitle>近期审核记录</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>项目名称</TableHead>
                    <TableHead>审核要点</TableHead>
                    <TableHead>发现问题</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(stats?.recent_projects ?? []).map((p: RecentProject) => (
                    <TableRow key={p.project_id}>
                      <TableCell className="font-medium">{p.name}</TableCell>
                      <TableCell>{p.point_count}</TableCell>
                      <TableCell>{p.issue_count}</TableCell>
                      <TableCell>
                        <Badge variant={AUDIT_STATUS_VARIANT[p.audit_status] ?? "muted"}>
                          {AUDIT_STATUS_LABEL[p.audit_status] ?? p.audit_status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Link to="/audit-results" className="text-accent hover:underline">
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                  {(stats?.recent_projects ?? []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-text-muted py-8">
                        暂无审核记录
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Audit status sidebar */}
          <Card>
            <CardHeader>
              <CardTitle>审查情况</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(stats?.recent_projects ?? []).map((p: RecentProject) => (
                <div key={p.project_id} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${p.audit_status === "completed" ? "bg-status-ok" : p.audit_status === "running" ? "bg-accent" : "bg-text-muted"}`} />
                    <span className="text-sm text-text-primary">{p.name}</span>
                  </div>
                  <span className="text-xs text-text-muted">
                    {p.issue_count > 0 ? `${p.issue_count} 项问题` : "无问题"}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 验证编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

- [ ] **Step 3: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/pages/DashboardPage.tsx && git commit -m "feat(frontend): implement Dashboard page with stats and recent audits"
```

---

## Task 5: 审核点库页面（含 Extract/Import 子页面 + 编辑/删除模态框）

**Files:**
- Modify: `frontend/src/pages/AuditLibraryPage.tsx`

基于 Pencil 设计稿：`Screen/AuditLibrary` + `Screen/AuditLib-Extract` + `Screen/AuditLib-Import` + `Modal/EditCheckpoint` + `Modal/DeleteConfirm`。

注意：本页面使用 `mode` 状态在 list/extract/import 三种视图间切换，无需新增路由。

- [ ] **Step 1: 完全重写 AuditLibraryPage**

```tsx
// frontend/src/pages/AuditLibraryPage.tsx
import { ArrowLeft, FileSpreadsheet, Pencil, Plus, Search, Sparkles, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import type { CheckpointItem, GovCheckpointPayload } from "@/types/ui";
import { parseCheckpointPayload } from "@/adapters/backendToUi";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StatusBadge } from "@/components/StatusBadge";
import { FileDropzone } from "@/components/FileDropzone";

const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = {
  critical: "err",
  major: "warn",
  minor: "default",
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: "严重",
  major: "重要",
  minor: "一般",
};

export function AuditLibraryPage() {
  const {
    checkpoints,
    extractStatus,
    extractError,
    uploadRuleAndExtract,
    updateCheckpoint,
    deleteCheckpoint,
    importCheckpointFile,
  } = useWorkbench();

  const [mode, setMode] = useState<"list" | "extract" | "import">("list");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  // Extract state
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Import state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported_count: number; skipped_count: number } | null>(null);

  // Edit modal
  const [editingCp, setEditingCp] = useState<CheckpointItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");

  // Delete modal
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deletingTitle, setDeletingTitle] = useState("");

  const parsed = checkpoints
    .map((c) => ({ item: c, payload: parseCheckpointPayload(c.payload_json) }))
    .filter((c): c is { item: CheckpointItem; payload: GovCheckpointPayload } => c.payload != null);

  const categories = [...new Set(parsed.map((c) => c.payload.category))];

  const filtered = parsed.filter((c) => {
    if (categoryFilter !== "all" && c.payload.category !== categoryFilter) return false;
    if (search && !c.payload.title.includes(search) && !c.payload.description.includes(search)) return false;
    return true;
  });

  // Handlers
  async function handleExtract() {
    if (!uploadTitle || !uploadFile) return;
    setUploading(true);
    try { await uploadRuleAndExtract(uploadTitle, uploadFile); }
    finally { setUploading(false); }
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    try {
      const result = await importCheckpointFile(importFile);
      setImportResult(result);
      setImportFile(null);
    } finally { setImporting(false); }
  }

  function openEdit(item: CheckpointItem) {
    const p = parseCheckpointPayload(item.payload_json);
    if (!p) return;
    setEditingCp(item);
    setEditTitle(p.title);
    setEditDesc(p.description);
  }

  async function saveEdit() {
    if (!editingCp) return;
    const p = parseCheckpointPayload(editingCp.payload_json);
    if (!p) return;
    await updateCheckpoint(editingCp.id, { ...p, title: editTitle, description: editDesc });
    setEditingCp(null);
  }

  function openDelete(item: CheckpointItem) {
    const p = parseCheckpointPayload(item.payload_json);
    setDeletingId(item.id);
    setDeletingTitle(p?.title ?? "");
  }

  async function confirmDelete() {
    if (!deletingId) return;
    await deleteCheckpoint(deletingId);
    setDeletingId(null);
  }

  // ── Render ──

  if (mode === "extract") {
    return (
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-text-primary">审核点库</span>
            <span className="text-text-muted">/</span>
            <span className="text-sm text-text-muted">AI 智能提取</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setMode("list")}>
            <ArrowLeft className="h-4 w-4" /> 返回列表
          </Button>
        </header>
        <div className="space-y-6 p-7">
          <div>
            <h2 className="text-lg font-semibold">AI 智能提取审查要点</h2>
            <p className="text-sm text-text-muted">上传法规或制度文件，AI 将自动提取并入库审查要点</p>
          </div>
          <div className="grid grid-cols-3 gap-6">
            <Card className="col-span-2">
              <CardHeader><CardTitle>上传规范文件</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">法规标题</label>
                  <Input placeholder="例如：政府采购法实施条例" value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">法规原文</label>
                  {uploadFile ? (
                    <div className="flex items-center justify-between rounded-card border p-3">
                      <span className="text-sm">{uploadFile.name}</span>
                      <button className="text-text-muted hover:text-text-primary text-sm" onClick={() => setUploadFile(null)}>移除</button>
                    </div>
                  ) : (
                    <FileDropzone title="选择或拖入法规文件" subtitle="支持 .md, .pdf, .docx" accept=".md,.pdf,.docx" onSelect={(f) => setUploadFile(f[0] ?? null)} />
                  )}
                </div>
                {extractStatus && extractStatus !== "draft_ready" && (
                  <div className={cn("rounded-btn p-3 text-sm", extractStatus === "failed" ? "bg-status-err-bg text-status-err" : "bg-status-info-bg text-status-info")}>
                    {extractStatus === "pending" ? "等待处理..." : extractStatus === "running" ? "正在提取审核点..." : extractError ?? "处理失败"}
                  </div>
                )}
                {extractStatus === "draft_ready" && (
                  <div className="rounded-btn bg-status-ok-bg p-3 text-sm text-status-ok">提取完成，审核点已入库。</div>
                )}
                <Button disabled={!uploadTitle || !uploadFile || uploading || extractStatus === "running"} onClick={handleExtract}>
                  <Sparkles className="h-4 w-4" /> 开始抽取
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>提取说明</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm text-text-muted leading-relaxed">
                  系统将从上传的法规原文中自动提取审查要点。每个要点包含标题、描述、法条引用和严重程度分级。
                </p>
                <p className="mt-3 text-sm text-text-muted leading-relaxed">
                  提取完成后，审查要点将自动入库。您可以在列表页面中查看和编辑。
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "import") {
    return (
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-text-primary">审核点库</span>
            <span className="text-text-muted">/</span>
            <span className="text-sm text-text-muted">导入审查点表格</span>
          </div>
          <Button variant="secondary" size="sm" onClick={() => { setMode("list"); setImportResult(null); }}>
            <ArrowLeft className="h-4 w-4" /> 返回列表
          </Button>
        </header>
        <div className="flex items-start justify-center p-7">
          <Card className="w-full max-w-xl">
            <CardHeader>
              <CardTitle>导入审查点表格</CardTitle>
              <p className="text-sm text-text-muted">上传已整理好的审查点表格，系统将自动解析并写入审核点库。</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">审查点文件</label>
                {importFile ? (
                  <div className="flex items-center justify-between rounded-card border p-3">
                    <span className="text-sm">{importFile.name}</span>
                    <button className="text-text-muted hover:text-text-primary text-sm" onClick={() => setImportFile(null)}>移除</button>
                  </div>
                ) : (
                  <FileDropzone title="选择审查点表格" subtitle="支持 .xls, .xlsx, .csv" accept=".xls,.xlsx,.csv" onSelect={(f) => setImportFile(f[0] ?? null)} />
                )}
              </div>
              {importResult && (
                <div className="rounded-btn bg-status-ok-bg p-3 text-sm text-status-ok">
                  成功导入 {importResult.imported_count} 条审查点{importResult.skipped_count > 0 ? `，跳过 ${importResult.skipped_count} 条` : ""}
                </div>
              )}
              <Button disabled={!importFile || importing} onClick={handleImport}>
                <FileSpreadsheet className="h-4 w-4" /> 启动解析并导入库
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // ── List mode ──
  return (
    <>
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <span className="text-base font-semibold text-text-primary">审核点库</span>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
              <Input className="pl-8 w-56" placeholder="搜索审查要点..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary"><Upload className="h-4 w-4" /> 上传</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setMode("extract")}>
                  <Sparkles className="h-4 w-4" /> AI 提取
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setMode("import")}>
                  <FileSpreadsheet className="h-4 w-4" /> 导入审查点表格
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <div className="space-y-5 p-7">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">审核点管理</h2>
              <p className="text-sm text-text-muted">已收录 {checkpoints.length} 个审查要点，支持 AI 提取或表格批量导入</p>
            </div>
          </div>

          {/* Category filter */}
          <div className="flex items-center gap-2">
            <button onClick={() => setCategoryFilter("all")} className={cn("rounded-full px-3 py-1 text-xs font-medium transition-colors", categoryFilter === "all" ? "bg-accent text-white" : "bg-surface text-text-secondary hover:bg-gray-200")}>
              全部分类
            </button>
            {categories.map((cat) => (
              <button key={cat} onClick={() => setCategoryFilter(cat)} className={cn("rounded-full px-3 py-1 text-xs font-medium transition-colors", categoryFilter === cat ? "bg-accent text-white" : "bg-surface text-text-secondary hover:bg-gray-200")}>
                {cat}
              </button>
            ))}
          </div>

          {/* Checkpoint table */}
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40%]">审查要点</TableHead>
                  <TableHead>分类</TableHead>
                  <TableHead>严重程度</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="w-20 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map(({ item, payload }) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium text-text-primary">{payload.title}</p>
                        <p className="text-xs text-text-muted mt-0.5 line-clamp-1">{payload.description}</p>
                      </div>
                    </TableCell>
                    <TableCell><Badge variant="outline">{payload.category}</Badge></TableCell>
                    <TableCell>
                      <Badge variant={SEVERITY_VARIANT[payload.severity] ?? "muted"}>
                        {SEVERITY_LABEL[payload.severity] ?? payload.severity}
                      </Badge>
                    </TableCell>
                    <TableCell><StatusBadge status="completed" /></TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => openDelete(item)}>
                          <Trash2 className="h-3.5 w-3.5 text-status-err" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {filtered.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-text-muted py-12">
                      暂无审核点，请点击「上传」开始创建。
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
        </div>
      </div>

      {/* Edit modal */}
      <Dialog open={editingCp != null} onOpenChange={(open) => { if (!open) setEditingCp(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑审查要点</DialogTitle>
            <DialogDescription>修改审查要点的标题和描述内容</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 p-5">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">标题</label>
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">描述</label>
              <Textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setEditingCp(null)}>取消</Button>
            <Button onClick={saveEdit}>保存修改</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete modal */}
      <Dialog open={deletingId != null} onOpenChange={(open) => { if (!open) setDeletingId(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 p-5">
            <div className="flex items-center gap-2 rounded-btn border border-status-err-border bg-status-err-bg p-3">
              <span className="text-sm text-status-err font-medium">此操作不可撤销</span>
            </div>
            <p className="text-sm text-text-secondary">
              确定要删除审查要点「{deletingTitle}」吗？删除后相关的审查记录将不受影响。
            </p>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeletingId(null)}>取消</Button>
            <Button variant="danger" onClick={confirmDelete}>确认删除</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

- [ ] **Step 2: 验证编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

- [ ] **Step 3: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/pages/AuditLibraryPage.tsx && git commit -m "feat(frontend): rewrite AuditLibrary with table view, extract/import sub-pages, edit/delete modals"
```

---

## Task 6: AI 审核页面（Setup + Running + ProgressTimeline）

**Files:**
- Modify: `frontend/src/pages/AIReviewPage.tsx`
- Create: `frontend/src/components/ProgressTimeline.tsx`

基于 Pencil 设计稿：`Screen/AIReview-Setup`（3 步向导）+ `Screen/AIReview-Running`（左栏状态列表 + 右栏 6 步时间线）。

当前 AIReviewPage 的逻辑（useProjectWorkflow + useAuditRun hooks）保持不变，仅重写 JSX 和样式。根据 `auditProgress` 是否存在切换 Setup/Running 视图。

- [ ] **Step 1: 创建 ProgressTimeline 组件**

基于 Pencil 组件 `Component/ProgressTimeline`，6 步映射 PES 3 阶段：

```tsx
// frontend/src/components/ProgressTimeline.tsx
import { Check, Loader2, AlertCircle, Clock, RefreshCw } from "lucide-react";
import type { AuditPointRun, GovCheckpointPayload } from "@/types/ui";
import { cn } from "@/lib/utils";

type PhaseStep = {
  label: string;
  phase: "plan" | "execute" | "summarize";
};

const STEPS: PhaseStep[] = [
  { label: "读取审查要点", phase: "plan" },
  { label: "检索招标文书", phase: "plan" },
  { label: "制定审核策略", phase: "plan" },
  { label: "定位证据段落", phase: "execute" },
  { label: "分析证据形成意见", phase: "execute" },
  { label: "汇总审查结果", phase: "summarize" },
];

const PHASE_ORDER = { plan: 0, execute: 1, summarize: 2 };

function getStepStatus(
  stepIndex: number,
  currentPhase: string | null,
  pointStatus: string,
): "done" | "active" | "pending" | "error" {
  if (pointStatus === "completed") return "done";
  if (pointStatus === "failed") {
    if (!currentPhase) return stepIndex === 0 ? "error" : "pending";
    const phaseIdx = PHASE_ORDER[currentPhase as keyof typeof PHASE_ORDER] ?? -1;
    const stepPhase = STEPS[stepIndex].phase;
    const stepPhaseIdx = PHASE_ORDER[stepPhase];
    if (stepPhaseIdx < phaseIdx) return "done";
    if (stepPhaseIdx === phaseIdx) return "error";
    return "pending";
  }
  if (pointStatus !== "running" || !currentPhase) return "pending";
  const phaseIdx = PHASE_ORDER[currentPhase as keyof typeof PHASE_ORDER] ?? -1;
  const stepPhase = STEPS[stepIndex].phase;
  const stepPhaseIdx = PHASE_ORDER[stepPhase];
  if (stepPhaseIdx < phaseIdx) return "done";
  if (stepPhaseIdx === phaseIdx) {
    const firstOfPhase = STEPS.findIndex((s) => s.phase === stepPhase);
    return stepIndex === firstOfPhase ? "active" : "pending";
  }
  return "pending";
}

export function ProgressTimeline({
  pointRun,
  checkpoint,
  onRetry,
}: {
  pointRun: AuditPointRun;
  checkpoint: GovCheckpointPayload | null;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-card border bg-surface-card p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-1">
        {checkpoint?.title ?? "审查进度"}
      </h3>
      {pointRun.started_at && (
        <p className="text-xs text-text-muted mb-4">
          开始于 {new Date(pointRun.started_at).toLocaleTimeString("zh-CN")}
        </p>
      )}
      <div className="space-y-0">
        {STEPS.map((step, i) => {
          const status = getStepStatus(i, pointRun.current_phase, pointRun.status);
          const isLast = i === STEPS.length - 1;
          return (
            <div key={i} className="flex gap-3">
              {/* Timeline dot + line */}
              <div className="flex flex-col items-center">
                <div className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                  status === "done" && "bg-status-ok",
                  status === "active" && "bg-accent",
                  status === "error" && "bg-status-err",
                  status === "pending" && "border-2 border-gray-200 bg-white",
                )}>
                  {status === "done" && <Check className="h-3.5 w-3.5 text-white" />}
                  {status === "active" && <Loader2 className="h-3.5 w-3.5 text-white animate-spin" />}
                  {status === "error" && <AlertCircle className="h-3.5 w-3.5 text-white" />}
                  {status === "pending" && <Clock className="h-3 w-3 text-gray-300" />}
                </div>
                {!isLast && (
                  <div className={cn("w-0.5 flex-1 min-h-[24px]", status === "done" ? "bg-status-ok" : "bg-gray-200")} />
                )}
              </div>
              {/* Content */}
              <div className="pb-4">
                <p className={cn(
                  "text-sm font-medium",
                  status === "done" && "text-text-primary",
                  status === "active" && "text-accent",
                  status === "error" && "text-status-err",
                  status === "pending" && "text-text-muted",
                )}>
                  {step.label}
                </p>
                {status === "active" && (
                  <p className="text-xs text-text-muted mt-0.5">正在处理中...</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {pointRun.status === "failed" && onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 flex items-center gap-1.5 text-sm text-accent hover:underline"
        >
          <RefreshCw className="h-3.5 w-3.5" /> 点击重试
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 重写 AIReviewPage**

```tsx
// frontend/src/pages/AIReviewPage.tsx
import { Check, ChevronRight, Loader2, Plus } from "lucide-react";
import { useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { useProjectWorkflow } from "@/hooks/useProjectWorkflow";
import { useAuditRun } from "@/hooks/useAuditRun";
import { parseCheckpointPayload, parseFindingJson } from "@/adapters/backendToUi";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { FileDropzone } from "@/components/FileDropzone";
import { EmptyState } from "@/components/EmptyState";
import { ProgressTimeline } from "@/components/ProgressTimeline";
import { PointInsight } from "@/components/PointInsight";

export function AIReviewPage() {
  const {
    projects,
    activeProject,
    selectedProjectId,
    setSelectedProjectId,
    auditInputDocs,
    finalCheckpoints,
    auditProgress,
    retryPointRun,
  } = useWorkbench();

  const wf = useProjectWorkflow();
  const auditRun = useAuditRun();
  const [detailPrId, setDetailPrId] = useState<string | null>(null);
  const [selectedTimelinePrId, setSelectedTimelinePrId] = useState<string | null>(null);

  const inputDocs = activeProject ? auditInputDocs[activeProject.id] : undefined;
  const mainDoc = inputDocs?.mainDoc;
  const isRunning = auditProgress != null;
  const pointRuns = auditProgress?.point_runs ?? [];
  const progress = auditProgress ? (auditProgress.total_count > 0 ? (auditProgress.processed_count / auditProgress.total_count) * 100 : 0) : 0;
  const completedCount = pointRuns.filter((p) => p.status === "completed").length;
  const failedCount = pointRuns.filter((p) => p.status === "failed").length;
  const runningCount = pointRuns.filter((p) => p.status === "running").length;

  const selectedTimelinePr = pointRuns.find((p) => p.id === selectedTimelinePrId) ?? pointRuns.find((p) => p.status === "running") ?? pointRuns[0];

  // ── Running view ──
  if (isRunning) {
    return (
      <>
        <div className="flex flex-col h-screen">
          <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-text-primary">AI 审核</span>
              <Badge variant="default">审核进行中</Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">已完成 {auditProgress.processed_count}/{auditProgress.total_count}</span>
              <span className="text-xs text-text-muted">预估剩余 {Math.max(0, auditProgress.total_count - auditProgress.processed_count) * 3} 分钟</span>
            </div>
          </header>
          <div className="flex-1 space-y-5 p-7 overflow-auto">
            <div>
              <h2 className="text-lg font-semibold">{activeProject?.name ?? "审核任务"}</h2>
              <p className="text-sm text-text-muted">共 {auditProgress.total_count} 个审核要点，已处理 {auditProgress.processed_count} 个</p>
            </div>

            {/* Progress bar section */}
            <Card>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">审核进度</span>
                  <span className="font-medium">{Math.round(progress)}%</span>
                </div>
                <Progress value={progress} />
                <div className="grid grid-cols-4 gap-3">
                  <MetricCard label="总审核点" value={auditProgress.total_count} tone="blue" />
                  <MetricCard label="已完成" value={completedCount} tone="green" />
                  <MetricCard label="审查中" value={runningCount} tone="amber" />
                  <MetricCard label="失败" value={failedCount} tone="red" />
                </div>
              </CardContent>
            </Card>

            {/* Main grid: left point list + right timeline */}
            <div className="grid grid-cols-2 gap-5">
              {/* Left: point status list */}
              <Card>
                <CardHeader><CardTitle>审核要点</CardTitle></CardHeader>
                <CardContent className="p-0">
                  <div className="max-h-[400px] overflow-auto">
                    {pointRuns.map((pr) => {
                      const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
                      const title = cp?.parsed?.title ?? pr.checkpoint_final_id.slice(0, 8);
                      return (
                        <button
                          key={pr.id}
                          className={cn(
                            "flex w-full items-center justify-between px-4 py-3 text-left border-b last:border-0 hover:bg-surface transition-colors",
                            pr.id === selectedTimelinePr?.id && "bg-accent-light",
                          )}
                          onClick={() => setSelectedTimelinePrId(pr.id)}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={cn(
                              "h-2 w-2 shrink-0 rounded-full",
                              pr.status === "completed" && "bg-status-ok",
                              pr.status === "running" && "bg-accent",
                              pr.status === "failed" && "bg-status-err",
                              pr.status === "pending" && "bg-gray-300",
                            )} />
                            <span className="text-sm truncate">{title}</span>
                          </div>
                          <StatusBadge status={pr.status} />
                        </button>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Right: timeline for selected point */}
              {selectedTimelinePr && (
                <ProgressTimeline
                  pointRun={selectedTimelinePr}
                  checkpoint={finalCheckpoints.find((c) => c.id === selectedTimelinePr.checkpoint_final_id)?.parsed ?? null}
                  onRetry={selectedTimelinePr.status === "failed" ? () => retryPointRun(selectedTimelinePr.id) : undefined}
                />
              )}
            </div>
          </div>
        </div>

        {/* Point detail modal */}
        <Dialog open={detailPrId != null} onOpenChange={(o) => { if (!o) setDetailPrId(null); }}>
          <DialogContent className="max-w-3xl">
            <DialogHeader><DialogTitle>审核点详情</DialogTitle></DialogHeader>
            {detailPrId && (() => {
              const pr = pointRuns.find((p) => p.id === detailPrId);
              const cp = pr ? finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id)?.parsed ?? null : null;
              if (!cp || !pr) return <EmptyState title="无法加载" description="找不到该审核点的数据。" />;
              return <div className="p-5"><PointInsight checkpoint={cp} finding={parseFindingJson(pr.finding_json ?? null)} pointStatus={pr.status} /></div>;
            })()}
          </DialogContent>
        </Dialog>
      </>
    );
  }

  // ── Setup view (3-step wizard) ──
  const step = !selectedProjectId || !activeProject ? 1 : !mainDoc ? 2 : 3;

  return (
    <div className="flex flex-col">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">AI 审核</span>
      </header>
      <div className="space-y-6 p-7">
        <div>
          <h2 className="text-lg font-semibold">新建审查任务</h2>
          <p className="text-sm text-text-muted">上传招标文件，选择审查要点，启动 AI 自动审核</p>
        </div>

        {/* Steps indicator */}
        <div className="flex items-center gap-3">
          {[
            { n: 1, label: "选择或创建项目" },
            { n: 2, label: "上传招标文件" },
            { n: 3, label: "选择审查要点" },
          ].map((s, i) => (
            <div key={s.n} className="flex items-center gap-3">
              <div className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium",
                step > s.n ? "bg-accent text-white" : step === s.n ? "bg-accent text-white" : "border border-gray-300 text-text-muted",
              )}>
                {step > s.n ? <Check className="h-4 w-4" /> : s.n}
              </div>
              <span className={cn("text-sm", step >= s.n ? "text-text-primary font-medium" : "text-text-muted")}>{s.label}</span>
              {i < 2 && <ChevronRight className="h-4 w-4 text-text-muted" />}
            </div>
          ))}
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-2 gap-6">
          {/* Left: steps 1 & 2 */}
          <div className="space-y-6">
            {/* Step 1: Project */}
            <Card>
              <CardHeader>
                <CardTitle>第一步：选择或创建项目</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">选择现有项目</label>
                  <select
                    className="flex h-9 w-full rounded-btn border bg-white px-3 py-1 text-sm"
                    value={selectedProjectId ?? ""}
                    onChange={(e) => setSelectedProjectId(e.target.value || null)}
                  >
                    <option value="">选择项目...</option>
                    {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">或创建新项目</label>
                  <div className="flex gap-2">
                    <Input placeholder="输入项目名称" value={wf.newProjectName} onChange={(e) => wf.setNewProjectName(e.target.value)} />
                    <Button variant="secondary" disabled={!wf.newProjectName || wf.creating} onClick={wf.handleCreateProject}>
                      <Plus className="h-4 w-4" /> 创建
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Step 2: Upload tender */}
            {activeProject && (
              <Card>
                <CardHeader><CardTitle>第二步：上传招标文件</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {mainDoc ? (
                    <div className="flex items-center gap-2 rounded-card border p-3 bg-status-ok-bg">
                      <Check className="h-4 w-4 text-status-ok" />
                      <span className="text-sm">{mainDoc.filename}</span>
                    </div>
                  ) : (
                    <FileDropzone
                      title="点击选择或拖入招标文件"
                      subtitle="支持 .docx, .pdf"
                      accept=".docx,.pdf"
                      onSelect={(files) => { if (files[0]) wf.setMainTenderFile(files[0]); }}
                    />
                  )}
                  {wf.mainTenderFile && !mainDoc && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm">{wf.mainTenderFile.name}</span>
                      <Button size="sm" disabled={wf.uploadingTender} onClick={wf.handleUploadTender}>
                        {wf.uploadingTender ? <Loader2 className="h-4 w-4 animate-spin" /> : "上传"}
                      </Button>
                    </div>
                  )}
                  {wf.uploadError && <p className="text-sm text-status-err">{wf.uploadError}</p>}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right: Step 3 checkpoint picker */}
          <Card>
            <CardHeader><CardTitle>第三步：选择审查要点</CardTitle></CardHeader>
            <CardContent>
              {mainDoc ? (
                <div className="space-y-3">
                  <div className="max-h-[360px] overflow-auto space-y-1">
                    {finalCheckpoints.map((cp) => (
                      <label key={cp.id} className="flex items-center gap-3 rounded-btn p-2 hover:bg-surface cursor-pointer">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-300 text-accent"
                          checked={auditRun.selectedCpIds.has(cp.id)}
                          onChange={() => auditRun.toggleCheckpoint(cp.id)}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-text-primary truncate">{cp.parsed.title}</p>
                          <p className="text-xs text-text-muted truncate">{cp.parsed.category}</p>
                        </div>
                      </label>
                    ))}
                    {finalCheckpoints.length === 0 && (
                      <p className="text-sm text-text-muted py-4 text-center">暂无审查要点，请先在审核点库中创建。</p>
                    )}
                  </div>
                  <Button
                    className="w-full"
                    disabled={auditRun.selectedCpIds.size === 0 || auditRun.startingAudit}
                    onClick={auditRun.handleStartAudit}
                  >
                    {auditRun.startingAudit ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    开始审核（{auditRun.selectedCpIds.size} 个要点）
                  </Button>
                </div>
              ) : (
                <EmptyState title="请先完成前两步" description="选择项目并上传招标文件后，即可选择审查要点。" />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 验证编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

- [ ] **Step 4: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/components/ProgressTimeline.tsx frontend/src/pages/AIReviewPage.tsx && git commit -m "feat(frontend): rewrite AI Review page with setup wizard and running progress timeline"
```

---

## Task 7: 审核结果页面

**Files:**
- Modify: `frontend/src/pages/AuditResultsPage.tsx`
- Modify: `frontend/src/components/PointInsight.tsx`

基于 Pencil 设计稿 `Screen/AuditResults`：左侧 320px 审核点列表 + 右侧详情面板（审查意见 + 整改建议 + 原文引用 + 法条依据 + 人工反馈）。

- [ ] **Step 1: 更新 PointInsight 组件为 Tailwind 样式**

```tsx
// frontend/src/components/PointInsight.tsx
import type { GovCheckpointPayload, GovFinding, PointRunStatus } from "@/types/ui";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";

const SEVERITY_LABEL: Record<string, string> = { critical: "高风险", major: "中风险", minor: "低风险" };
const SEVERITY_VARIANT: Record<string, "err" | "warn" | "default"> = { critical: "err", major: "warn", minor: "default" };

export function PointInsight({
  checkpoint,
  finding,
  pointStatus,
}: {
  checkpoint: GovCheckpointPayload;
  finding: GovFinding | null;
  pointStatus: PointRunStatus;
}) {
  const verdict = finding?.verdict;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h3 className="text-base font-semibold text-text-primary">{checkpoint.title}</h3>
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          {verdict && <StatusBadge status={verdict.verdict} />}
          <Badge variant={SEVERITY_VARIANT[checkpoint.severity] ?? "muted"}>
            {SEVERITY_LABEL[checkpoint.severity] ?? checkpoint.severity}
          </Badge>
          <Badge variant="outline">{checkpoint.category}</Badge>
        </div>
      </div>

      {!finding && pointStatus !== "completed" && (
        <p className="text-sm text-text-muted">该审核点尚未完成审查。</p>
      )}

      {verdict && (
        <>
          {/* Two-column: 审查意见 + 整改建议 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">审查意见</h4>
              <p className="text-sm text-text-secondary leading-relaxed">{verdict.rationale}</p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">整改建议</h4>
              <p className="text-sm text-text-secondary leading-relaxed">{verdict.suggestion}</p>
            </div>
          </div>

          {/* 原文引用 */}
          {verdict.evidence_quotes.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">原文引用</h4>
              <div className="space-y-2">
                {verdict.evidence_quotes.map((q, i) => (
                  <blockquote key={i} className="border-l-2 border-accent pl-3 text-sm text-text-secondary italic">
                    "{q}"
                  </blockquote>
                ))}
              </div>
            </div>
          )}

          {/* 法条依据 */}
          {checkpoint.legal_basis.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">法条依据</h4>
              <div className="space-y-2">
                {checkpoint.legal_basis.map((lb, i) => (
                  <div key={i} className="rounded-btn bg-accent-light px-3 py-2">
                    <p className="text-sm font-medium text-accent">{lb.law_name} {lb.article}</p>
                    {lb.quote && <p className="text-xs text-text-secondary mt-0.5">{lb.quote}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 重写 AuditResultsPage**

```tsx
// frontend/src/pages/AuditResultsPage.tsx
import { RefreshCw, Send } from "lucide-react";
import { useEffect, useState } from "react";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { parseFindingJson, verdictToStatus } from "@/adapters/backendToUi";
import { listComments, createComment } from "@/api/v3";
import type { Comment } from "@/types/ui";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { PointInsight } from "@/components/PointInsight";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export function AuditResultsPage() {
  const {
    auditRuns,
    auditProgress,
    selectedAuditRunId,
    setSelectedAuditRunId,
    selectedPointRunId,
    setSelectedPointRunId,
    finalCheckpoints,
    retryPointRun,
  } = useWorkbench();

  const pointRuns = auditProgress?.point_runs ?? [];
  const activePr = pointRuns.find((pr) => pr.id === selectedPointRunId);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!selectedPointRunId) return;
    listComments("AuditPointRun", selectedPointRunId).then(setComments).catch(() => {});
  }, [selectedPointRunId]);

  async function handleRetry(prId: string) {
    setRetryingId(prId);
    try { await retryPointRun(prId); } finally { setRetryingId(null); }
  }

  async function handleSubmitFeedback() {
    if (!selectedPointRunId || !feedbackText.trim()) return;
    setSubmitting(true);
    try {
      const c = await createComment("AuditPointRun", selectedPointRunId, "reviewer", feedbackText);
      setComments((prev) => [c, ...prev]);
      setFeedbackText("");
    } finally { setSubmitting(false); }
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Topbar */}
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">审核结果</span>
        <div className="flex items-center gap-2">
          <Select value={selectedAuditRunId ?? ""} onValueChange={(v) => setSelectedAuditRunId(v || null)}>
            <SelectTrigger className="w-56">
              <SelectValue placeholder="选择审核运行" />
            </SelectTrigger>
            <SelectContent>
              {auditRuns.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.project_name || r.id.slice(0, 8)} ({r.status})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </header>

      {pointRuns.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <EmptyState title="暂无审核结果" description="请先完成一次审核运行。" />
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          {/* Left: point list (320px) */}
          <div className="w-80 shrink-0 border-r bg-surface-card overflow-auto">
            <div className="p-4 border-b">
              <p className="text-sm font-medium text-text-primary">审核要点列表</p>
              <p className="text-xs text-text-muted">{pointRuns.length} 个审核点</p>
            </div>
            <ScrollArea className="h-[calc(100vh-120px)]">
              {pointRuns.map((pr) => {
                const cp = finalCheckpoints.find((c) => c.id === pr.checkpoint_final_id);
                const title = cp?.parsed?.title ?? pr.checkpoint_final_id.slice(0, 8);
                const finding = parseFindingJson(pr.finding_json);
                const status = verdictToStatus(finding, pr.status);
                return (
                  <button
                    key={pr.id}
                    className={cn(
                      "flex w-full items-center justify-between px-4 py-3 text-left border-b hover:bg-surface transition-colors",
                      pr.id === selectedPointRunId && "bg-accent-light border-l-2 border-l-accent",
                    )}
                    onClick={() => setSelectedPointRunId(pr.id)}
                  >
                    <span className="text-sm truncate mr-2">{title}</span>
                    <StatusBadge status={finding?.verdict?.verdict ?? pr.status} />
                  </button>
                );
              })}
            </ScrollArea>
          </div>

          {/* Right: detail panel */}
          <div className="flex-1 overflow-auto p-7 space-y-5">
            {activePr ? (() => {
              const cp = finalCheckpoints.find((c) => c.id === activePr.checkpoint_final_id);
              const finding = parseFindingJson(activePr.finding_json);
              if (!cp?.parsed) return <EmptyState title="无法加载" description="找不到该审核点数据。" />;
              return (
                <>
                  <PointInsight checkpoint={cp.parsed} finding={finding} pointStatus={activePr.status} />

                  {(activePr.status === "failed" || activePr.status === "waiting_retry") && (
                    <Button variant="secondary" disabled={retryingId === activePr.id} onClick={() => handleRetry(activePr.id)}>
                      <RefreshCw className={cn("h-4 w-4", retryingId === activePr.id && "animate-spin")} />
                      {retryingId === activePr.id ? "正在重试..." : "重试此审核点"}
                    </Button>
                  )}

                  <Separator />

                  {/* Feedback section */}
                  <div>
                    <h4 className="text-sm font-medium text-text-primary mb-3">人工反馈</h4>
                    <div className="flex gap-2 mb-4">
                      <Textarea
                        placeholder="输入审查意见或修改建议..."
                        value={feedbackText}
                        onChange={(e) => setFeedbackText(e.target.value)}
                        className="flex-1"
                      />
                      <Button
                        size="icon"
                        disabled={!feedbackText.trim() || submitting}
                        onClick={handleSubmitFeedback}
                      >
                        <Send className="h-4 w-4" />
                      </Button>
                    </div>
                    {comments.map((c) => (
                      <div key={c.id} className="border-b py-2.5 last:border-0">
                        <p className="text-sm text-text-primary">{c.text}</p>
                        <p className="text-xs text-text-muted mt-1">{c.author} · {new Date(c.created_at).toLocaleString("zh-CN")}</p>
                      </div>
                    ))}
                  </div>
                </>
              );
            })() : (
              <div className="flex-1 flex items-center justify-center h-full">
                <EmptyState title="请选择审核点" description="点击左侧列表查看详细审查结果。" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 验证编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

- [ ] **Step 4: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/pages/AuditResultsPage.tsx frontend/src/components/PointInsight.tsx && git commit -m "feat(frontend): rewrite AuditResults page with split panel and feedback"
```

---

## Task 8: 工作底稿页面

**Files:**
- Modify: `frontend/src/pages/WorkpaperPage.tsx`
- Modify: `frontend/src/components/WorkpaperEditor.tsx`

基于 Pencil 设计稿 `Screen/Workpaper` + `Screen/Workpaper-Empty`。

- [ ] **Step 1: 更新 WorkpaperEditor 样式**

```tsx
// frontend/src/components/WorkpaperEditor.tsx
import { Bold, Heading2, List, Quote } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";

export function WorkpaperEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (html: string) => void;
}) {
  const editorRef = useRef<HTMLDivElement>(null);

  function exec(command: string, arg?: string) {
    document.execCommand(command, false, arg);
    if (editorRef.current) onChange(editorRef.current.innerHTML);
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b px-3 py-2">
        <Button variant="ghost" size="icon" onClick={() => exec("bold")} title="加粗">
          <Bold className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => exec("formatBlock", "H2")} title="标题">
          <Heading2 className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => exec("formatBlock", "BLOCKQUOTE")} title="引用">
          <Quote className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => exec("insertOrderedList")} title="有序列表">
          <List className="h-4 w-4" />
        </Button>
      </div>
      {/* Editor */}
      <div
        ref={editorRef}
        contentEditable
        className="min-h-[500px] p-10 text-sm leading-relaxed text-text-primary focus:outline-none prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: value }}
        onInput={() => {
          if (editorRef.current) onChange(editorRef.current.innerHTML);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: 重写 WorkpaperPage**

```tsx
// frontend/src/pages/WorkpaperPage.tsx
import { Download, FileDown, FileText, Save } from "lucide-react";
import { Link } from "react-router-dom";

import { useWorkbench } from "@/context/V3WorkbenchContext";
import { getWorkpaperFinalDocxUrl } from "@/api/v3";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { WorkpaperEditor } from "@/components/WorkpaperEditor";
import { EmptyState } from "@/components/EmptyState";

export function WorkpaperPage() {
  const {
    activeAuditRun,
    auditRuns,
    selectedAuditRunId,
    setSelectedAuditRunId,
    workpaperHtml,
    workpaperJson,
    workpaperSaveStatus,
    finalizeStatus,
    loadWorkpaper,
    setWorkpaperHtml,
    finalizeWorkpaper,
  } = useWorkbench();

  async function handleSelectRun(id: string) {
    setSelectedAuditRunId(id || null);
    if (id) await loadWorkpaper(id);
  }

  function handleExport() {
    if (!activeAuditRun) return;
    window.open(getWorkpaperFinalDocxUrl(activeAuditRun.id), "_blank");
  }

  // Empty state
  if (!activeAuditRun && auditRuns.length === 0) {
    return (
      <div className="flex flex-col h-screen">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <span className="text-base font-semibold text-text-primary">工作底稿</span>
        </header>
        <div className="flex-1 flex items-center justify-center">
          <EmptyState
            icon={<FileText className="h-7 w-7 text-accent" />}
            title="暂无工作底稿"
            description="完成一次审查任务后，系统将自动生成工作底稿"
            action={
              <div className="flex gap-3">
                <Link to="/ai-review"><Button>创建审查任务</Button></Link>
                <Link to="/audit-results"><Button variant="secondary">查看历史记录</Button></Link>
              </div>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Topbar */}
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <div className="flex items-center gap-3">
          <span className="text-base font-semibold text-text-primary">工作底稿</span>
          <Select value={selectedAuditRunId ?? ""} onValueChange={handleSelectRun}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="选择审核运行" />
            </SelectTrigger>
            <SelectContent>
              {auditRuns.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.project_name || r.id.slice(0, 8)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => {}}>
            <Save className="h-4 w-4" /> 保存
          </Button>
          <Button variant="secondary" size="sm" disabled={finalizeStatus === "finalizing"} onClick={() => activeAuditRun && finalizeWorkpaper(activeAuditRun.id)}>
            <FileDown className="h-4 w-4" /> {finalizeStatus === "finalizing" ? "定稿中..." : "定稿"}
          </Button>
          <Button size="sm" disabled={finalizeStatus !== "finalized"} onClick={handleExport}>
            <Download className="h-4 w-4" /> 导出 Word
          </Button>
        </div>
      </header>

      {/* Main: editor + side panel */}
      <div className="flex flex-1 overflow-hidden p-6 gap-5">
        {/* Editor */}
        <Card className="flex-1 overflow-auto">
          {activeAuditRun ? (
            <WorkpaperEditor value={workpaperHtml} onChange={setWorkpaperHtml} />
          ) : (
            <div className="flex items-center justify-center h-full text-text-muted text-sm">
              请先选择一个审核运行
            </div>
          )}
        </Card>

        {/* Side panel */}
        <div className="w-72 shrink-0 space-y-4">
          <Card>
            <CardHeader><CardTitle>文档信息</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-muted">保存状态</span>
                <Badge variant={workpaperSaveStatus === "saved" ? "ok" : workpaperSaveStatus === "error" ? "err" : "muted"}>
                  {workpaperSaveStatus === "saving" ? "保存中" : workpaperSaveStatus === "saved" ? "已保存" : workpaperSaveStatus === "error" ? "保存失败" : "未保存"}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">定稿状态</span>
                <Badge variant={finalizeStatus === "finalized" ? "ok" : finalizeStatus === "error" ? "err" : "muted"}>
                  {finalizeStatus === "finalizing" ? "定稿中" : finalizeStatus === "finalized" ? "已定稿" : finalizeStatus === "error" ? "定稿失败" : "未定稿"}
                </Badge>
              </div>
              {workpaperJson && (
                <div className="flex justify-between">
                  <span className="text-text-muted">发现数量</span>
                  <span>{workpaperJson.findings.length} 条</span>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>使用说明</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-text-muted leading-relaxed">
                工作底稿由 AI 自动生成，支持富文本编辑。编辑内容会自动保存。定稿后可导出为 Word 文档。
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 验证编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

- [ ] **Step 4: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/pages/WorkpaperPage.tsx frontend/src/components/WorkpaperEditor.tsx && git commit -m "feat(frontend): rewrite Workpaper page with editor and metadata side panel"
```

---

## Task 9: 文档对比页面

**Files:**
- Modify: `frontend/src/pages/DocComparePage.tsx`

基于 Pencil 设计稿 `Screen/DocCompare` + `Screen/DocCompare-Upload`。

该页面逻辑复杂，但核心渲染逻辑（CompareDocumentColumn + match highlight）保持不变，只替换 CSS 类名为 Tailwind utilities。

- [ ] **Step 1: 重写 DocComparePage**

该文件较大，重构重点：
1. 移除所有 CSS class 引用（`compare-*`, `metric-grid` 等）
2. 用 Tailwind utilities 替代
3. 保留所有现有函数逻辑和 CompareDocumentColumn / CompareFileDropzone 子组件
4. 使用新组件：Button, Card, MetricCard, EmptyState, Badge

```tsx
// frontend/src/pages/DocComparePage.tsx
import { ArrowDown, Download, FileText, GitCompareArrows, Upload } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent,
  type FormEvent,
} from "react";

import {
  buildCompareDownloadUrl,
  compareDocxFiles,
  type CompareCategoryId,
  type CompareDocument,
  type CompareMatch,
  type CompareResponse,
  type CompareSummary,
} from "@/api/compare";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MetricCard } from "@/components/MetricCard";
import { EmptyState } from "@/components/EmptyState";

const CATEGORY_PRIORITY: Record<CompareCategoryId, number> = { paragraph: 0, sentence: 1, segment: 2 };

function categoryCount(summary: CompareSummary, cat: CompareCategoryId): number {
  if (cat === "paragraph") return summary.commonParagraphCount;
  if (cat === "sentence") return summary.commonSentenceCount;
  return summary.commonSegmentCount;
}

export function DocComparePage() {
  const [firstFile, setFirstFile] = useState<File | null>(null);
  const [secondFile, setSecondFile] = useState<File | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [visibleCats, setVisibleCats] = useState<Record<CompareCategoryId, boolean>>({ paragraph: true, sentence: true, segment: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visibleMatches = useMemo(() => result?.matches.filter((m) => visibleCats[m.category]) ?? [], [result, visibleCats]);
  const visibleLookup = useMemo(() => Object.fromEntries(visibleMatches.map((m) => [m.id, m])), [visibleMatches]);

  useEffect(() => {
    if (selectedMatchId && !visibleLookup[selectedMatchId]) setSelectedMatchId(visibleMatches[0]?.id ?? null);
  }, [selectedMatchId, visibleLookup, visibleMatches]);

  async function handleCompare(e: FormEvent) {
    e.preventDefault();
    if (!firstFile || !secondFile) return;
    setLoading(true);
    setError(null);
    try {
      const r = await compareDocxFiles(firstFile, secondFile);
      setResult(r);
      setSelectedMatchId(r.matches[0]?.id ?? null);
    } catch (err) { setError(err instanceof Error ? err.message : "对比失败"); }
    finally { setLoading(false); }
  }

  // ── Upload state ──
  if (!result) {
    return (
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
          <span className="text-base font-semibold text-text-primary">文档对比</span>
        </header>
        <div className="space-y-6 p-7">
          <div>
            <h2 className="text-lg font-semibold">文档对比</h2>
            <p className="text-sm text-text-muted">上传两份 Word 文档，自动对比并标记相似内容</p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>上传文档</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCompare} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <CompareDropzone label="文档 A" file={firstFile} onFile={setFirstFile} />
                  <CompareDropzone label="文档 B" file={secondFile} onFile={setSecondFile} />
                </div>
                {error && <p className="text-sm text-status-err">{error}</p>}
                <div className="flex justify-end">
                  <Button type="submit" disabled={!firstFile || !secondFile || loading}>
                    <GitCompareArrows className="h-4 w-4" /> {loading ? "对比中..." : "开始对比"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <EmptyState
            icon={<GitCompareArrows className="h-7 w-7 text-accent" />}
            title="上传两份文档开始对比"
            description="上传两份 DOCX 文件后将在此显示对比结果"
          />
        </div>
      </div>
    );
  }

  // ── Results state ──
  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between border-b bg-surface-card px-7 py-3.5">
        <span className="text-base font-semibold text-text-primary">文档对比</span>
        <div className="flex items-center gap-2">
          <a href={buildCompareDownloadUrl(result.downloads.first)}>
            <Button variant="secondary" size="sm"><Download className="h-4 w-4" /> 下载文档 A</Button>
          </a>
          <a href={buildCompareDownloadUrl(result.downloads.second)}>
            <Button variant="secondary" size="sm"><Download className="h-4 w-4" /> 下载文档 B</Button>
          </a>
        </div>
      </header>
      <div className="flex-1 overflow-auto space-y-4 p-5">
        {/* Metrics */}
        <div className="grid grid-cols-4 gap-3">
          <MetricCard label="匹配总数" value={result.summary.matchCount} tone="blue" />
          <MetricCard label="相同段落" value={result.summary.commonParagraphCount} tone="amber" />
          <MetricCard label="相同句子" value={result.summary.commonSentenceCount} tone="green" />
          <MetricCard label="公共片段" value={result.summary.commonSegmentCount} tone="slate" />
        </div>

        {/* Category toggles */}
        <div className="flex items-center gap-2">
          {result.categories.map((cat) => (
            <button
              key={cat.id}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium border transition-colors",
                visibleCats[cat.id] ? "border-transparent text-white" : "border-gray-300 bg-white text-text-secondary",
              )}
              style={visibleCats[cat.id] ? { backgroundColor: cat.color } : undefined}
              onClick={() => setVisibleCats((c) => ({ ...c, [cat.id]: !c[cat.id] }))}
            >
              {cat.label} ({categoryCount(result.summary, cat.id)})
            </button>
          ))}
        </div>

        {/* Workspace: two doc columns + match panel */}
        <div className="grid grid-cols-[1fr_1fr_280px] gap-4">
          <DocColumn
            title={result.summary.firstFileName}
            doc={result.documents.first}
            lookup={visibleLookup}
            selectedId={selectedMatchId}
            onSelect={setSelectedMatchId}
          />
          <DocColumn
            title={result.summary.secondFileName}
            doc={result.documents.second}
            lookup={visibleLookup}
            selectedId={selectedMatchId}
            onSelect={setSelectedMatchId}
          />
          <Card>
            <CardHeader>
              <CardTitle>匹配清单</CardTitle>
              <p className="text-xs text-text-muted">{visibleMatches.length} 项</p>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[500px]">
                {visibleMatches.map((m) => (
                  <button
                    key={m.id}
                    className={cn(
                      "w-full text-left px-4 py-2.5 border-b hover:bg-surface transition-colors",
                      selectedMatchId === m.id && "bg-accent-light",
                    )}
                    onClick={() => setSelectedMatchId(m.id)}
                  >
                    <span className="text-xs font-medium" style={{ color: m.color }}>{m.label}</span>
                    <p className="text-sm text-text-primary line-clamp-2 mt-0.5">{m.text}</p>
                    <p className="text-xs text-text-muted mt-0.5">A 侧 {m.firstCount} 处 · B 侧 {m.secondCount} 处</p>
                  </button>
                ))}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──

function CompareDropzone({ label, file, onFile }: { label: string; file: File | null; onFile: (f: File | null) => void }) {
  const [dragging, setDragging] = useState(false);
  function handleDrop(e: DragEvent<HTMLLabelElement>) { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }
  return (
    <label
      className={cn("flex flex-col items-center gap-2 rounded-card border-2 border-dashed p-8 cursor-pointer transition-colors", dragging ? "border-accent bg-accent-light/50" : "hover:border-accent")}
      onDragEnter={(e) => { e.preventDefault(); setDragging(true); }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input className="sr-only" type="file" accept=".docx" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-light">
        {file ? <FileText className="h-5 w-5 text-accent" /> : <Upload className="h-5 w-5 text-accent" />}
      </div>
      <strong className="text-sm">{label}</strong>
      <span className="text-xs text-text-muted">{file ? file.name : "选择或拖入 DOCX"}</span>
    </label>
  );
}

function DocColumn({ title, doc, lookup, selectedId, onSelect }: {
  title: string; doc: CompareDocument; lookup: Record<string, CompareMatch>; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!selectedId || !ref.current) return;
    ref.current.querySelector(`[data-match-ids~="${selectedId}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selectedId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
        <p className="text-xs text-text-muted">{doc.blockCount} 段</p>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[500px] px-4">
          <div ref={ref}>
            {doc.blocks.map((block) => (
              <p key={block.id} className="flex gap-2 py-1 text-sm leading-relaxed">
                <span className="shrink-0 text-xs text-text-muted w-6 text-right">{String(block.index).padStart(2, "0")}</span>
                <span>
                  {block.segments.map((seg, i) => {
                    const visible = seg.matchIds.filter((id) => lookup[id]);
                    const primary = [...visible].sort((a, b) => CATEGORY_PRIORITY[lookup[a].category] - CATEGORY_PRIORITY[lookup[b].category])[0];
                    if (!primary) return <span key={`${block.id}-${i}`}>{seg.text}</span>;
                    const m = lookup[primary];
                    const isActive = selectedId != null && visible.includes(selectedId);
                    return (
                      <button
                        key={`${block.id}-${i}`}
                        className={cn("rounded px-0.5 transition-colors", isActive && "ring-2 ring-offset-1")}
                        style={{ backgroundColor: `${m.color}33`, "--tw-ring-color": m.color } as CSSProperties}
                        data-match-ids={visible.join(" ")}
                        onClick={() => onSelect(primary)}
                      >
                        {seg.text}
                      </button>
                    );
                  })}
                </span>
              </p>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: 验证编译**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

- [ ] **Step 3: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add frontend/src/pages/DocComparePage.tsx && git commit -m "feat(frontend): rewrite DocCompare page with upload and comparison states"
```

---

## Task 10: 清理旧文件 + 更新测试 + 最终验证

**Files:**
- Delete: `frontend/src/styles.css`
- Delete: `frontend/src/components/Ui.tsx`
- Delete: `frontend/src/components/AuditProgressPanel.tsx`
- Delete: `frontend/src/components/TenderUploadPanel.tsx`
- Delete: `frontend/src/components/CheckpointPicker.tsx`
- Delete: `frontend/src/pages/HomePage.tsx`
- Delete: `frontend/src/components/Modal.tsx`
- Modify: `frontend/src/main.tsx` — 移除 `import "./styles.css"`
- Modify: `frontend/tests/pages/AIReviewPage.test.tsx` — 更新 import

- [ ] **Step 1: 移除旧样式导入**

修改 `frontend/src/main.tsx`，删除 `import "./styles.css";` 行。

```tsx
// frontend/src/main.tsx
import "@fontsource-variable/inter";
import "@fontsource/geist-mono/400.css";
import "./globals.css";

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { WorkbenchProvider } from "./context/V3WorkbenchContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <WorkbenchProvider>
        <App />
      </WorkbenchProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 2: 删除旧文件**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && rm -f src/styles.css src/components/Ui.tsx src/components/AuditProgressPanel.tsx src/components/TenderUploadPanel.tsx src/components/CheckpointPicker.tsx src/components/Modal.tsx src/pages/HomePage.tsx
```

- [ ] **Step 3: 修复 import 错误**

检查所有文件是否仍然引用已删除的模块。运行 `tsc` 查看错误并逐一修复：

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit 2>&1 | head -50
```

可能需要修复的文件：
- `frontend/src/hooks/useProjectWorkflow.ts` — 如果引用了 TenderUploadPanel 的类型
- `frontend/src/hooks/useAuditRun.ts` — 如果引用了 CheckpointPicker 的类型
- `frontend/tests/pages/AIReviewPage.test.tsx` — 更新 mock imports

对于 `useProjectWorkflow.ts` 和 `useAuditRun.ts`：这两个 hooks 不依赖被删除的组件（它们只依赖 `V3WorkbenchContext`），应该无需修改。

对于测试文件，更新 import 以匹配新的页面组件结构。如果测试引用了旧的 `Ui.tsx` 或 `Modal.tsx` 导出，替换为新的 shadcn 组件路径。

- [ ] **Step 4: 更新测试文件**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npx tsc -b --noEmit
```

根据错误输出修复。典型修复：将 `from "../src/components/Ui"` 改为具体的 shadcn 组件导入。

- [ ] **Step 5: 运行全部前端测试**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npm run test
```

Expected: 测试通过（可能需要更新 mock 数据或 snapshot）。

- [ ] **Step 6: 完整构建验证**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor/frontend && npm run build
```

Expected: 构建成功。

- [ ] **Step 7: 提交**

```bash
cd /home/iomgaa/Projects/GovDoc_Editor && git add -A frontend/ && git commit -m "refactor(frontend): remove legacy CSS and old components, finalize Tailwind migration"
```

---

## 验收标准

| 项目 | 标准 |
|------|------|
| TypeScript 编译 | `npx tsc -b --noEmit` 零错误 |
| Vite 构建 | `npm run build` 成功 |
| 前端测试 | `npm run test` 全部通过 |
| 旧文件清理 | `styles.css`, `Ui.tsx`, `Modal.tsx`, `HomePage.tsx`, `AuditProgressPanel.tsx`, `TenderUploadPanel.tsx`, `CheckpointPicker.tsx` 已删除 |
| 设计稿覆盖 | 15 个 Pencil 设计屏幕全部有对应 React 组件 |
| 路由保持 | 6 条路由不变（`/`, `/audit-library`, `/ai-review`, `/workpaper`, `/audit-results`, `/compare`） |
| API 不变 | `api/v3.ts` 和 `V3WorkbenchContext.tsx` 不修改 |
| 侧边栏 | 深色 #0A0F1E 固定侧边栏，宽 240px |
| 字体 | Inter（正文）+ Geist Mono（代码/技术文本） |
| 面向律师 | 所有 UI 文案使用简体中文，无计算机术语 |
