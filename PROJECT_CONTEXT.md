# Vibe-Guardian (VBG) Project Context

## 1. Project Overview
**Vibe-Guardian (VBG)** is an AI Cross-Check Automation Tool designed to orchestrate collaboration between multiple AI CLI agents (Claude Code, Gemini CLI, Antigravity).
- **Goal:** Automate code review, refactoring, and project scaffolding by leveraging the strengths of different AI models (e.g., Claude for generation/planning, Gemini for auditing/cross-checking).
- **Core Script:** `vbg.py` (Python 3.8+)
- **Configuration:** `vbg_config.json`

## 2. Architecture & Workflow
- **Controller:** `vbg.py` acts as the central controller, executing shell commands to invoke other CLI tools.
- **Workflow:**
  1.  **Analyze:** Detects project type (Next.js, Spring Boot, Python, etc.).
  2.  **Execute:** Runs `claude` or `gemini` CLIs based on the user's task.
  3.  **Cross-Check:** (Optional) Feeds the output of one AI (e.g., Claude) into another (e.g., Gemini) for verification.
  4.  **Report:** Generates metrics (execution time, memory usage) and saves logs to `.vbg_reports/`.

## 3. Key Files
- `vbg.py`: Main entry point. Contains logic for `AIEngine`, `Benchmarker`, and `VBGCore`.
- `vbg_config.json`: Configuration for model versions, timeouts, and enabled features.
- `INSTALL.md`: Installation instructions for Windows/Mac/Linux.
- `vbg_plan.md`: Generated implementation plans.

## 4. Development Guidelines
- **Language:** Python 3 (Type hinting required).
- **Style:** Follow PEP 8.
- **CLI Output:** Use `Spinner` class for long-running tasks. Use `Colors` class for terminal output.
- **Error Handling:** Graceful degradation (Fallback mode) if an AI CLI is missing or fails.

## 5. Current Configuration (Dynamic)
- **Primary AI:** Claude (Builder role)
- **Auditor AI:** Gemini (Auditor role)
- **Model Versions:**
  - Gemini: `gemini-3.0-pro` (Updated from 2.5)
  - Claude: `sonnet` (Default)
