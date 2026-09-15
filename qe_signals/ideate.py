"""Loop-engineered ideation: draft → guardrails → judge → improve, per cluster.

Rules that control spend and honesty:
  * stop the moment the judge score >= bar; otherwise iterate to max_iter, keep the best
  * a guardrail failure skips the judge for that iteration (one call saved) and goes
    straight to improve with the report
  * an invalid draft is retried once with a nudge; a second invalid draft abandons the
    cluster (best=None, reason='invalid_output') — recorded, never silently dropped
  * an invalid judge reply scores 0 for that iteration and consumes it
  * the judge's overall score is RECOMPUTED as the playbook-weighted mean of its
    per-criterion scores; the model's own total is not trusted
  * a run-level CallBudget stops further clusters with reason='budget'
"""

from __future__ import annotations

import re
from collections.abc import Callable

from qe_signals import guardrails, prompts
from qe_signals.llm import LLM, BudgetExceeded
from qe_signals.models import Cluster, Idea, IdeaResult, IterationRecord, Judgement, Signal

MAX_CONSECUTIVE_API_ERRORS = 3
REASON_BUDGET = "budget"
REASON_INVALID_OUTPUT = "invalid_output"
REASON_NO_JUDGED = "no_judged_iteration"
API_ERROR_PREFIX = "api_error"
WEIGHT_RE = re.compile(r"^###\s+([a-z0-9_]+)\s*\(weight\s+(\d+(?:\.\d+)?)\)", re.M)


def playbook_weights(playbook: str) -> dict[str, float]:
    """Parse '### name (weight N)' headings; empty dict means 'equal weights'."""
    return {name: float(w) for name, w in WEIGHT_RE.findall(playbook)}


