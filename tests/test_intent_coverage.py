"""Unit tests for intent-coverage — does the test assert the requirement's terms?"""
from __future__ import annotations

from pr_gate import intent_coverage as ic

# ---- term extraction + normalisation --------------------------------------- #

def test_salient_terms_pulls_words_and_quoted_phrases():
    words, quoted = ic.salient_terms('Completing an item reveals "Clear completed".')
    assert "clear completed" not in words          # quoted words aren't double-counted
    assert quoted == ["Clear completed"]
    assert "complet" in {ic._norm(w) for w in ("Completing",)} or "completing" in words
    assert "reveal" in words                        # de-pluralised content word


def test_stopwords_dropped():
    words, _ = ic.salient_terms("A user can add an item to the list")
    assert "user" not in words and "the" not in words and "can" not in words
    assert "add" in words and "item" in words and "list" in words


def test_norm_depluralises():
    assert ic._norm("items") == "item"
    assert ic._norm("filters") == "filter"
    assert ic._norm("count") == "count"             # no trailing s → unchanged


# ---- scoring --------------------------------------------------------------- #

def test_strong_when_test_asserts_terms_and_quoted():
    req = 'add an item; the "items left" count reflects it'
    test = 'add(item); expect(count).toHaveText("1 item left")'
    s = ic.score(req, test)
    assert s["grade"] == "strong" and s["coverage"] >= 0.7
    assert '"items left"' in s["matched"]


def test_weak_when_test_only_references_id():
    req = 'The Active filter shows only incomplete items.'
    test = 'expect(true).toBe(true);'               # asserts nothing about the intent
    s = ic.score(req, test)
    assert s["grade"] == "weak" and s["coverage"] < 0.4


def test_quoted_phrase_matches_singular_plural():
    # requirement says "items left"; the test asserts "1 item left"
    s = ic.score('the "items left" count', '.toHaveText("1 item left")')
    assert '"items left"' in s["matched"]


# ---- block extraction + full grade ----------------------------------------- #

def test_test_text_for_isolates_the_right_block():
    content = (
        'test("adds TMVC-1", () => { expect(x).toHaveText("1 item left"); });\n'
        'test("deletes TMVC-2", () => { expect(y).toBeHidden(); });'
    )
    block = ic.test_text_for({"s.spec.ts": content}, "TMVC-1")
    assert "1 item left" in block and "toBeHidden" not in block


def test_grade_all_flags_untested():
    reqs = {"TMVC-1": "add an item; count shows 1 item left",
            "TMVC-9": "the Completed filter shows completed items"}
    files = {"s.spec.ts": 'test("adds TMVC-1", () => { expect(c).toHaveText("1 item left"); });'}
    trace = ic.reqdrift.build_traceability(files)
    report = ic.grade_all(reqs, trace, files)
    by_id = {r["id"]: r for r in report["rows"]}
    assert by_id["TMVC-9"]["grade"] == "untested"   # no test traces to it
    assert by_id["TMVC-1"]["coverage"] > 0.0
    assert report["summary"]["untested"] == 1
