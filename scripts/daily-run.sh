#!/usr/bin/env bash
# Horizon daily run + deploy to GitHub Pages
# Scheduled via launchd: ~/Library/LaunchAgents/com.horizon.daily.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

cd "$PROJECT_DIR"

TODAY=$(date +%Y-%m-%d)
HTML_FILE="data/summaries/horizon-${TODAY}-zh.html"

# ── Idempotent: skip if today's report already generated ─────
if [ -f "$HTML_FILE" ]; then
    echo "$LOG_PREFIX Today's report already exists, skipping."
    open "$PROJECT_DIR/$HTML_FILE"
    exit 0
fi

echo "$LOG_PREFIX Starting Horizon daily run..."

# ── 1. Wait for proxy if needed (up to 60s) ──────────────────
PROXY_HOST="${HTTP_PROXY:-http://127.0.0.1:7890}"
PROXY_HOST="${PROXY_HOST#http://}"
PROXY_HOST="${PROXY_HOST#https://}"
PROXY_HOST="${PROXY_HOST%%/*}"
PROXY_PORT="${PROXY_HOST##*:}"
PROXY_HOST="${PROXY_HOST%:*}"

for i in $(seq 1 12); do
    if curl -s --max-time 3 "http://${PROXY_HOST}:${PROXY_PORT}" >/dev/null 2>&1; then
        echo "$LOG_PREFIX Proxy is ready (after ${i}x5s)"
        break
    fi
    if [ "$i" -eq 12 ]; then
        echo "$LOG_PREFIX Proxy not available, unsetting proxy vars"
        unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
    fi
    sleep 5
done

# ── 2. Pull latest code (best-effort) ────────────────────────
git pull --quiet origin main 2>/dev/null || echo "$LOG_PREFIX git pull skipped"

# ── 3. Sync dependencies (best-effort) ───────────────────────
uv sync --quiet 2>/dev/null || echo "$LOG_PREFIX uv sync skipped"

# ── 4. Run Horizon ───────────────────────────────────────────
uv run horizon --hours 24 || {
    echo "$LOG_PREFIX Horizon failed with exit code $?"
    osascript -e "display notification \"请检查日志\" with title \"Horizon 日报失败\" subtitle \"${TODAY}\""
    exit 1
}

# ── 5. Open HTML + notify ────────────────────────────────────
if [ -f "$HTML_FILE" ]; then
    open "$PROJECT_DIR/$HTML_FILE"
    ITEM_COUNT=$(grep -c '<article class="item-card"' "$PROJECT_DIR/$HTML_FILE" 2>/dev/null || echo "?")
    osascript -e "display notification \"${ITEM_COUNT} 条重要资讯\" with title \"Horizon 日报就绪\" subtitle \"${TODAY}\" sound name \"Glass\""
    echo "$LOG_PREFIX Report opened: $HTML_FILE ($ITEM_COUNT items)"
fi

# ── 6. Deploy to gh-pages (best-effort) ─────────────────────
echo "$LOG_PREFIX Deploying to gh-pages..."

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Try to fetch gh-pages; if remote doesn't exist, skip gracefully
if ! git ls-remote --exit-code origin gh-pages >/dev/null 2>&1; then
    echo "$LOG_PREFIX No gh-pages branch on remote, skipping deploy."
    echo "$LOG_PREFIX Done (no deploy)."
    exit 0
fi

git fetch origin gh-pages:gh-pages 2>/dev/null || {
    echo "$LOG_PREFIX Failed to fetch gh-pages, skipping deploy."
    exit 0
}

git worktree add "$TMPDIR" gh-pages 2>/dev/null || {
    echo "$LOG_PREFIX Worktree failed, skipping deploy."
    exit 0
}

cp -r docs/* "$TMPDIR/" 2>/dev/null || true

cd "$TMPDIR"
if git diff --quiet && git diff --cached --quiet; then
    echo "$LOG_PREFIX Nothing new to deploy."
else
    git add -A
    git commit -m "Daily Summary: $TODAY" || true
    git push origin gh-pages 2>/dev/null || echo "$LOG_PREFIX Push failed (no network?)"
fi

cd "$PROJECT_DIR"
git worktree remove "$TMPDIR" 2>/dev/null || true

echo "$LOG_PREFIX Done."
