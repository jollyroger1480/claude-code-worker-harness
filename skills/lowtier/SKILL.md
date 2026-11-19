---
name: lowtier
description: >
  Odd chores that need no Claude sub-agent: a short blurb, a rename list, a
  one-file summary, a format conversion, a first-draft regex, an image prompt.
  Do it inline, or hand it to the optional cheap lane (bin/grok-leaf, the Grok
  CLI by default) and check the answer before using it. Never send secrets,
  customer data, private files, or anything that changes a live system.
---

# Lowtier: the cheap lane

<purpose>
Some jobs are too small for a Claude sub-agent and too dull for the main context.
The router denies `subagent_type: lowtier` on purpose and points here. This skill
decides between "just do it inline" and "send it to a cheaper model", and it keeps
the cheaper model on a short leash.
</purpose>

## When to use the cheap lane

Send a job to `grok-leaf` only when ALL of these hold:
- It is self-contained: the whole job fits in one prompt, with no repo access needed.
- The answer is easy to check: you can read it, run it, or diff it in under a minute.
- Nothing in the prompt is private: no keys, tokens, passwords, `.env` content,
  customer or buyer data, personal details, or files the user has not said are public.
- Getting it wrong costs nothing: no live system, money, sends, deploys or deletes.

Good fits: rewrite a paragraph in plain English, draft 10 test inputs, turn a table
into CSV, suggest names, draft an image prompt, summarize a public page you already
fetched, write a first-pass regex you will test yourself.

Keep on Claude: multi-file code changes, anything touching a live service, anything
the user will act on without reading, security or legal judgment, and hard reasoning.

## How

```bash
grok-leaf "Rewrite this in plain English, under 60 words: <text>"
grok-leaf --prompt-file /path/to/prompt.txt
some_command | grok-leaf
```

`grok-leaf` exits 3 when the grok CLI is not installed. Then do the job inline; do
not try to install anything. It also refuses prompts that look like they carry a
key (exit 4), refuses `--always-approve` (exit 2), runs Grok in an empty scratch
folder, closes stdin, times out (default 300 s) and caps concurrent calls (default 2).

## Verify before use

Treat the answer as a draft from a stranger:
- Code or regex: run it on real input, including an edge case.
- Facts: check them against the source you already have. A cheap model's claim is a
  candidate, not evidence.
- Text: read it once; fix tone and anything it invented.

Say in your report that the cheap lane produced it and how you checked it.

## Image work

For images and video, use a dedicated CLI rather than a chat prompt. The companion
project [grok-imagine-cli](https://github.com/jollyroger1480/grok-imagine-cli) does
Grok Imagine stills and video from the terminal. Image generation usually costs money
per call, so ask before a batch.

## NEVER
- Send secrets, private data or unpublished files to the cheap lane.
- Pass `--always-approve` or any auto-approve mode to the leaf.
- Use a leaf answer without checking it.
- Run more than a couple of leaf calls at once; the wrapper's slot cap is there for a reason.

## ALWAYS
- Prefer inline when the job takes you less time than writing the prompt.
- Fall back to inline when `grok-leaf` exits 3, 4 or 5.
