# qe_signals — weekly QE signal digest and idea backlog

Adapted from Sisinty's 4-step content framework (topic selection → packaging → loop-engineered
scripting → posting) but aimed at **product discovery for quality engineering**:

| Stage   | What happens                                                                 | LLM? |
|---------|------------------------------------------------------------------------------|------|
| fetch   | `sources.yaml` → RSS/Atom, HN, GitHub, arXiv, sitemap+HTML → `Signal`s + health | no   |
| rank    | dedupe → deterministic score → lexical clusters → skip clusters ideated last run | no   |
| ideate  | per cluster: draft → guardrails → judge vs `dna_playbook.md` → improve, until bar | yes  |
| deliver | `docs/qe-signals/<YYYY>-W<WW>-digest.md` + `backlog.json` → Cognee dataset `qe_signals` | no   |

```bash
pip install -e ".[signals]"
make signals-dry          # fetch + rank, prints clusters + projected LLM calls (no spend)
make signals              # full run; digest under docs/qe-signals/
make signals ARGS="--since 14d --max-ideas 5 --bar 80 --no-cognee"
```

Always invoke as `python -m qe_signals.run` from the repo root (the package imports its
siblings; a bare `python qe_signals/run.py` will not resolve them).

## Exit codes (pr_gate vocabulary)

| Code | Light  | When                                                                                   |
|-----:|--------|----------------------------------------------------------------------------------------|
| 0    | green  | every source ok, every idea met the bar, Cognee push ok — or a quiet week (all seen)    |
| 10   | review | a source failed/empty, an idea below bar, a cluster with invalid LLM output, Cognee failed |
| 20   | red    | registry unparseable/invalid entry, playbook missing, zero signals, zero clusters, run in progress, LLM unavailable |

Fail CLOSED: registry, playbook and the pid lock are checked before any network or LLM spend.

## Files you own

- `sources.yaml` — the registry. `enabled: false` parks a source (say why in a comment).
  URLs must be http(s) to public hosts; private/loopback/link-local are refused at validation
  and on every redirect hop.
- `dna_playbook.md` — judging criteria with `(weight N)` headings. Its sha256 is stamped in
  every digest; the judge's overall score is recomputed as the weighted mean of its
  per-criterion scores.
- `vocab.yaml` — scoring terms. Pinned by `tests/fixtures/qe_signals/scores.golden.json`;
  delete the golden file to regenerate after a deliberate change.

## Windows and spend

- `--since` defaults to the time since the last **delivered** run (one that ended with a
  non-red verdict); dry runs and red runs (LLM unavailable, nothing fetched) never count, so a
  broken week cannot drop its signals from the next window. Fallback 7d, cap 30d.
- A missing `ANTHROPIC_API_KEY` is red before any fetch (dry-run exempt).
- A second run in the same ISO week writes `<week>-digest-<sha8>.md` alongside the published
  digest instead of overwriting it.
- LLM calls ≤ `min(--max-calls, clusters × --max-iter × 2)`; `--dry-run` prints the projection.
- The loop stops the moment an idea meets `--bar`; guardrail failures skip the judge call.

## First real run — 2026-09-15 (W38)

- 25 enabled sources: 15 ok, 7 empty (nothing in 7 days), 3 failed (arXiv 429/timeout — it
  throttles an IP after a burst). 190 signals → 92 clusters → 8 ideas, all ≥ 75.
- 29 LLM calls on `claude-sonnet-5` (projected max 48), ≈26k input + ≈10k output tokens
  (chars/4 estimate) — well under $1 at list price. Scores spread 54 → 87 across iterations;
  improve rounds raised flaky 61→75→85 and coverage 63→86, so the judge discriminates.
- Cognee push failed: the Anthropic account's credit balance ran out mid-run (Cognee's
  `cognify` uses the same key). Re-push by hand after topping up:
  `~/cognee/.venv/bin/python qe_signals/cognee_push.py docs/qe-signals/2026-W38-digest.md .ci/qe-signals/<run>/backlog.json`
- YouTube channel feeds returned 404 with a consent redirect from this network for every
  channel id; parked with `enabled: false`. Software Testing Weekly moved its feed to
  `/issues/rss/`.

## Tests

`pytest -k qe_signals` is network-free (injected http/resolver/clock/LLM client). One live
smoke test hits three verified sources and runs only when you ask for it:

```bash
QE_SIGNALS_RUN_NETWORK_TESTS=1 pytest tests/test_qe_signals_fetch.py -k live
```

## Cognee

`cognee_push.py` runs under `~/cognee/.venv/bin/python` (override with
`QE_SIGNALS_COGNEE_PYTHON`) and stores one document for the digest plus one per idea in
dataset `qe_signals`. Cognee dedupes identical text, so re-pushing an unchanged digest is a
no-op. Query from Claude Code with the `recall` tool and `datasets="qe_signals"`.