def weighted_score(per_criterion: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted mean over EVERY playbook criterion; one the judge omitted scores 0.

    Normalising over only the returned keys would let a judge inflate the score by
    leaving out the criteria it scored badly.
    """
    if not per_criterion:
        return 0.0
    if not weights:
        return round(sum(per_criterion.values()) / len(per_criterion), 2)
    den = sum(weights.values())
    num = sum(
        w * max(0.0, min(100.0, float(per_criterion.get(name, 0.0)))) for name, w in weights.items()
    )
    return round(num / den, 2) if den else 0.0


def missing_criteria(per_criterion: dict[str, float], weights: dict[str, float]) -> list[str]:
    return sorted(set(weights) - set(per_criterion))


def ideate_cluster(
    cluster: Cluster,
    signals: dict[str, Signal],
    playbook: str,
    llm: LLM,
    *,
    bar: float = 75.0,
    max_iter: int = 3,
    seen_titles: set[str] | None = None,
    log: Callable[[str], None] = lambda m: None,
    weights: dict[str, float] | None = None,
    known_ids: set[str] | None = None,
    known_urls: set[str] | None = None,
) -> IdeaResult:
    weights = weights if weights is not None else playbook_weights(playbook)
    known_ids = known_ids if known_ids is not None else set(signals)
    known_urls = known_urls if known_urls is not None else {s.url for s in signals.values()}
    seen_titles = seen_titles if seen_titles is not None else set()

    records: list[IterationRecord] = []
    best: Idea | None = None
    best_score: float | None = None
    idea: Idea | None = None
    guard_text = ""
    fix_list: list[str] = []

    def result(reason: str, *, met_bar: bool | None = None) -> IdeaResult:
        return IdeaResult(
            cluster_key=cluster.key_term,
            best=best,
            best_score=best_score,
            met_bar=(
                met_bar
                if met_bar is not None
                else bool(best_score is not None and best_score >= bar)
            ),
            iterations=records,
            reason=reason,
        )

    try:
        for n in range(1, max_iter + 1):
            stage = "draft" if idea is None else "improve"
            if idea is None:
                system, user = prompts.draft(cluster, signals)
            else:
                system, user = prompts.improve(idea, cluster, signals, guard_text, fix_list)
            parsed = llm.structured(system, user, Idea, stage=f"{stage}:{cluster.key_term}")
            if not parsed.valid:
                # one nudge, then give up on this cluster
                nudge = (
                    user + "\n\nYour previous reply was not valid JSON for the requested shape: "
                )
                nudge += "; ".join(parsed.errors)[:400] + ". Return ONLY the JSON object."
                parsed = llm.structured(
                    system, nudge, Idea, stage=f"{stage}-retry:{cluster.key_term}"
                )
                if not parsed.valid:
                    records.append(
                        IterationRecord(
                            n=n,
                            stage=stage,
                            idea=None,
                            guardrails_passed=None,
                            judged=False,
                            score=None,
                            valid=False,
                        )
                    )
                    log(f"[ideate] {cluster.key_term}: invalid output twice — cluster abandoned")
                    return result(REASON_INVALID_OUTPUT, met_bar=False)
            idea = parsed.data
            report = guardrails.check(idea, known_ids, known_urls, seen_titles)
            guard_text = report.as_text()
            if not report.passed:
                records.append(
                    IterationRecord(
                        n=n,
                        stage=stage,
                        idea=idea,
                        guardrails_passed=False,
                        guardrail_issues=[i.message for i in report.issues],
                        judged=False,
                        score=None,
                        valid=True,
                    )
                )
                fix_list = []
                log(f"[ideate] {cluster.key_term} iter {n}: guardrails failed → improve")
                continue

            jsys, juser = prompts.judge(idea, playbook)
            jparsed = llm.structured(jsys, juser, Judgement, stage=f"judge:{cluster.key_term}")
            if jparsed.valid:
                score = weighted_score(jparsed.data.per_criterion, weights)
                fix_list = list(jparsed.data.fix_list)
                missing = missing_criteria(jparsed.data.per_criterion, weights)
                if missing:
                    fix_list.append(f"judge omitted criteria (scored 0): {', '.join(missing)}")
                    log(f"[ideate] {cluster.key_term} iter {n}: judge omitted {missing}")
            else:
                score = 0.0
                fix_list = ["previous judge reply was not valid JSON; keep the idea concrete"]
            records.append(
                IterationRecord(
                    n=n,
                    stage=stage,
                    idea=idea,
                    guardrails_passed=True,
                    judged=True,
                    score=score,
                    valid=jparsed.valid,
                )
            )
            log(f"[ideate] {cluster.key_term} iter {n}: score {score:.1f} (bar {bar:.0f})")
            if best_score is None or score > best_score:
                best, best_score = idea, score
            if score >= bar:
                break
    except BudgetExceeded:
        log(f"[ideate] {cluster.key_term}: LLM call budget exhausted")
        return result(REASON_BUDGET)
    except Exception as e:  # noqa: BLE001 — an API/network error is an outcome, not a crash
        msg = f"{API_ERROR_PREFIX}: {type(e).__name__}: {str(e)[:160]}"
        log(f"[ideate] {cluster.key_term}: {msg}")
        return result(msg)

    if best is not None:
        seen_titles.add(best.title.strip().lower())
    return result("" if best is not None else REASON_NO_JUDGED)


def ideate_all(
    clusters: list[Cluster],
    signals: dict[str, Signal],
    playbook: str,
    llm: LLM,
    *,
    max_ideas: int = 8,
    bar: float = 75.0,
    max_iter: int = 3,
    log: Callable[[str], None] = lambda m: None,
) -> tuple[list[IdeaResult], list[Cluster], list[Cluster]]:
    """Ideate the top `max_ideas` clusters.

    Returns (results, skipped_budget, skipped_errors): clusters never attempted because
    the call budget ran out, and clusters never attempted because the API-error breaker
    tripped. Two different stories for the digest.
    """
    results: list[IdeaResult] = []
    skipped_budget: list[Cluster] = []
    skipped_errors: list[Cluster] = []
    seen_titles: set[str] = set()
    weights = playbook_weights(playbook)
    known_ids = set(signals)
    known_urls = {s.url for s in signals.values()}
    budget_out = False
    consecutive_errors = 0
    for c in clusters[:max_ideas]:
        if budget_out or (llm.budget is not None and llm.budget.remaining == 0):
            skipped_budget.append(c)
            continue
        if consecutive_errors >= MAX_CONSECUTIVE_API_ERRORS:
            skipped_errors.append(c)
            continue
        r = ideate_cluster(
            c,
            signals,
            playbook,
            llm,
            bar=bar,
            max_iter=max_iter,
            seen_titles=seen_titles,
            log=log,
            weights=weights,
            known_ids=known_ids,
            known_urls=known_urls,
        )
        results.append(r)
        if r.reason == REASON_BUDGET:
            budget_out = True
        is_api_error = r.reason.startswith(API_ERROR_PREFIX)
        consecutive_errors = consecutive_errors + 1 if is_api_error else 0
    results.sort(key=lambda r: (-(r.best_score or -1), r.cluster_key))
    return results, skipped_budget, skipped_errors


def projected_calls(n_clusters: int, max_ideas: int, max_iter: int, max_calls: int) -> int:
    return min(max_calls, min(n_clusters, max_ideas) * max_iter * 2)
