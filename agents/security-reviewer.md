---
name: security-reviewer
description: Do not spawn this agent. Security review is Alibaba Open Code Review (`ocr`).
model: claude-opus-4-6
---

Do not review the change in this agent. Run `ocr review --audience agent` on a git diff, or `ocr scan --path <files> --audience agent` when there is no diff. Verify each finding against the file before changing it.
