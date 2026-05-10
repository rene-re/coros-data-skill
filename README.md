# COROS Data Skill

A small dual-channel COROS data tool for fetching both:

- **Web / Training Hub data**: activities, activity details, schedule, HRV, daily training metrics
- **Mobile / Daily health data**: sleep and other wellness-style daily stats

This repository is designed for personal analysis workflows and OpenClaw skill usage.

## What it does

The bundled script `scripts/coros_data.py` talks to two different COROS API surfaces:

- **Web API** (`teamapi.coros.com`)
  - Best for training-oriented data
  - Commands: `activities`, `activity-detail`, `schedule`, `hrv`, `daily-metrics`
- **Mobile API** (`api.coros.com`)
  - Best for sleep / daily health data
  - Commands: `sleep`, `auth-mobile`

This split matters because COROS exposes different data through different channels.

## Repository layout

```text
coros-data-skill/
├── SKILL.md
├── README.md
├── .gitignore
├── .coros.env
├── scripts/
│   └── coros_data.py
└── references/
    └── coros-workout-field-notes.md
```

## Requirements

- Python 3.9+
- `requests`
- `pycryptodomex`

Install dependencies:

```bash
pip install requests pycryptodomex
```

## Authentication

The script supports two auth channels.

### 1) Web API auth

Used for:

- `activities`
- `activity-detail`
- `schedule`
- `hrv`
- `daily-metrics`

Provide either:

- `COROS_WEB_TOKEN`
- or `COROS_ACCESS_TOKEN`

### 2) Mobile API auth

Used for:

- `sleep`

Provide either:

- `COROS_MOBILE_TOKEN`
- or `COROS_MOBILE_EMAIL` + `COROS_MOBILE_PASSWORD`

If email/password are provided, the script can log in and mint a mobile token automatically.

## Environment file

Create a local `.coros.env` file:

```bash
export COROS_WEB_TOKEN='your_web_token_here'
export COROS_MOBILE_TOKEN='your_mobile_token_here'
# or
# export COROS_MOBILE_EMAIL='you@example.com'
# export COROS_MOBILE_PASSWORD='your_password_here'
```

Optional overrides:

```bash
export COROS_WEB_BASE='https://teamapi.coros.com'
export COROS_MOBILE_BASE='https://api.coros.com'
```

Only `teamapi.coros.com` and `api.coros.com` are accepted by default. Set `COROS_ALLOW_CUSTOM_BASE_URL=1` only when you intentionally want to send credentials to another host.

Load env before running:

```bash
set -a && . ./.coros.env && set +a
```

## How to get tokens

### Web token

Use the Playwright login helper. It stores the token in `.coros.env` without printing it by default:

```bash
cd scripts
COROS_EMAIL='you@example.com' node coros_web_login.js --write-env
```

Add `--print-token` only when you intentionally need to display the token.

Chromium sandboxing is disabled by default for constrained VM compatibility. Set `COROS_PLAYWRIGHT_SANDBOX=1` only on hosts that support Chromium sandboxing.

### Mobile token

You can either:

- capture a token from the mobile app traffic / existing environment
- or let the script log in with email + password

Manual login command:

```bash
python3 scripts/coros_data.py auth-mobile --email you@example.com --write-env
```

Avoid passing passwords as command-line arguments; they can leak through shell history and process listings.

## Usage

### Show recent activities

```bash
python3 scripts/coros_data.py activities --size 10 --page 1
```

### Fetch activity detail

```bash
python3 scripts/coros_data.py activity-detail --label-id 123456789
```

If needed, provide `sportType` explicitly:

```bash
python3 scripts/coros_data.py activity-detail --label-id 123456789 --sport-type 1
```

### Fetch training schedule

```bash
python3 scripts/coros_data.py schedule --start 20260328 --end 20260410
```

### Fetch recent HRV summary

```bash
python3 scripts/coros_data.py hrv
```

### Fetch daily training / recovery metrics

```bash
python3 scripts/coros_data.py daily-metrics --start 20260324 --end 20260330
```

### Fetch sleep data

```bash
python3 scripts/coros_data.py sleep --start 20260330 --end 20260330
```

Multi-day range:

```bash
python3 scripts/coros_data.py sleep --start 20260324 --end 20260330
```

## Example output

### Sleep

