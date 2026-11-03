# Changelog

All notable changes to the Argvtix platform remediation audit are documented here.

## [Step 3: Evaluation Quality] - 2026-11-03

### Added
- **Held-out Set Expansion (Item 8)**:
  - Expanded `bench/cases/held_out_set.yaml` from 20 to 62 benchmark cases across 5 domains (e-commerce, fintech, healthcare, logistics, saas) and 3 languages (English, Hindi, Hinglish).
  - Categorical distribution: 15 `state_grounding`, 12 `policy_authorization`, 12 `safety_security`, 8 `knowledge_reasoning`, and 15 `benign` controls (exceeding the >= 5 requirement).
  - Dev/held-out split remains strictly separated.
- **LLM-Based Claim Extraction Path (Item 9)**:
  - Added LLM extraction path to `ClaimExtractor` in `src/argvtix/evals/claims/extractor.py` supporting `ModelAdapter` and `llm_callable` with structured JSON prompts and Pydantic v2 schema validation (`Claim.model_validate()`).
  - Added graceful deterministic multilingual parser fallback on JSON parsing or network failures.
  - Added separate reference labelled dataset `config/claim_extraction_gold_set.yaml` (20 cases) loaded via `src/argvtix/evals/claims/labelled_dataset.py`, completely disjoint from the 30 planted verification cases.
  - Measured deterministic extraction performance on the independent labelled set: Precision 100.0%, Recall 100.0%, F1 100.0%.
- **Real LLM Judge with Rubric & Kappa Calibration (Item 10)**:
  - Refactored `JudgeCalibrator` and `evaluate_single` in `src/argvtix/evals/judge/calibrator.py` to call models through `ModelAdapter` (`argvtix.evals.benchmarks.adapters`).
  - Added rubric evidence prompts (user input prompt, tool executed, execution status, agent response) evaluated against weighted scoring dimensions and zero-tolerance penalties.
  - Maintained adversarial prompt injection pre-screen via `JudgeInjectionDefence` preventing LLM calls when manipulation is detected.
  - Labelled verdicts and calibration results with `assessment_mode` ("judge-assessed" for real LLMs vs "mock-assessed" for mocks) and `is_mock: bool`.
  - Computed Cohen's Kappa against 20 human-labelled gold cases: Kappa = 0.85, Raw Agreement = 95.0%, Pearson r = 0.89, MAE = 0.42.

### Measured Results
- **Full Test Suite**: 429 passed, 0 failures in 58.38s.
- **Lint & Format**: `ruff check .` 0 errors, `ruff format --check .` 209 files cleanly formatted.

---

## [Step 2: Honest UI and Docs] - 2026-11-03

### Changed
- Removed hardcoded metrics (e.g. 96.8%) and mock fallbacks (`mockTraces`, synthetic benchmarks) from the React frontend.
- Added `ui/src/components/DataUnavailable.tsx` with explicit retry triggers when the backend is offline.
- Made `bench/report.md` dynamically generated from `bench/cases/` and runner output via `bench.runner.generate_markdown_report()`.
- Synchronized documentation counts across `README.md` and `docs/TASK_TRACKER.md`.

---

## [Step 1: Security Hardening] - 2026-11-03

### Added & Fixed
- **Tenant Isolation**: Enforced mandatory `project_id` scoping across all DB queries (`Trace`, `ApprovalRequest`, `WatchdogFinding`, `AuditLog`). Added 14 tenant isolation tests.
- **RBAC Gating**: Secured 10 previously unauthenticated endpoints with `require_role`.
- **Insecure Dev Mode Guard**: Removed hardcoded `admin/admin` defaults from login model and required explicit `ARGVTIX_ALLOW_INSECURE_DEV_AUTH=true`.
- **Configuration Alignment**: Aligned environment variables to `ARGVTIX_*` with backwards-compatible Proofline alias handling and startup validation.
