---
name: render-wiki-page
description: "将 research-wiki 中的 Markdown 实体渲染为 React + shadcn/ui 的 .tsx 页面组件。触发短语: render wiki, 渲染 wiki, render page。"
argument-hint: "[entity .md 文件路径，或 'all' 渲染全部队列]"
---

# Render Wiki Page

将 Wiki Markdown 实体渲染为 React + shadcn/ui 的 .tsx 页面组件，写入 `tools/wiki-site/app/src/pages/` 目录。

## 触发方式

1. **手动**：`/render-wiki-page <path>` 或 `/render-wiki-page all`
2. **自动**：其他 skill（brainstorming、writing-plans 等）修改 wiki 后，由 hook 自动触发

## 执行流程

### Step 1: 确定要渲染的文件

- 如果传入了具体 .md 文件路径 → 渲染该文件
- 如果传入 `all` → 读取 `.wiki-site/render-queue.json`，渲染队列中的所有文件
- 如果队列为空或不存在 → 扫描 `research-wiki/` 下所有 .md 实体文件

跳过以下文件：`index.md`、`log.md`、`query_pack.md`、`gap_map.md`

### Step 2: 对每个 .md 文件渲染

对每个待渲染的 .md 文件：

1. **读取内容**：读取 .md 文件的 YAML frontmatter 和 markdown body
2. **读取 prompts**：
   - 系统 prompt：`tools/wiki-site/prompts/system.md`
   - 类型 prompt：`tools/wiki-site/prompts/types/<entity_type>.md`
3. **读取关系**：从 `research-wiki/graph/edges.json` 提取该实体的相关边
4. **读取上一版**：如果 `tools/wiki-site/app/src/pages/<entity_type_plural>/<stem>.tsx` 已存在，读取作为参考
   - 路径映射：entity type → 复数目录名（paper→papers, plan→plans, design→designs, idea→ideas, finding→findings, review→reviews, claim→claims, gap→gaps, experiment→experiments, schema→schemas, metric→metrics）
   - 这与 wiki 目录结构和 manifest.json 的 page_path 一致
5. **生成 .tsx**：

   按以下格式组装 prompt，然后直接生成 .tsx 文件内容：

   **System**：系统 prompt + 类型 prompt 的内容

   **User**：
   ```
   ## 实体元数据
   <frontmatter as JSON>

   ## 正文内容
   <markdown body>

   ## 关系边
   <related edges as JSON>

   ## 上一版组件（如有，请基于此更新，保持布局稳定）
   <previous tsx content>
   ```

6. **写入 .tsx**：将生成的 TSX 代码写入 `tools/wiki-site/app/src/pages/<entity_type_plural>/<stem>.tsx`
   - **关键**：使用复数目录名（papers/, plans/, designs/ 等），与 manifest.json 的 page_path 和 wiki 目录结构一致
   - 如果输出包含 \`\`\`tsx 代码块标记，提取代码块内容
   - 确保目录存在

### Step 3: 清空已处理的队列

渲染完成后，将已处理的文件从 `.wiki-site/render-queue.json` 中移除。

### Step 4: 通知用户

报告渲染结果：成功几个、失败几个、可以在 `http://localhost:8687` 查看。

## 重要约束

- 生成的 .tsx 文件必须 `export default function Page()`
- 只能 import `react` 和 `@/components/ui/*` 中的 shadcn/ui 组件
- SVG 图表内联 JSX，不使用外部图表库
- 中文界面
- 每个文件独立渲染，使用 Agent 工具并行渲染多个文件（最多 3 个并行）

## Tailwind CSS 扫描（关键）

生成的 .tsx 页面位于 `src/pages/` 目录，通过 `import.meta.glob` 动态加载。Tailwind v4 默认不扫描动态加载的文件。

`src/index.css` 中已配置 `@source "../src/pages/**/*.tsx"` 指令确保 Tailwind 扫描 pages 目录。**如果此指令丢失，所有 Tailwind class 在实体页面中将不生效**（表现为 grid 不分列、间距不生效等）。

检查方法：如果实体页面的 `grid-cols-4` 渲染为单列，首先检查 index.css 中是否存在 `@source` 指令。
