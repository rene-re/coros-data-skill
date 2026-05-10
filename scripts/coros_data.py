#!/usr/bin/env python3
import argparse
import base64
import getpass
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

DEFAULT_WEB_BASE = "https://teameuapi.coros.com"
DEFAULT_MOBILE_BASE = "https://api.coros.com"
DEFAULT_MOBILE_REGION = ""
DEFAULT_MOBILE_LANGUAGE = "en-US"
ALLOWED_WEB_HOSTS = {"teamapi.coros.com", "teameuapi.coros.com"}
ALLOWED_MOBILE_HOSTS = {"api.coros.com"}
ENV_FILE = Path(__file__).resolve().parents[1] / ".coros.env"
WEB_LOGIN_SCRIPT = Path(__file__).resolve().parent / "coros_web_login.js"


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def env_truthy(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_base_url(value, var_name, allowed_hosts):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        fail(f"{var_name} must be an https URL")
    if parsed.username or parsed.password:
        fail(f"{var_name} must not include credentials")
    allow_custom = env_truthy("COROS_ALLOW_CUSTOM_BASE_URL")
    if parsed.hostname not in allowed_hosts and not allow_custom:
        allowed = ", ".join(sorted(allowed_hosts))
        fail(f"{var_name} host must be {allowed}; set COROS_ALLOW_CUSTOM_BASE_URL=1 to override")
    return value.rstrip("/")


WEB_BASE = normalize_base_url(os.environ.get("COROS_WEB_BASE", DEFAULT_WEB_BASE), "COROS_WEB_BASE", ALLOWED_WEB_HOSTS)
MOBILE_BASE = normalize_base_url(
    os.environ.get("COROS_MOBILE_BASE", DEFAULT_MOBILE_BASE),
    "COROS_MOBILE_BASE",
    ALLOWED_MOBILE_HOSTS,
)
WEB_TOKEN = os.environ.get("COROS_WEB_TOKEN") or os.environ.get("COROS_ACCESS_TOKEN")
MOBILE_TOKEN = os.environ.get("COROS_MOBILE_TOKEN")
MOBILE_EMAIL = os.environ.get("COROS_MOBILE_EMAIL")
MOBILE_PASSWORD = os.environ.get("COROS_MOBILE_PASSWORD")
MOBILE_REGION = os.environ.get("COROS_MOBILE_REGION", DEFAULT_MOBILE_REGION).strip()
MOBILE_LANGUAGE = os.environ.get("COROS_MOBILE_LANGUAGE", DEFAULT_MOBILE_LANGUAGE)
MOBILE_LOGIN_IV = b"weloop3_2015_03#"

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://training.coros.com",
    "Referer": "https://training.coros.com/",
}


def shell_quote(value):
    return "'" + value.replace("'", "'\"'\"'") + "'"


def ensure_secret_file_permissions(path):
    if path.exists() and path.stat().st_mode & 0o077:
        fail(f"{path} is readable by group/others; run: chmod 600 {path}")


def write_env_value(key, value, env_file=ENV_FILE):
    ensure_secret_file_permissions(env_file)
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    replacement = f"export {key}={shell_quote(value)}"
    replaced = False
    next_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"export {key}="):
            if not replaced:
                next_lines.append(replacement)
                replaced = True
            continue
        next_lines.append(line)
    if not replaced:
        next_lines.append(replacement)

    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(next_lines).rstrip() + "\n")
    os.chmod(env_file, 0o600)


def write_env_values(values, env_file=ENV_FILE):
    ensure_secret_file_permissions(env_file)
    lines = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    pending = dict(values)
    next_lines = []
    for line in lines:
        stripped = line.strip()
        replaced = False
        for key in list(pending):
            if stripped.startswith(f"{key}=") or stripped.startswith(f"export {key}="):
                next_lines.append(f"export {key}={shell_quote(pending.pop(key))}")
                replaced = True
                break
        if not replaced:
            next_lines.append(line)
    for key, value in pending.items():
        next_lines.append(f"export {key}={shell_quote(value)}")

    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(next_lines).rstrip() + "\n")
    os.chmod(env_file, 0o600)


