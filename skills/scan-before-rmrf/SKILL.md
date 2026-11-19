---
name: scan-before-rmrf
description: |
  Before running rm -rf (or equivalent bulk delete) on any directory,
  list its actual current contents and check whether anything generated,
  downloaded, or relied-upon during THIS session lives inside it
  un-copied elsewhere. Never trust your memory of "what's in there" —
  re-list it right before the delete.
allowed-tools: |
  Bash: ls, find
---

# Scan Before rm -rf

<purpose>
A directory that was "the old broken tool" at the start of a session can
silently become "the folder I've been saving fresh output/models into" by
the end of it. Deletion decisions get made based on what the directory WAS
(a thing to replace), not what it currently CONTAINS (which may now include
work done this session). The fix is cheap: re-list the directory's actual
contents immediately before deleting, not from memory of what it used to
hold.
</purpose>

## When To Activate

- About to run `rm -rf`, `shutil.rmtree`, or any recursive delete on a
  directory (tool install, project folder, "old" anything) that existed
  before this session started.
- Especially when that directory was ever used mid-session as an output
  path (`-o`, `--output`, redirected logs, saved files) or a source of
  files another tool now reads from (models, configs, generated assets).
- Any time a user says "delete X now that Y works" — Y's own outputs may
  be sitting inside X.

## Instructions

1. Immediately before the delete, run `find <dir> -newer <session-start-marker>`
   or just `ls -laR <dir>` (or a scoped `du -sh <dir>/*` for large trees) —
   do NOT rely on "I remember what's in there."
2. For every subpath that looks like output, input, or model data, ask:
   is this copied/backed up somewhere OUTSIDE the directory being deleted?
   If unsure, assume no.
3. If anything found is not safely duplicated elsewhere, copy or move it
   out first — even if that means creating a throwaway holding directory.
4. Only after that check comes back clean (or after confirmed copy-out)
   proceed with the delete.
5. This check is cheap (one `ls`/`find`) — never skip it to save a step,
   especially right after you personally wrote files into that directory
   earlier in the same session.

## NEVER

- Delete a directory based on what it was described as at the start of
  the session ("the broken ComfyUI install") without re-checking what it
  currently holds.
- Reuse a soon-to-be-replaced tool's own folder structure (its `output/`,
  `input/`, `models/`) as the save location for a NEW tool's generated
  files or downloaded assets, even temporarily — pick an independent path
  from the start.
- Treat "the replacement tool works" as proof the old directory is safe
  to delete — the replacement working and the old directory being empty
  of un-backed-up content are two separate facts.

## ALWAYS

- Pick output/model paths for a new tool OUTSIDE any directory that is a
  candidate for later deletion, from the very first run — not just before
  the delete.
- Re-list a directory's real contents right before deleting it, every time,
  no matter how confident you are about what's in there.

## The Failure That Spawned This Skill

Built a replacement for a crashing ComfyUI install
(stable-diffusion.cpp), and out of convenience pointed its `--diffusion-model`,
`--vae`, `--t5xxl` flags and `-o` output path directly at files inside
the old ComfyUI folder (its `models/` and `output/` folders already had the
right structure). Generated 3 real video clips, verified them, reported
success. Then the user said "yes delete" ComfyUI — and `rm -rf` on that
directory silently destroyed the 3 just-generated clips, the ~18GB of Wan2.2
model weights, and the 3 source stills, none of which had ever been copied
outside it. The tool wrapper being replaced does not mean its data directory
is a safe delete target — its contents had changed since the session started.
