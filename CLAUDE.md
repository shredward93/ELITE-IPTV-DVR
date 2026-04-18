# ELITE IPTV DVR — Claude Instructions

## Project
Two-part system: Python PC server brain + Android TV client.
See IMPLEMENTATION.md for full architecture.

## Models
- Default: Sonnet (coding, edits, API design)
- Use **Haiku** when: reading large files for context only, summarizing logs, scanning Android XML layouts, or any task that is read-heavy with no code output needed.

## Repo layout
```
core/          PC backend modules — edit here for server/API/DVR work
ui/            PC tkinter frontend — edit here for desktop UI work
android/       Android TV app (Kotlin) — not yet created
IMPLEMENTATION.md  Full feature plan — read this first on any new task
```

## Skill usage

| When | Use |
|------|-----|
| Designing a new module or major feature | `senior-architect` — run BEFORE writing code |
| Any Android TV / Kotlin / ExoPlayer question | `taches-cc-resources:research:technical` |
| Starting a new build phase | `taches-cc-resources:create-plans` |
| After implementing a feature | `simplify` — check for redundancy/quality |
| Debugging something that won't yield | `taches-cc-resources:debug-like-expert` |
| Need to know what to work on next | `taches-cc-resources:whats-next` |

## Rules
- Read IMPLEMENTATION.md before starting any new feature — it defines the API contract between PC and Android.
- PC modules live in `core/`. Never put business logic in `ui/`.
- Android TV is a thin client — no FFmpeg, no file management. All heavy work stays on PC.
- DVR buffer segments live in a separate folder from completed scheduled recordings.
- Both DVR caps (hours AND GB) must always be enforced together.
- HTTP range requests are required on all file-serving endpoints (`/dvr/stream/`, `/recordings/`).

## Communication Style
- **Maximum terseness:** 1–2 sentences per response. No preamble, no compliments, no small talk. Direct answer only.
- **No trailing summaries:** User reads diffs themselves.
- **Assume senior engineer:** Skip basic explanations.
