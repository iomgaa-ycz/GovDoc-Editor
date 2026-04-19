# Fixtures

本目录对应 `docs/TD.md` T0.5。

默认路径就是仓库内 `tests/fixtures/`；如需外部数据集，可通过环境变量
`GOVDOC_FIXTURES=/abs/path/to/fixtures` 覆盖。

当前已约定：

- `guide_excerpt.md`：法规节选 markdown
- `checkpoints_golden.json`：管道 A 的金标准输出
- `tender_small.docx` / `tender_small.md`：最小招标文书样例
- `workpaper_expected.json`：管道 B 期望 workpaper
- `workpaper_template.docx`：仅供测试回放的简化 docxtpl 模板
- `mock_agent_trajectories/`：MockPES replay 数据，含 `phase_outcomes.json` 与 `working/`
