---
name: audit-loose-ends
description: >-
  Run a comprehensive codebase audit to identify where the project is, partially implemented features, unfinished flows, undocumented systems, and high-value loose ends before a playtest. Use this when the user wants to know what to do next or wants to close all loose ends.
---

# Audit Loose Ends

This skill instructs the agent to perform a deep inspection of the codebase and project documentation to create an actionable plan for closing all loose ends before a playtest.

See also: a broader, tool-agnostic "project x-ray" (architecture drift,
roadmap vs. stated goal, ranked next actions) exists as a separate skill some
sessions use — this one is narrower and playtest-focused, not a replacement
for it.

## Objective

- Identify the current state of the project and the best immediate next steps.
- Find partially implemented features and incomplete flows.
- Discover systems that are documented (e.g., in `RULES.md` or `REFERENCE.md`) but not yet implemented.
- Identify high-value features or technical debt left for "later" that should be resolved now.
- Produce a clear, prioritized checklist/action plan.

## Steps to Execute

1. **Scan for Code Markers:**
   - Use `grep_search` to find `TODO`, `FIXME`, `XXX`, `pass`, and other placeholder comments across the codebase (e.g., `src/`, `tests/`).
   - Identify stubs or functions that return hardcoded values instead of proper logic.

2. **Cross-Reference Documentation:**
   - Read `RULES.md` and `REFERENCE.md`.
   - Compare the described systems and rules with the actual implementation in core modules (`unit.py`, `battle.py`, `campaign.py`, etc.).
   - Note any documented system that is completely missing or only partially implemented.

3. **Analyze Architecture & State:**
   - Review how modules connect. Are there loose ends in the `pygame` app shell (`app.py`), the UI screens, or the turn flow?
   - Identify features that feel "half-done" (e.g., a status effect that is defined but never applied, or an AI heuristic that is a placeholder).

4. **Generate the Audit Report & Plan:**
   - Create an artifact named `loose_ends_audit.md` (or update an implementation plan).
   - **Structure the report with:**
     - **Current State:** A brief summary of where the project stands.
     - **Incomplete Flows:** List of partially implemented features.
     - **Missing Systems:** Features documented but not coded.
     - **High-Value Targets:** Things left for "later" that are critical for a playtest.
   - **Action Plan:** Conclude with a concrete, prioritized checklist (TODO list) for the user's next development session.

5. **Present to the User:**
   - Ask the user to review the audit report and decide which items to prioritize first.
