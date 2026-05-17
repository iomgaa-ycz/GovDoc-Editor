# Graph Report - .  (2026-04-18)

## Corpus Check
- 103 files · ~50,894 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 523 nodes · 792 edges · 32 communities detected
- Extraction: 72% EXTRACTED · 28% INFERRED · 0% AMBIGUOUS · INFERRED: 221 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `request()` - 22 edges
2. `AuditRun` - 16 edges
3. `GovDocModel` - 16 edges
4. `AuditPointRun` - 15 edges
5. `V3 Drift Review 2026-04-19` - 15 edges
6. `TenderDoc` - 14 edges
7. `WorkpaperDraft` - 14 edges
8. `DocumentStore` - 14 edges
9. `GovDoc app.sqlite SQLModel tables (Project/TenderDoc/ExtractRun/AuditRun)` - 13 edges
10. `CheckpointFinal` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Converted: tender_small_11349032.md` --semantically_similar_to--> `Fixture: tender_small.md`  [INFERRED] [semantically similar]
  graphify-out/converted/tender_small_11349032.md → tests/fixtures/tender_small.md
- `Three-Layer Architecture (GovDoc/Scrivai/qmd)` --conceptually_related_to--> `GOVDOC_OVERVIEW (human-readable speed-read)`  [INFERRED]
  README.md → 工程md/GOVDOC_OVERVIEW(1).md
- `workpaper docxtpl template (converted markdown)` --shares_data_with--> `GovCheckpoint/LegalBasis/GovFinding/Workpaper schemas`  [EXTRACTED]
  graphify-out/converted/workpaper_9e5a65c2.md → 工程md/GovDoc-Auditor/design(1).md
- `Design baseline restriction (no import qmd / claude_agent_sdk)` --conceptually_related_to--> `Implementation constraints (no V2, no qmd import)`  [INFERRED]
  README.md → AGENTS.md
- `Skill: gov-extract-checkpoint` --references--> `GovCheckpoint/LegalBasis/GovFinding/Workpaper schemas`  [EXTRACTED]
  skills/gov-extract-checkpoint/SKILL.md → 工程md/GovDoc-Auditor/design(1).md

## Hyperedges (group relationships)
- **Three-layer dependency chain (GovDoc→Scrivai→qmd)** — overview_govdoc_position, overview_scrivai_position, overview_qmd_position [EXTRACTED 1.00]
- **PES three phases (PLAN/EXECUTE/SUMMARIZE files contract)** — scrivai_base_pes, scrivai_phase_contract_files, scrivai_allowed_tools_matrix, scrivai_hook_strategy [EXTRACTED 0.95]
- **5 Evaluator classes + CompositeEvaluator (anti-overfitting)** — govdoc_5_evaluators, scrivai_evolution_runner, concept_evoskill_external, issue_003_evolutionconfig_align [EXTRACTED 0.90]
- **V3 P0 Drift Cluster** — drift_p0_audit_point_run_missing, drift_p0_runtime_compat_missing, drift_p0_prompt_duplication, drift_p0_api_501, drift_p0_finalize_missing [EXTRACTED 0.95]
- **V2 lessons -> V3 design fix chain** — v2_pit_audit_one_json, v2_solution_audit_point_run, td_t0_12_pipeline_b_skel, drift_p0_audit_point_run_missing [INFERRED 0.85]
- **Government audit skill trio** — skill_audit_tender, skill_locate_evidence, skill_cite_legal_basis [EXTRACTED 0.90]

## Communities

### Community 0 - "React Frontend Pages"
Cohesion: 0.05
Nodes (9): checkpointToDisplay(), escapeHtml(), parseCheckpointPayload(), workpaperToHtml(), build_parser(), _emit_stderr(), _emit_stdout(), main() (+1 more)

### Community 1 - "V3 Design Docs & Constraints"
Cohesion: 0.04
Nodes (56): Constraint: do not fabricate official workpaper template, Constraint: must not regress to V2 object model, Constraint: runtime.py is sole compat layer for Scrivai gaps, Claude V3 Alignment Prompt, Data Flow Doc, Known issue: PDF/DOCX conversion fallback may garble, Known issue: workpaper edit only persists summary, Pipeline A data flow: rule upload to checkpoints (+48 more)

### Community 2 - "Pipeline B Audit Orchestrator"
Cohesion: 0.1
Nodes (46): Audit routes — 管道 B 触发 + 状态 + 重试。, count_processed_points(), _delete_trajectory_run(), _ensure_tender_collection(), generate_summary(), _match_finding_by_checkpoint_id(), prepare_point_run_retry(), 管道 B：审核点 + 招标文书 -> 工作底稿（逐点编排）。  设计基线：docs/design.md §10。 每个 AuditPointRun 对应一个独立 (+38 more)

### Community 3 - "Checkpoint Schemas & API"
Cohesion: 0.09
Nodes (34): CheckpointCategory, GovCheckpoint, GovFinding, GovFindingVerdict, LegalBasis, list_checkpoints(), _serialize_draft(), _serialize_final() (+26 more)

### Community 4 - "Cross-Project Integration Issues"
Cohesion: 0.05
Nodes (43): EvoSkill (external package), 5 Evaluator classes (IoU/LegalCitation/Severity/Verdict/EvidenceRecall) + CompositeEvaluator, CaseLibrary feedback loop (finalized workpaper → CaseLibrary.add), EvoSkill .claude/skills symlink workaround (project root), scrivai.build_qmd_client_from_config (replaces qmd.connect), Workpaper docxtpl template must be hand-crafted constraint, INTEGRATION_ISSUES.md (cross-project coordination board), ISSUE-001 EvoSkill hardcoded .claude/skills/ path (+35 more)

### Community 5 - "Pipeline A Extract & Skills"
Cohesion: 0.07
Nodes (15): Frontend README (Swagger UI as MVP frontend), GovDoc-Auditor design.md, Pipeline A (extract checkpoints from legal guide), Pipeline B (audit tender → workpaper), GovCheckpoint/LegalBasis/GovFinding/Workpaper schemas, GovDoc-Auditor TD.md, GovDoc prompts README, AuditorPES (+7 more)

### Community 6 - "PES Override Layer"
Cohesion: 0.09
Nodes (22): AuditorPES, ExtractorPES, GovDocAuditorPES, GovDocExtractorPES, _load_previous_phase_output(), GovDoc PES override 层——解决 prompt duplication + 接 validator / recovery hook。  设计基, 按 GovDoc 的 GovFinding 结构校验 summarize 输出。, 尝试从指定路径加载合法的 output JSON。 (+14 more)

### Community 7 - "API Routes & Migrations"
Cohesion: 0.08
Nodes (6): Alembic migrations README, GovDoc app.sqlite SQLModel tables (Project/TenderDoc/ExtractRun/AuditRun), GovDoc API route modules., test_pipeline_b_with_mock_pes_replay(), test_retry_point_run_reuses_same_run_id_after_cleanup(), _write_test_config()

### Community 8 - "Frontend API Client"
Cohesion: 0.16
Nodes (23): createAuditRun(), createProject(), deleteCheckpoint(), finalizeWorkpaper(), getAuditRunProgress(), getExtractRunStatus(), getProject(), getWorkpaperDraft() (+15 more)

### Community 9 - "Document Storage & Conversion"
Cohesion: 0.12
Nodes (11): DocumentStore, ensure_project_dir(), ensure_rule_source_dir(), ensure_workpaper_dir(), get_storage_root(), GovDoc 文件存储与 DocumentStore。, 列出所有已转换的 prepared 文件及其 manifest 信息。, 最简 fallback：把文件当二进制读，提取可读文本。 (+3 more)

### Community 10 - "Application Configuration"
Cohesion: 0.16
Nodes (16): BaseModel, BaseSettings, app_db_path(), AppConfig, EvolutionConfig, _expand_env(), GovDocConfig, GovDocEnvOverrides (+8 more)

### Community 11 - "Output Utils & JSON Repair"
Cohesion: 0.16
Nodes (15): _escape_intra_string_quotes(), _looks_like_string_terminator(), normalize_output(), _normalize_structural_punctuation(), 输出工具：relaxed JSON 修复 + 输出 normalize + 业务级校验。  设计基线：docs/v2-lessons-design-amendm, 宽松 JSON 加载：修复常见 LLM 输出问题。, 判断当前位置的双引号更像是 JSON 字符串结束符，而非正文内引号。, 输出 normalize：统一字段名和结构。 (+7 more)

### Community 12 - "Runtime Compat Layer"
Cohesion: 0.28
Nodes (15): build_gov_auditor_pes(), build_gov_extractor_pes(), _build_hooks(), collect_diagnostics(), get_config(), get_document_store(), get_gov_auditor_config(), get_gov_extractor_config() (+7 more)

### Community 13 - "GovDoc Architecture Overview"
Cohesion: 0.18
Nodes (14): Implementation constraints (no V2, no qmd import), AGENTS.md (Claude Code Agent specification), GOVDOC_OVERVIEW (human-readable speed-read), GovDoc-Auditor position (top layer, business web app), Milestone M0 (contract freeze + Mock), Milestone M1 (real integration), Milestone M2 (evolution + scale), Milestone M3 (release + deploy) (+6 more)

### Community 14 - "PES SDK Decisions"
Cohesion: 0.17
Nodes (12): claude-agent-sdk (external dep), Herald2 precedent project (CLI+Bash validation), PES three-phase (PLAN/EXECUTE/SUMMARIZE), Rationale: CLI+Bash chosen over MCP (Herald2 precedent), Rationale: PES uses files not text-chain (resumable, structured validation), Rationale: summarize tools tightened (avoid divergence), PES (Plan-Execute-Summarize), allowed_tools matrix (plan/execute/summarize) (+4 more)

### Community 15 - "Mock Audit Trajectories"
Cohesion: 0.27
Nodes (12): Checkpoint: cp_local_service_bonus (local service bias), Checkpoint: cp_vendor_scope (geographic eligibility restriction), Mock trajectory: audit_case_01 plan, Mock trajectory: extract_case_01 plan, Concept: biased scoring favoring local vendors, Concept: unfair vendor restriction by locality, Fixture: guide_excerpt.md (regulation snippet), Tests Fixtures README (+4 more)

### Community 16 - "Audit Skill Principles"
Cohesion: 0.2
Nodes (11): Schema: GovFinding, Principle: insufficient evidence -> doubt, not guess, Principle: evidence first, then verdict, Skill: gov-audit-tender, Skill: gov-cite-legal-basis, Rule: prefer original law text, no paraphrase, Rule: law_name/article/quote all required, Skill: gov-locate-evidence (+3 more)

### Community 17 - "Testing Support Helpers"
Cohesion: 0.33
Nodes (3): load_mock_replay(), MockReplayBundle, 测试 fixture 与 MockPES replay 辅助。

### Community 18 - "Database Session"
Cohesion: 0.6
Nodes (4): get_engine(), get_session(), init_db(), GovDoc 数据库引擎与 Session 依赖。

### Community 19 - "Alembic Migration Env"
Cohesion: 0.5
Nodes (1): Alembic env for GovDoc.

### Community 20 - "Initial DB Migration"
Cohesion: 0.5
Nodes (1): Initial GovDoc schema.  Revision ID: 0001_initial Revises: Create Date: 2026-04-

### Community 21 - "PES Overrides Tests"
Cohesion: 0.67
Nodes (0): 

### Community 22 - "Output Utils Tests"
Cohesion: 0.67
Nodes (0): 

### Community 23 - "Tender Doc Tests"
Cohesion: 0.67
Nodes (0): 

### Community 24 - "Agent Configs Test"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "Config Loading Test"
Cohesion: 1.0
Nodes (0): 

### Community 26 - "Vite Config"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Vite Env Types"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Skill Concept (orphan)"
Cohesion: 1.0
Nodes (1): Skill (Claude Code capability unit)

### Community 29 - "Docs README (orphan)"
Cohesion: 1.0
Nodes (1): Docs README

### Community 30 - "Integration Test README"
Cohesion: 1.0
Nodes (1): Tests Integration README

### Community 31 - "Contract Test README"
Cohesion: 1.0
Nodes (1): Tests Contract README

## Knowledge Gaps
- **117 isolated node(s):** `测试 fixture 与 MockPES replay 辅助。`, `GovDoc 配置加载。  设计基线：`docs/design.md` §13-14。`, `只负责读取少量环境覆盖项，保持 YAML 为单一配置文件。`, `GovDoc API route modules.`, `GovDoc SQLModel 数据模型。  设计基线：`docs/design.md` §5。` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Agent Configs Test`** (2 nodes): `test_agent_configs.py`, `test_agent_configs_load_with_current_pes_schema()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Config Loading Test`** (2 nodes): `test_config.py`, `test_load_config_expands_environment_variables()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Config`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Env Types`** (1 nodes): `vite-env.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Skill Concept (orphan)`** (1 nodes): `Skill (Claude Code capability unit)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Docs README (orphan)`** (1 nodes): `Docs README`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Integration Test README`** (1 nodes): `Tests Integration README`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Contract Test README`** (1 nodes): `Tests Contract README`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GovDocModel` connect `Checkpoint Schemas & API` to `Application Configuration`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Why does `GovDoc 运行时装配。  设计基线：`docs/design.md` §13。` connect `Runtime Compat Layer` to `Document Storage & Conversion`, `Application Configuration`, `PES Override Layer`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `GovDocConfig` connect `Application Configuration` to `Runtime Compat Layer`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `request()` (e.g. with `resolveBaseUrl()` and `healthCheck()`) actually correct?**
  _`request()` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `AuditRun` (e.g. with `Audit routes — 管道 B 触发 + 状态 + 重试。` and `Workpaper routes — 草稿/定稿/docx 下载。`) actually correct?**
  _`AuditRun` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `GovDocModel` (e.g. with `CheckpointListOutput` and `WorkpaperAuditOutput`) actually correct?**
  _`GovDocModel` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `测试 fixture 与 MockPES replay 辅助。`, `GovDoc 配置加载。  设计基线：`docs/design.md` §13-14。`, `只负责读取少量环境覆盖项，保持 YAML 为单一配置文件。` to the rest of the system?**
  _117 weakly-connected nodes found - possible documentation gaps or missing edges._