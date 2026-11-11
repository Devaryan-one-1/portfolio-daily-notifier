#!/usr/bin/env python3
"""Read-only GitHub portfolio reviewer and Telegram delivery (stdlib only)."""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

OWNER = "Devaryan-one-1"
REPO = "Multimodal-Claim-Verifier"
BASE = f"https://github.com/{OWNER}/{REPO}"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
UA = "portfolio-daily-readonly-reviewer/1.0"


def request_json(url, token=None, payload=None):
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers,
        data=json.dumps(payload).encode() if payload is not None else None,
        method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=18) as res:
            return json.load(res)
    except urllib.error.HTTPError as exc:
        # Avoid exposing bearer tokens, response bodies, or private URL query strings.
        raise RuntimeError(f"HTTP {exc.code} from {'Telegram' if 'telegram.org' in url else 'GitHub'}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Network request failed or timed out") from None


def inspect_repo(token=None):
    metadata = request_json(API, token)
    branch = metadata.get("default_branch")
    if not branch:
        raise RuntimeError("Repository default branch unavailable")
    # GET only: no clone, checkout, push, workflow dispatch, or write operation.
    tree = request_json(f"{API}/git/trees/{urllib.parse.quote(branch, safe='')}?recursive=1", token)
    if tree.get("truncated"):
        raise RuntimeError("Repository tree truncated; cannot assess file presence reliably")
    paths = {item['path'] for item in tree.get('tree', []) if item.get('type') == 'blob'}
    commits = request_json(f"{API}/commits?sha={urllib.parse.quote(branch)}&per_page=30", token)
    readmes = [p for p in paths if p.lower() in ('readme.md', 'readme.rst', 'readme.txt')]
    return branch, paths, commits, readmes


def owner_changes(commits, now):
    # Rolling window avoids claiming a persistent last-review baseline that isn't stored.
    start = now.astimezone(dt.timezone.utc) - dt.timedelta(hours=25)
    changes = []
    for c in commits:
        author = c.get('author') or {}
        author_login = (author.get('login') or '').lower()
        commit = c.get('commit') or {}
        timestamp = ((commit.get('author') or {}).get('date') or '')
        if author_login != OWNER.lower():
            continue
        try:
            parsed = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            continue
        if parsed >= start:
            changes.append(c)
    return changes


def recommendations(paths, readmes, branch):
    """Only recommend absence backed by complete repository tree evidence."""
    lower = {p.lower() for p in paths}
    tasks = []
    test_paths = [p for p in paths if re.search(r'(^|/)(tests?/|test_[^/]+\.py$|[^/]+\.test\.[^/]+$|[^/]+\.spec\.[^/]+$)', p, re.I)]
    workflows = [p for p in paths if p.startswith('.github/workflows/') and (p.endswith('.yml') or p.endswith('.yaml'))]
    examples = [p for p in paths if p.lower().startswith(('examples/', 'demo/', 'samples/'))]
    if not readmes:
        tasks.append(("Write a root README covering purpose, setup and usage", "No root README was found in the complete tracked file tree", "README exists with verified run instructions", f"{BASE}/tree/{branch}", "1–2h"))
    if not test_paths:
        tasks.append(("Add one focused automated test for a verified core behavior", "No obvious test filenames/directories appear in the complete tracked file tree", "One meaningful test can be run locally with its command documented", f"{BASE}/tree/{branch}", "1–3h"))
    if not workflows:
        tasks.append(("Add a CI test workflow after a local test command is established", "No GitHub Actions workflow files appear in the tracked file tree", "CI runs the documented tests on a sample pull request", f"{BASE}/tree/{branch}", "1–2h"))
    if not examples:
        tasks.append(("Document a reproducible, sanitized input/output example", "No examples/, demo/, or samples/ directory appears in the tracked file tree", "A reviewer can reproduce an example from the README", f"{BASE}/tree/{branch}", "1–2h"))
    # Presence alone does not establish adequacy: don't invent deficiencies.
    return tasks[:3]


def compose(now, branch, commits, readmes, paths):
    day = now.strftime('%d %b %Y')
    changes = owner_changes(commits, now)
    tasks = recommendations(paths, readmes, branch)
    text = [f"Daily tasks — {OWNER}/{REPO} — {day}", "Goal: Portfolio-ready — tests, docs, demo"]
    if changes:
        text.append(f"Owner commits in the past 25h: {len(changes)} (latest: {changes[0].get('sha', '')[:7]})")
        text.append(f"Latest: {BASE}/commit/{changes[0].get('sha', '')}")
    else:
        text.append("No owner-authored commits identified in the past 25h (latest 30 commits checked).")
    if tasks:
        text.append("Evidence-based starting points (no changes made):")
        for n, (action, why, done, url, effort) in enumerate(tasks, 1):
            text.append(f"{n}. {action} (~{effort})\nWhy: {why}.\nDone: {done}.\nSource: {url}")
    else:
        text.append("No safe missing-file recommendation from tree metadata alone. Review README, tests and demo quality manually before choosing work.")
    text.append(f"Branch: {branch}. Assessment is file-tree based; no tests were executed.")
    return '\n'.join(text)


def telegram_send(token, chat_id, message):
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    if len(message) > 4096:
        raise RuntimeError("Brief exceeds Telegram's 4096-character limit")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    result = request_json(url, payload={"chat_id": chat_id, "text": message,
        "disable_web_page_preview": True})
    if not result.get('ok'):
        raise RuntimeError("Telegram rejected message")
    return result.get('result', {}).get('message_id')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-sender', action='store_true', help='Send only an explicit Telegram test')
    parser.add_argument('--send', action='store_true', help='Send the actual briefing (opt-in)')
    args = parser.parse_args()
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat = os.getenv('TELEGRAM_CHAT_ID', '')
    if args.test_sender:
        mid = telegram_send(token, chat, "✅ Telegram test: portfolio repo agent sender works. No GitHub changes were made.")
        print(f"Telegram test accepted (message_id={mid})")
        return
    try:
        now = dt.datetime.now(ZoneInfo('Europe/London'))
        branch, paths, commits, readmes = inspect_repo(os.getenv('GITHUB_READ_TOKEN'))
        brief = compose(now, branch, commits, readmes, paths)
    except RuntimeError as exc:
        # Fail closed: never deliver invented tasks after an unavailable source.
        print(f"Repository review unavailable: {exc}", file=sys.stderr)
        sys.exit(1)
    if not args.send:
        print('DRY RUN — no Telegram delivery; GitHub read-only\n')
        print(brief)
        return
    mid = telegram_send(token, chat, brief)
    print(f"Telegram briefing accepted (message_id={mid}). GitHub was read-only.")


if __name__ == '__main__':
    main()
