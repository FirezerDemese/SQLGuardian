# SQLGuardian Demo Video — Recording Runbook

Target: 90-120 seconds, recruiter/hiring-manager audience. Hook fast, prove the AI feature is real (not a mockup), close with stack + name.

## Tooling

- **Recorder: Loom** (free tier). Gives a hosted link recruiters click and watch in-browser — no download, no "video won't play" friction. Enable auto-captions (many recruiters watch muted in open offices).
- Skip OBS/editing software unless you already know it well — editing time isn't worth it for a 2-minute clip.
- 1080p, cursor click-highlight on, webcam bubble optional (a 2-second face intro adds trust, then cut it for the rest).

## Pre-recording setup (do this BEFORE hitting record — don't record dead time)

1. **Verify `GROQ_API_KEY` in `.env` is a live key.** The AI panel is the whole differentiator of this video — if the key is missing/invalid, `/ai/explain` returns `"AI analysis unavailable"` and kills the best 30 seconds. Test it once via the Swagger docs (`/docs`) before recording.
2. Rebuild + start clean: `docker compose up -d --build` (or `./dev_start.sh` for a full reset including reseed).
3. Fleet Overview now has 4 instances (`primary`, `prod-sql01`, `reporting-sql01`, `Prod-sql02`) registered against the same dev SQL Server — all 4 cards will show **identical** CPU/memory/severity numbers since they're really one server. That's fine for a fast establishing pan (see shot list below) but do NOT let the camera linger on the grid — a paused frame with 4 matching cards reads as fake to a technical viewer.
4. Have three terminal tabs ready against the seeded `WideWorldImporters` DB (from `scripts/seed_dev.sql`, already run by `dev_start.sh`):
   - Tab 1: `scripts/simulate_blocking.sql` (holds locks ~10 min per the current `WAITFOR DELAY '00:10:30'`)
   - Tab 2: `scripts/simulate_workload.sql` (hits the same rows → produces actual `blocked_sessions`)
   - Tab 3: `scripts/simulate_longquery.sql` (optional, only if you show the long-running-queries view)
5. **Start Tab 1 and Tab 2 about 30-45 seconds before you hit record.** You want the dashboard already showing a red/critical blocking state the instant recording starts — no dead air waiting for locks to appear on camera.
6. Browser: clean profile/incognito (no bookmarks bar, no extension icons), zoom ~110% so text reads clearly, notifications off, dashboard tab pre-loaded and on the Fleet Overview page when you hit record.

## Shot list (~110s)

**0:00-0:06 — Hook (on Fleet Overview or straight into the blocked instance)**
> "This is a live blocking chain — the kind that pages a DBA at 3 AM. SQLGuardian already caught it, and it's about to tell me exactly why."

**0:06-0:12 — Fleet Overview (fast pan, keep the cursor moving, don't stop on the grid)**
Sweep across the 4 instance cards in one continuous motion, then click into an instance before the shot holds still.
> "SQLGuardian watches a whole fleet of SQL Server instances from one place — CPU, memory, blocking, disk, backups, failed jobs — all pulled straight from the DMVs, no agent bolted on top."

**0:12-0:35 — Instance Overview tab**
Click into the blocked instance, show live CPU/memory.
> "Drill into one instance and health refreshes every 30 seconds straight off `sys.dm_os` and `sys.dm_exec` views."

**0:35-0:55 — Blocking tab**
Show `blocked_sessions` / `head_blockers` table, live and red.
> "Here's the blocking chain — head blocker, wait time, exact session IDs. No guessing at what's stuck."

**0:55-1:25 — AI Brain tab (the differentiator, spend the most time here)**
Click **Explain**, let the real headline/DBA-summary/manager-summary render on camera.
> "This is the part that makes it different — it doesn't just show data, it explains it. One click and an LLM reads the live snapshot and gives me the plain-English version, and a separate one-liner for a non-technical manager."

Then click **Suggest** and scroll to show the ordered remediation list (diagnose → identify owner → non-destructive fix → kill as last resort).
> "And it doesn't just say 'kill the session.' It diagnoses first, identifies who owns the blocking query, offers a non-destructive fix if one exists, and only suggests killing it as the last resort with an explicit risk flag. That's real DBA judgment built into the prompt, not a generic wrapper."

**1:25-1:40 — Waits tab**
Quick glance at the wait-stats bar chart.
> "Same pattern everywhere — wait stats, agent jobs, disk, backup status."

**1:40-1:50 — Close**
Cut to the GitHub repo or a clean terminal with the stack.
> "Built solo — FastAPI, SQLAlchemy, React, TypeScript, Docker, and Groq's Llama 3.3 70B for the AI layer. I'm Firezer, a senior SQL Server DBA who also ships full-stack tools. Link's below."

## Delivery notes

- Do it in 3-4 short takes (per section) and trim in Loom rather than one perfect long take.
- Move the mouse slowly and deliberately — jerky cursor movement reads as nervous on camera.
- Use the AI panel frame (red severity badge + generated headline) as the video thumbnail — it's the most eye-catching still.
- After export: pin the Loom link in the README, in the GitHub repo description, and in your LinkedIn/portfolio post.