```text
--- 睡眠 1 ---
日期: 2026-03-30
总睡眠: 5h52m
深睡: 38m
浅睡: 3h14m
REM: 2h00m
清醒: 13m
小睡: 0m
平均心率: 54
最低心率: 49
最高心率: 70
睡眠评分: -1
```

### HRV

```text
最近 HRV: 38
HRV 基线: 33
HRV 波动: 3.33
2026-03-24: avg=36 base=33
2026-03-25: avg=32 base=33
```

## Command reference

```bash
python3 scripts/coros_data.py activities --size 10 --page 1
python3 scripts/coros_data.py activity-detail --label-id <id> [--sport-type <type>]
python3 scripts/coros_data.py schedule --start YYYYMMDD --end YYYYMMDD
python3 scripts/coros_data.py hrv
python3 scripts/coros_data.py daily-metrics --start YYYYMMDD --end YYYYMMDD
python3 scripts/coros_data.py sleep --start YYYYMMDD --end YYYYMMDD
python3 scripts/coros_data.py auth-mobile --email <email> --write-env
```

## Data notes

- `sleep` uses the **mobile** API because daily health / sleep data is exposed there.
- `activities`, `schedule`, `hrv`, and `daily-metrics` use the **web** API.
- `activity-detail` may need `sportType`; the script tries to infer it from recent activities first.
- `daily-metrics` currently prints raw JSON for deeper analysis workflows.

For structured workout/schedule field notes, see:

- `references/coros-workout-field-notes.md`

## Security notes

- Do **not** commit real tokens or passwords.
- Keep `.coros.env` local only.
- Keep `.coros.env` and `.coros_web_session` mode `0600`.
- Avoid positional password arguments and default token printing.
- Rotate tokens if they leak.
- Treat captured auth material as sensitive account credentials.

## Known limitations

- **Mobile API is incomplete.** Several COROS mobile endpoints (particularly sleep/day and sleep/dayDetail) are mapped but return server errors or unknown parameter errors. Packet capture of the COROS mobile app (iOS/Android) would help identify the correct endpoints and parameters. PRs welcome.
- COROS web and mobile APIs expose different slices of data.
- Some field meanings are still empirical and documented in `references/coros-workout-field-notes.md`.
- Output is optimized for CLI inspection, not yet for stable JSON schemas across all commands.

## Contributing / PRs welcome

This tool was built from browser/network inspection of the COROS web app and limited mobile API reverse-engineering. If you have captured mobile app traffic (e.g., via Charles Proxy, mitmproxy, or similar) and can fill in the missing mobile endpoints, PRs are welcome. Also welcome: additional field mappings, more sport types, cleaner output formats.

## What we use it for

In practice, we use this tool for a few recurring jobs:

- Pulling **single-day sleep data** to judge whether recovery was real or fake
- Looking at **HRV vs baseline** before deciding whether to run easy, go hard, or rest
- Checking **daily recovery / fatigue metrics** after a harder session
- Inspecting recent **activities and training load** from COROS Training Hub
- Fetching a specific workout by `labelId` when a run needs deeper post-analysis
- Supporting lightweight coaching-style decisions like:
  - whether to run tomorrow
  - whether a session should be easy / moderate / hard
  - whether fatigue is coming from sleep debt or training accumulation

## TODO

There are still some rough edges and partially-mapped fields:

- [ ] Map more COROS field names to stable human-readable meanings
- [ ] Confirm the exact semantics of several workout intensity-related fields
- [ ] Normalize `daily-metrics` into a cleaner structured output instead of raw JSON only
- [ ] Document more `sportType` / `exerciseType` / `targetType` combinations from real account data
- [ ] Add clearer examples for recovery-state interpretation across multiple days

Some workout/schedule fields are still empirical and not fully matched to COROS UI labels yet. See `references/coros-workout-field-notes.md` for the currently verified subset.

## References / Acknowledgments

This project builds on prior work from the community:

- [wurongle/coros-data-skil](https://github.com/wurongle/coros-data-skil) — original inspiration for the dual web/mobile API approach and mobile auth implementation
- [harunme/coros-training-hub-skill](https://github.com/harunme/coros-training-hub-skill) — reference for Training Hub API exploration and activity/schedule fetching patterns

## License / ownership

This project wraps private COROS account data access for personal use. Review COROS terms and your local policies before redistributing or using it in shared environments.
