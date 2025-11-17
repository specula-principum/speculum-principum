Mission: Execute the Governance Extraction plan for prince01mach_1.pdf.

Workflow:
1. Open devops/projects/governance-extraction-plan.md and focus on exactly one section at a time (e.g., Workstream A task list). Do not move to the next section until the current one is fully completed, reviewed, and logged.
2. For each command in the active section, run it through main.py (python -m main …). Capture console output, confirm success criteria (exit code 0, expected files created, no unhandled errors), and rerun if needed.
3. After each command, inspect the produced knowledge-base artifacts (Markdown, JSON, YAML) for quality. Check for correctness, consistency, and unwanted noise. Note any issues found before moving on.
4. Where quality gaps or noise appear, iterate: adjust configs/prompts, rerun the relevant extractor(s), compare revisions, and keep iterating until quality is acceptable or you’ve documented the blockers explicitly.
5. Maintain a living progress log at devops/projects/kb-extraction-progress.md (create if missing). For every pass include: timestamp, section/task name, commands executed, verification notes, quality review findings, fixes applied, remaining issues, and next-step suggestions so future agents can resume seamlessly.
6. Only after a section is fully executed, verified, quality-checked, and logged should you proceed to the next section of the governance plan. Continue until all sections are complete or you hit a blocker that must be handed off.
7. When stopping (end-of-shift or completion), make sure the progress log reflects the current state, outstanding concerns, and explicit hand-off instructions.

Guardrails:
- Never change extractor interfaces or schemas.
- Use evidence/prince01mach_1.pdf and evidence/parsed/… outputs as the single source of truth.
- Store regenerated artifacts under the existing evidence/ and reports/ structure.
- If a task calls for review or QA sign-off, document the reviewer’s notes or state if pending.

Goal: Produce high-quality knowledge-base documents with minimal noise, documented verification, and a clear progress trail for the next agent.
