#!/usr/bin/env bash
# stlc_demo.sh — run all six canonical STLC phases end-to-end, live, and show
# what each one produces. The subject is ParaBank; every phase uses a real tool
# from this repo, no mocks.
#
#   bash pr_gate/stlc_demo.sh              # full run against the live demo
#   STLC_OFFLINE=1 bash pr_gate/stlc_demo.sh   # skip phases 4-6 (no network)
#
# Exit code mirrors the closure verdict: 0 GO · 10 HOLD · 20 NO-GO.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

APP=parabank
BASE=https://parabank.parasoft.com/parabank/
REQ=docs/requirements/PB-parabank-transfer.md
DESIGN=docs/requirements/PB-parabank-test-design.json
WORK=.ci/stlc/$APP
mkdir -p "$WORK"

hr() { printf '\n\033[1m[%s/6] %s\033[0m\n' "$1" "$2"; }

hr 1 "Requirement analysis  (yilsf — surface what is unspecified)"
grep -cE '^PB-[0-9]+:' "$REQ" | xargs printf '  %s acceptance criteria with stable IDs\n'
grep -c 'UNKNOWN' "$DESIGN" | xargs printf '  %s clarification UNKNOWNs carried into the design\n'
echo "  requirement: $REQ"

hr 2 "Test planning  (test_plan.py — computed exit criteria, not asserted)"
python3 pr_gate/test_plan.py --app "$APP" --requirements "$REQ" --design "$DESIGN" \
  --specs 'e2e/parabank/*.spec.ts' --base-url "$BASE" \
  --out "$WORK/plan.md" --json "$WORK/plan.json" >/dev/null
python3 - "$WORK/plan.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1])); t = p["totals"]
print(f"  {t['cases']} cases · {t['automated']} automated · {t['blocked']} blocked on clarification")
for c in p["exit_criteria"]:
    print(f"  {'✅' if c['met'] else ('⏳' if c['met'] is None else '❌')} {c['text']}")
PY

hr 3 "Test-case design  (yilsf test-design — real guardrails)"
( cd yilsf && npx tsx scripts/session_validate.ts \
    --artefact "../$DESIGN" --requirements generated/pb-requirements.txt --structured 2>/dev/null ) \
  | python3 -c "import json,sys; d=json.load(sys.stdin); g=d['guardrails']; \
print(f\"  guardrails: {'PASS' if g['passed'] else 'FAIL'} · schema {'valid' if d.get('schemaValid') else 'INVALID'} · \
{len(g['coveredRequirements'])}/{len(g['coveredRequirements'])+len(g['uncoveredRequirements'])} requirements covered\")" \
  || echo "  (design validation skipped — needs yilsf deps: cd yilsf && npm install)"

if [ "${STLC_OFFLINE:-0}" = "1" ]; then
  echo; echo "STLC_OFFLINE=1 — stopping after phase 3 (no network)."; exit 0
fi

hr 4 "Test environment setup  (env_setup.py — the phase that used to break the demo)"
if ! python3 pr_gate/env_setup.py --app "$APP" --base-url "$BASE" --out "$WORK/env.sh"; then
  echo "  environment NOT ready — aborting before execution so a broken env is not misreported as red."
  exit 2
fi
# shellcheck disable=SC1090
source "$WORK/env.sh"

hr 5 "Test execution  (Playwright + qe_evidence — sealed proof pack)"
( cd e2e && npx playwright test -c parabank --workers=1 --reporter=json 2>/dev/null ) > "$WORK/results.json"
python3 - "$WORK/results.json" <<'PY'
import json, sys
sys.path.insert(0, ".")
from pr_gate.closure import summarize
e = summarize(json.load(open(sys.argv[1])))
print(f"  {e['passed']} passed · {e['failed']} failed · {e['skipped']} skipped (blocked, ship as fixme)")
PY
python3 pr_gate/qe_evidence.py seal --app "$APP" --pr stlc-demo \
  --verdict "$WORK/results.json" --input results="$WORK/results.json" \
  --out "$WORK/evidence" 2>/dev/null | sed 's/^/  /'

hr 6 "Test cycle closure  (closure.py — one ship verdict)"
python3 pr_gate/closure.py --app "$APP" --plan "$WORK/plan.json" \
  --results "$WORK/results.json" --out "$WORK/closure.md" >/dev/null
RC=$?  # 0 GO · 10 HOLD · 20 NO-GO
sed 's/^/  /' "$WORK/closure.md" | head -14

echo; printf '\033[1mDemo artefacts in %s: plan.md · results.json · evidence/ · closure.md\033[0m\n' "$WORK"
exit "$RC"
