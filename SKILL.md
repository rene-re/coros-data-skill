---
name: coros-data-skill
description: Access COROS data through a dual-channel integration: use mobile API for daily health metrics like sleep stages, sleep heart rate, and wellness-style daily stats; use COROS Training Hub web API for activities, activity details, training plans, workout programs, training schedule, HRV, recovery, threshold metrics, and training analysis. Use when the user asks about COROS, sleep, REM, deep sleep, resting heart rate, HRV, training load, activities, runs, rides, workouts, training plans, or schedule data.
---

# COROS Data Skill

Use the bundled script at `{baseDir}/scripts/coros_data.py`.

## Channel selection

- Use `mobile` endpoints for daily health and sleep-oriented questions.
- Use `web` endpoints for activity, training, and analysis-oriented questions.
- Prefer not to expose the channel split to the user unless it matters.

## Auth model

- Load environment from `{baseDir}/.coros.env` when present.
- Web API uses `COROS_WEB_TOKEN`.
- Mobile API can use either `COROS_MOBILE_TOKEN` or `COROS_MOBILE_EMAIL` + `COROS_MOBILE_PASSWORD`.
- Prefer env-based mobile login for this skill.
- Use `auth-mobile` to mint a mobile token manually when needed.
- **Web token** — `COROS_WEB_TOKEN` is obtained via Playwright browser login (see below).
- If neither token nor credentials are present, mobile commands cannot run.

### Getting Web Token via Playwright

The web API (`COROS_WEB_TOKEN`) cannot be obtained via mobile API login. Use the Playwright script:

```bash
cd {baseDir}/scripts
node coros_web_login.js [email] [password]
```

This prints the token to stdout. To save it:

```bash
cd {baseDir}/scripts
TOKEN=$(node coros_web_login.js)
sed -i "s/export COROS_WEB_TOKEN='.*'/export COROS_WEB_TOKEN='$TOKEN'/" ../.coros.env
```

The script:
1. Launches a headless Chromium browser
2. Navigates to the COROS Training Hub login page
3. Fills credentials and **checks the hidden privacy policy checkbox** (which blocks naive automation)
4. Submits the form and waits for navigation
5. Extracts the `CPL-coros-token` cookie (the web API access token)
6. Saves session cookies to `../.coros_web_session` for potential reuse

**Note:** The privacy policy checkbox must be checked — it is visually hidden and rejects programmatic clicks. The script uses `evaluate()` to check it directly via JavaScript.

## Common commands

```bash
set -a && . {baseDir}/.coros.env && set +a

# Get web token (Playwright — needed for activity/schedule/HRV data)
node {baseDir}/scripts/coros_web_login.js

# Mint mobile token (for sleep / daily health)
python3 {baseDir}/scripts/coros_data.py auth-mobile --email <email> --password <password>

# Activities (uses COROS_WEB_TOKEN)
python3 {baseDir}/scripts/coros_data.py activities --size 10

# Activity detail
python3 {baseDir}/scripts/coros_data.py activity-detail --label-id <id>

# Training schedule
python3 {baseDir}/scripts/coros_data.py schedule --start 20260328 --end 20260410

# HRV
python3 {baseDir}/scripts/coros_data.py hrv

# Sleep (uses COROS_MOBILE_TOKEN)
python3 {baseDir}/scripts/coros_data.py sleep --start 20260321 --end 20260406
```

## Analysis framework

When the user asks for analysis instead of raw data, organize the answer around these blocks.

### Sleep quality

Focus on recovery quality, not just time in bed.

- Total sleep duration
- Deep sleep duration
- REM duration
- Light sleep duration
- Awake duration / fragmentation
- Nap duration
- Sleep average heart rate
- Sleep min / max heart rate
- Sleep HRV
- HRV vs baseline
- Multi-day sleep stability

Use this block to judge whether recovery is real, partial, or clearly insufficient.

### Single-run analysis

Separate performance, cost, and mechanics.

- Performance: distance, duration, pace, splits, elevation
- Cost: average HR, max HR, HR zones, training load, average power
- Mechanics: cadence, stride length, ground time, stride height, stride ratio, ground balance, leg stiffness when available

Use this block to answer whether the run was efficient, forced, drifting, or mechanically unstable.

### Multi-run trend analysis

Look for trends and coupling, not isolated values.

- Pace trend
- HR trend
- Same-pace HR change
- Same-HR pace change
- Power trend
- Cadence / stride length trend
- Ground time trend
- Vertical oscillation related trend via stride height / stride ratio
- Training load trend
- Long-run recovery pattern

Use this block to judge whether fitness is improving, stagnating, or being masked by fatigue.

### Body change / recovery state

Combine sleep and training.

- Resting heart rate
- Sleep HRV and baseline deviation
- Recovery percentage / recovery state
- Full recovery hours
- Fatigue indicators
- ATI / CTI
- Training load ratio
- Recent 7-day and 28-day changes

Use this block to judge readiness, overload risk, and whether intensity should be raised or reduced.

### Practical combination rules

Prefer combined interpretations over single metrics.

- Poor sleep + HRV down + resting HR up -> likely under-recovered or stressed
- Same pace + lower HR -> aerobic efficiency improved
- Same effort + longer ground time + shorter stride -> fatigue or form degradation
- Rising training load + worsening sleep -> overload risk
- Better sleep + HRV recovery + faster pace at same HR -> positive adaptation

## Workout field notes

- When modifying COROS structured workouts or schedule payloads, read `{baseDir}/references/coros-workout-field-notes.md` first.
- Persist any newly confirmed field semantics there.
- Do not present guessed enum meanings as facts.

## Response style

- Summarize clearly in Chinese unless the user asked otherwise.
- Normalize dates and units.
- If a channel is unavailable because a token is missing, say exactly which token is missing.
- When a field is absent in the API response, say it is unavailable instead of guessing.
- For analysis requests, explicitly separate observations, interpretation, and actionable takeaways.