def resolve_auth_inputs(args):
    email = args.email or MOBILE_EMAIL or os.environ.get("COROS_EMAIL")
    if not email:
        fail("Missing COROS email; pass --email or set COROS_EMAIL")
    if getattr(args, "password", None):
        print("Warning: --password can leak through shell history and process lists; prefer prompt input.", file=sys.stderr)
    password = getattr(args, "password", None) or MOBILE_PASSWORD or os.environ.get("COROS_PASSWORD")
    if not password:
        if sys.stdin.isatty():
            password = getpass.getpass("COROS password: ")
        else:
            fail("Missing COROS password; set COROS_PASSWORD or run interactively")
    return email, password


def web_login(email, password):
    env = os.environ.copy()
    env["COROS_EMAIL"] = email
    env["COROS_PASSWORD"] = password
    command = ["node", str(WEB_LOGIN_SCRIPT), "--print-token"]
    result = subprocess.run(command, env=env, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "web login failed"
        fail(message)
    token = result.stdout.strip()
    if not token:
        fail("Web login succeeded but token output missing")
    return token


def require_web_token():
    if not WEB_TOKEN:
        fail("Missing COROS_WEB_TOKEN (or COROS_ACCESS_TOKEN) for web API")


def require_mobile_token():
    if not MOBILE_TOKEN:
        fail("Missing COROS_MOBILE_TOKEN for mobile API")


def resolve_mobile_token():
    if MOBILE_TOKEN:
        return MOBILE_TOKEN
    if MOBILE_EMAIL and MOBILE_PASSWORD:
        return mobile_login(MOBILE_EMAIL, MOBILE_PASSWORD)
    fail("Missing COROS_MOBILE_TOKEN or COROS_MOBILE_EMAIL/COROS_MOBILE_PASSWORD for mobile API")


def web_get(path, params=None):
    require_web_token()
    headers = {**WEB_HEADERS, "accesstoken": WEB_TOKEN}
    response = requests.get(f"{WEB_BASE}{path}", params=params, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("result") not in (None, "0000") and data.get("apiCode") is None:
        fail(f"Web API error: {data.get('message', data)}")
    return data


def web_post(path, payload=None, params=None):
    require_web_token()
    headers = {**WEB_HEADERS, "accesstoken": WEB_TOKEN, "Content-Type": "application/json"}
    response = requests.post(f"{WEB_BASE}{path}", params=params, json=payload or {}, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("result") not in (None, "0000") and data.get("apiCode") is None:
        fail(f"Web API error: {data.get('message', data)}")
    return data


def mobile_post(path, payload=None, params=None):
    token = resolve_mobile_token()
    headers = {"Content-Type": "application/json", "accesstoken": token, "User-Agent": "okhttp/4.9.0"}
    query = dict(params or {})
    query.setdefault("accessToken", token)
    response = requests.post(f"{MOBILE_BASE}{path}", params=query, json=payload or {}, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "0000":
        fail(f"Mobile API error: {data.get('message', data)}")
    return data


def md5_hex(value):
    return hashlib.md5(value.encode()).hexdigest()


def mobile_encrypt(plaintext, app_key):
    try:
        from Cryptodome.Cipher import AES
    except ModuleNotFoundError:
        try:
            from Crypto.Cipher import AES
        except ModuleNotFoundError:
            fail("Missing Python dependency pycryptodomex/pycryptodome; install it with: pip install pycryptodomex")

    key = app_key.encode("ascii")
    data = plaintext.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    pad_len = 16 - (len(xored) % 16)
    padded = xored + bytes([pad_len] * pad_len)
    cipher = AES.new(key, AES.MODE_CBC, MOBILE_LOGIN_IV)
    return base64.b64encode(cipher.encrypt(padded)).decode("ascii")


class AuthFailure(Exception):
    pass


def mobile_login(email, password, region=None, language=None, fail_on_error=True):
    region = MOBILE_REGION if region is None else region
    region = region.strip() if isinstance(region, str) else region
    language = language or MOBILE_LANGUAGE
    app_key = str(random.randint(1_000_000_000_000_000, 9_999_999_999_999_999))
    payload = {
        "account": mobile_encrypt(email, app_key) + "\n",
        "accountType": 2,
        "appKey": app_key,
        "clientType": 1,
        "hasHrCalibrated": 0,
        "kbValidity": 0,
        "pwd": mobile_encrypt(md5_hex(password), app_key) + "\n",
        "skipValidation": False,
    }
    if region:
        payload["region"] = region
    yfheader = json.dumps(
        {
            "appVersion": 1125917087236096,
            "clientType": 1,
            "language": language,
            "mobileName": "sdk_gphone64_arm64,google,Google",
            "releaseType": 1,
            "systemVersion": "13",
            "timezone": 8,
            "versionCode": "404080400",
        },
        separators=(",", ":"),
    )
    headers = {
        "content-type": "application/json",
        "accept-encoding": "gzip",
        "user-agent": "okhttp/4.12.0",
        "request-time": str(int(time.time() * 1000)),
        "yfheader": yfheader,
    }
    response = requests.post(f"{MOBILE_BASE}/coros/user/login", json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "0000":
        message = f"Mobile login failed: {data.get('message', data)}"
        if fail_on_error:
            fail(message)
        raise AuthFailure(message)
    token = data.get("data", {}).get("accessToken")
    if not token:
        message = "Mobile login succeeded but accessToken missing"
        if fail_on_error:
            fail(message)
        raise AuthFailure(message)
    return token


def parse_date_to_ms(date_str):
    """Convert YYYYMMDD string to Unix timestamp in milliseconds."""
    if not date_str:
        return None
    text = str(date_str)
    if len(text) == 8 and text.isdigit():
        dt = datetime.strptime(text, "%Y%m%d")
        return int(dt.timestamp() * 1000)
    return int(float(date_str))  # already a number


def format_date(date_value):
    if not date_value:
        return "-"
    text = str(date_value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def format_duration(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_minutes(minutes):
    if minutes is None:
        return "-"
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    if hours:
        return f"{hours}h{mins:02d}m"
    return f"{mins}m"


def format_distance(meters):
    if meters is None:
        return "-"
    return f"{float(meters)/1000:.2f} km"


def cmd_activities(args):
    payload = web_get("/activity/query", {"size": args.size, "pageNumber": args.page})
    items = payload.get("data", {}).get("dataList", [])
    if not items:
        print("没有活动记录")
        return
    print(f"共 {payload.get('data', {}).get('count', len(items))} 条，当前第 {payload.get('data', {}).get('pageNumber', args.page)} 页")
    for index, item in enumerate(items, 1):
        print(f"\n--- 活动 {index} ---")
        print(f"名称: {item.get('name', '-')}")
        print(f"日期: {format_date(item.get('date'))}")
        print(f"距离: {format_distance(item.get('distance'))}")
        print(f"时长: {format_duration(item.get('totalTime'))}")
        print(f"平均心率: {item.get('avgHr', '-')}")
        print(f"最高心率: {item.get('maxHr', '-')}")
        print(f"训练负荷: {item.get('trainingLoad', '-')}")
        print(f"labelId: {item.get('labelId', '-')}")


def cmd_activity_detail(args):
    account_payload = web_get("/account/query")
    user_id = account_payload.get("data", {}).get("userId")
    if not user_id:
        fail("Cannot resolve userId from /account/query")
    sport_type = args.sport_type
    if sport_type is None:
        activities_payload = web_get("/activity/query", {"size": 50, "pageNumber": 1})
        for item in activities_payload.get("data", {}).get("dataList", []):
            if str(item.get("labelId")) == str(args.label_id):
                sport_type = item.get("sportType")
                break
    if sport_type is None:
        fail("sportType required; could not infer it from recent activity list")
    headers = {**WEB_HEADERS, "accesstoken": WEB_TOKEN}
    response = requests.post(
        f"{WEB_BASE}/activity/detail/query",
        data={"labelId": args.label_id, "userId": user_id, "sportType": str(sport_type)},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("result") != "0000":
        fail(f"Activity detail API error: {result.get('message', result)}")
    data = result.get("data", {})
    for key in ("graphList", "frequencyList", "gpsLightDuration"):
        data.pop(key, None)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_schedule(args):
    payload = web_get("/training/schedule/query", {"startDate": args.start, "endDate": args.end, "supportRestExercise": 1})
    data = payload.get("data", {})
    print(f"计划: {data.get('name', '-')}")
    print(f"周期: {format_date(data.get('startDay'))} ~ {format_date(data.get('endDay'))}")
    entities = data.get("entities", [])
    for index, item in enumerate(entities, 1):
        print(f"\n--- 日程 {index} ---")
        print(f"日期: {format_date(item.get('happenDay'))}")
        print(f"Day No: {item.get('dayNo', '-')}")
        print(f"状态: {item.get('executeStatus', '-')}")
        print(f"planProgramId: {item.get('planProgramId', '-')}")


def cmd_hrv(args):
    payload = web_get("/dashboard/query")
    hrv = payload.get("data", {}).get("summaryInfo", {}).get("sleepHrvData", {})
    print(f"最近 HRV: {hrv.get('avgSleepHrv', '-')}")
    print(f"HRV 基线: {hrv.get('sleepHrvBase', '-')}")
    print(f"HRV 波动: {hrv.get('sleepHrvSd', '-')}")
    for item in hrv.get("sleepHrvList", []):
        print(f"{format_date(item.get('happenDay'))}: avg={item.get('avgSleepHrv', '-')} base={item.get('sleepHrvBase', '-')}")


def cmd_daily_metrics(args):
    payload = web_get("/analyse/dayDetail/query", {"startDay": args.start, "endDay": args.end})
    print(json.dumps(payload.get("data", {}), ensure_ascii=False, indent=2))


def cmd_auth_mobile(args):
    email, password = resolve_auth_inputs(args)
    token = mobile_login(email, password, region=args.mobile_region, language=args.mobile_language)
    if args.write_env:
        write_env_value("COROS_MOBILE_TOKEN", token)
        print(f"Wrote COROS_MOBILE_TOKEN to {ENV_FILE}", file=sys.stderr)
    if args.print_token:
        print(token)
    if not args.write_env and not args.print_token:
        print("Mobile token obtained. Re-run with --write-env to store it or --print-token to display it.", file=sys.stderr)


def cmd_auth(args):
    email, password = resolve_auth_inputs(args)
    web_token = web_login(email, password)
    tokens = {"COROS_WEB_TOKEN": web_token}
    mobile_error = None
    try:
        tokens["COROS_MOBILE_TOKEN"] = mobile_login(
            email,
            password,
            region=args.mobile_region,
            language=args.mobile_language,
            fail_on_error=False,
        )
    except AuthFailure as error:
        mobile_error = str(error)

    if args.write_env:
        write_env_values(tokens)
        print(f"Wrote {', '.join(tokens)} to {ENV_FILE}", file=sys.stderr)
    if args.print_token:
        print(json.dumps(tokens, indent=2))
    if mobile_error:
        print(f"Warning: {mobile_error}; web token was still obtained.", file=sys.stderr)
    if not args.write_env and not args.print_token:
        print("COROS auth completed. Re-run with --write-env to store tokens or --print-token to display them.", file=sys.stderr)


def cmd_sleep(args):
    payload = mobile_post(
        "/coros/data/statistic/daily",
        {
            "allDeviceSleep": 1,
            "dataType": [5],
            "dataVersion": 0,
            "startTime": parse_date_to_ms(args.start),
            "endTime": parse_date_to_ms(args.end),
            "statisticType": 1,
        },
    )
    items = payload.get("data", {}).get("statisticData", {}).get("dayDataList", [])
    if not items:
        print("没有睡眠记录")
        return
    for index, item in enumerate(items, 1):
        sleep = item.get("sleepData", {})
        print(f"\n--- 睡眠 {index} ---")
        print(f"日期: {format_date(item.get('happenDay'))}")
        print(f"总睡眠: {format_minutes(sleep.get('totalSleepTime'))}")
        print(f"深睡: {format_minutes(sleep.get('deepTime'))}")
        print(f"浅睡: {format_minutes(sleep.get('lightTime'))}")
        print(f"REM: {format_minutes(sleep.get('eyeTime'))}")
        print(f"清醒: {format_minutes(sleep.get('wakeTime'))}")
        print(f"小睡: {format_minutes(sleep.get('shortSleepTime'))}")
        print(f"平均心率: {sleep.get('avgHeartRate', '-')}")
        print(f"最低心率: {sleep.get('minHeartRate', '-')}")
        print(f"最高心率: {sleep.get('maxHeartRate', '-')}")
        print(f"睡眠评分: {item.get('performance', '-')}")


def build_parser():
    parser = argparse.ArgumentParser(description="COROS dual-channel data tool")
    sub = parser.add_subparsers(dest="command", required=True)

    activities = sub.add_parser("activities")
    activities.add_argument("--size", type=int, default=10)
    activities.add_argument("--page", type=int, default=1)
    activities.set_defaults(func=cmd_activities)

    activity_detail = sub.add_parser("activity-detail")
    activity_detail.add_argument("--label-id", required=True)
    activity_detail.add_argument("--sport-type", type=int)
    activity_detail.set_defaults(func=cmd_activity_detail)

    schedule = sub.add_parser("schedule")
    schedule.add_argument("--start", required=True)
    schedule.add_argument("--end", required=True)
    schedule.set_defaults(func=cmd_schedule)

    hrv = sub.add_parser("hrv")
    hrv.set_defaults(func=cmd_hrv)

    daily = sub.add_parser("daily-metrics")
    daily.add_argument("--start", required=True)
    daily.add_argument("--end", required=True)
    daily.set_defaults(func=cmd_daily_metrics)

    auth = sub.add_parser("auth")
    auth.add_argument("--email")
    auth.add_argument("--password", help="Deprecated: prefer prompt input")
    auth.add_argument("--mobile-region", default=MOBILE_REGION)
    auth.add_argument("--mobile-language", default=MOBILE_LANGUAGE)
    auth.add_argument("--print-token", action="store_true")
    auth.add_argument("--write-env", action="store_true")
    auth.set_defaults(func=cmd_auth)

    auth_mobile = sub.add_parser("auth-mobile")
    auth_mobile.add_argument("--email")
    auth_mobile.add_argument("--password", help="Deprecated: prefer COROS_MOBILE_PASSWORD or interactive prompt")
    auth_mobile.add_argument("--mobile-region", default=MOBILE_REGION)
    auth_mobile.add_argument("--mobile-language", default=MOBILE_LANGUAGE)
    auth_mobile.add_argument("--print-token", action="store_true")
    auth_mobile.add_argument("--write-env", action="store_true")
    auth_mobile.set_defaults(func=cmd_auth_mobile)

    sleep = sub.add_parser("sleep")
    sleep.add_argument("--start", required=True)
    sleep.add_argument("--end", required=True)
    sleep.set_defaults(func=cmd_sleep)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
