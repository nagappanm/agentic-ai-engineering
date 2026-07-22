#!/usr/bin/env bash
# Proof that a Sigma.js (WebGL) graph node can be clicked *through the same
# `@playwright/cli` that klew wraps* — no external CDP bridge, no hardcoded
# pixels. The node's screen point is computed by `eval` (page.evaluate) from its
# LABEL via Sigma's `graphToViewport`, then a REAL click is issued with the CLI's
# `mousemove`/`mousedown`/`mouseup` so Sigma's own WebGL hit-testing fires.
#
# Usage: BASE_URL=http://127.0.0.1:8123 bash drive-through-cli.sh <NodeLabel>
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8123}"
LABEL="${1:-Alice}"
CONFIG="$(dirname "$0")/cli.config.json"
S=sigma

cli() { playwright-cli -s="$S" "$@"; }

cleanup() { playwright-cli -s="$S" close >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "== open $BASE_URL/index.html =="
cli open "$BASE_URL/index.html" --config "$CONFIG" >/dev/null
# Wait until Sigma has painted its first frame.
cli eval "() => new Promise(r => { const t = setInterval(() => { if (window.__sigmaReady) { clearInterval(t); r('ready'); } }, 50); })" >/dev/null

echo "== compute '$LABEL' screen point via scene model (eval) =="
# Stash the derived point on window, then read each axis as a plain number.
cli eval "() => {
  const g = window.__graph, s = window.__sigma;
  const id = g.findNode((n,a) => a.label.toLowerCase() === '${LABEL}'.toLowerCase());
  if (!id) throw new Error('no node labelled ${LABEL}');
  const a = g.getNodeAttributes(id);
  const vp = s.graphToViewport({ x: a.x, y: a.y });
  const r = s.getContainer().getBoundingClientRect();
  window.__pt = { x: Math.round(r.left + vp.x), y: Math.round(r.top + vp.y) };
  return 'ok';
}" >/dev/null
X=$(cli --raw eval "() => window.__pt.x")
Y=$(cli --raw eval "() => window.__pt.y")
echo "   derived point: ($X,$Y)"

echo "== real click at ($X,$Y) via CLI mouse commands =="
cli mousemove "$X" "$Y" >/dev/null
cli mousedown >/dev/null
cli mouseup   >/dev/null

echo "== read selection back =="
# --raw returns a JSON string value (quoted); strip the surrounding quotes.
SEL=$(cli --raw eval "() => document.querySelector('#selected b').textContent" | sed -E 's/^"(.*)"$/\1/')
echo "   #selected = $SEL"

if [ "$SEL" = "$LABEL" ]; then
  echo "PASS: clicked Sigma node '$LABEL' through playwright-cli (scene model + mouse)."
  exit 0
else
  echo "FAIL: expected '$LABEL', got '$SEL'."
  exit 1
fi
