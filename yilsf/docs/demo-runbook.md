# TestMu Demo Runbook

A rehearsed, wifi-proof script for the live demo. Everything here runs **offline
on the deterministic mock** unless you deliberately flip to a real provider, so
the projector can't betray you. Times are a guide for a ~8-minute demo slot.

## Before you walk on stage

```bash
cd yilsf
npm install          # once
npm test             # 36 green — a credibility slide in itself
npm run eval:mock    # confirm the comparison table renders
```

Have two terminals open: one in `yilsf/`, one showing the golden set /
requirements file. Font size up. `clear` between steps.

Screenshot every expected output below in advance — the mock is deterministic, so
your screenshots will match the live run exactly. That's your backup if the
terminal dies.

---

## Step 1 — The problem (raw call invents things) · ~1.5 min

Show what an undisciplined call does with an under-specified requirement.

```bash
npm run --silent eval:mock
```

Point at two rows in the table:

```
Ambiguities invented (/3)   3   0    YILSF
Ambiguities flagged (/3)    0   3    YILSF
```

**The line to say:** *"Same model, same requirements. The only difference is the
discipline. The raw call invented a lockout threshold nobody specified; the
disciplined run refused and asked."*

---

## Step 2 — The discipline, live (flag vs invent) · ~3 min

The money moment. Run the framework on a requirement that is deliberately vague.

```bash
echo "AUTH-003: The account locks after several failed login attempts." \
  | npm run --silent cli -- test-design --trace
```

Scroll the `trace` to show **generate → critique → validate**, then land on the
final artefact. Call out that the ambiguous count/duration is marked, not
invented.

Now show it is *structured*, not just prose:

```bash
echo "AUTH-003: The account locks after several failed login attempts." \
  | npm run --silent cli -- test-design --structured
```

**The line to say:** *"It's not just calmer prose — it's validated JSON. Every
case has a risk tag and traces to the requirement, and the missing threshold
lands in `unknowns` instead of a made-up number."*

---

## Step 3 — Same discipline, different job (code review) · ~2 min

Prove it isn't only test generation.

```bash
printf 'diff --git a/auth.ts b/auth.ts\n+ const hash = await bcrypt.hash(pw,10)\n' > /tmp/pr.diff
echo "PROJ-123: Passwords must be hashed before storage." \
  | npm run --silent cli -- code-review --diff /tmp/pr.diff --constitution code-review --structured
```

**The line to say:** *"Same engine, a review constitution swapped in. Every
finding carries a verdict and cites evidence — and it says `unknown` when the
diff can't prove the requirement, instead of rubber-stamping it."*

---

## Step 4 — Optional: real model · ~1 min (only if wifi is solid)

```bash
export YILSF_PROVIDER=vertex   # or ANTHROPIC_API_KEY / CLAUDE_CODE_USE_VERTEX
echo "AUTH-003: The account locks after several failed login attempts." \
  | npm run --silent cli -- test-design --structured
```

Same shape, real tokens. If the network stutters, **do not wait** — cut back to
the mock screenshots.

---

## Closing line

*"Three things to steal on Monday: prune context before every task; add a
self-critique pass; and make at least one guardrail deterministic code, not a
prompt. That's the whole framework."*

## If something breaks

- Terminal dies → the screenshots (mock is deterministic, they match).
- `npm run` noise → add `--silent`; warnings go to stderr, output is clean JSON.
- Someone asks "is the mock cheating?" → yes, and say so: it's a deterministic
  *illustration*; the real proof is `npm run eval` (Step 4) and the eval README's
  independent metrics. Owning that is more convincing than hiding it.
