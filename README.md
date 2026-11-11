# Telegram daily portfolio briefing — separate, read-only runner

Target: https://github.com/Devaryan-one-1/Multimodal-Claim-Verifier  
Delivery: Telegram Bot API  
Schedule: 09:00 Europe/London every day, weekends included  
Goal: portfolio readiness (tests, docs, reproducible demo)  
Budget: flexible  
**No writes to the target GitHub repository, ever.**

## Setup

1. Install Telegram. Visit https://t.me/BotFather, send `/newbot`, follow prompts, and **copy the bot token privately**.
2. In Telegram, open the new bot and send `/start`, followed by a test message such as `hello`.
3. On your own machine, retrieve your chat ID. Avoid putting tokens into shell history by setting them through your terminal's secure input:
   ```bash
   read -rs TELEGRAM_BOT_TOKEN; echo
   export TELEGRAM_BOT_TOKEN
   python - <<'PY'
   import json, os, urllib.request
   url = 'https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/getUpdates'
   with urllib.request.urlopen(url) as r: updates=json.load(r)
   print('Chat IDs:', [x.get('message', {}).get('chat', {}).get('id') for x in updates.get('result', []) if x.get('message')])
   PY
   ```
   If the list is empty, message the bot again and retry. If an existing webhook is configured, `getUpdates` will not work until it is removed; don't change a webhook you depend on.
4. **On GitHub, create a brand-new public repository** such as `portfolio-daily-notifier` (do NOT make changes in Multimodal-Claim-Verifier). Upload only `notifier.py`, `tests/`, and `.github/workflows/daily.yml` from this bundle. The supplied workflow is **manual-only** so tests cannot accidentally activate daily delivery. Keep bot credentials out of committed files. The target repository is queried with read-only REST `GET` calls; `actions/checkout` checks out only the notifier repository.
5. In your **new notifier repository** go to Settings → Secrets and variables → Actions → New repository secret. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. If the target repo is private, also add `GITHUB_READ_TOKEN`, a fine-grained token restricted to **only** that target repo with **Contents: Read** and Metadata access; no write permissions. If it is public, no GitHub token is required to read its public API (rate limited).
6. Go to Actions → **Read-only portfolio briefing** → Run workflow. Use `dry-run` first, and inspect logs for grounded output; no Telegram message is sent.
7. Run the workflow again using `test-sender` to send **one** test message. Check your Telegram chat. This does not read or modify GitHub.
8. If satisfied, run `send-once` for a one-off real briefing. The scheduled job sends a briefing every day at 09:00 UK time (subject to GitHub Actions scheduler delays). After confirming the test and single real briefing, replace `.github/workflows/daily.yml` in the **separate notifier repository** with `templates/daily-enabled.yml` from this bundle. This is the explicit activation step; the first workflow is intentionally manual-only.

## Local tests and dry run

```bash
python -m unittest discover -s tests -v
python notifier.py                 # GitHub GET only, prints draft; no Telegram send
python notifier.py --test-sender   # Telegram POST only, needs bot token + chat ID
python notifier.py --send          # GitHub GET and Telegram POST
```

## What is and isn't implemented

- Implemented: official Telegram sender, prepared UK-time scheduled workflow (activated only after replacing the manual-only workflow), read-only public GitHub API inspection, owner-commit detection within a **rolling 25-hour window** (limited to 30 recent commits), grounded missing-file checks (README/tests/CI/examples), message with links, explicit dry-run/test/send controls, no external Python dependencies, no paid AI API.
- **Not implemented:** full semantic code review, comprehensive tests/CI status interpretation, durable cross-day review state/deduplication, historical carry-forward, secrets redaction in third-party tooling, or guaranteed exact-time or exactly-once delivery. The agent does not claim these are implemented. Scheduled retries or manual `send-once` can result in duplicate messages. We recommend adding an explicitly authorized external private state store before claiming production-grade deduplication.
- An absent test directory does **not** prove no tests exist. Similarly, presence of a README does not imply good documentation. These heuristics are only first-pass suggestions, never a full audit.
- GitHub Actions for a public **notifier** repository using standard hosted runners is generally free, subject to current GitHub limits and policy. Telegram Bot API is free for ordinary low-volume direct messages. No paid language model is used.

Official docs: https://core.telegram.org/bots/api and https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
