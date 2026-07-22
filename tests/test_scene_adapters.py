"""Unit tests for the scene-tier engine adapters (scripts/scene_adapters.py).

The adapters are pure functions that emit JS text, so they unit-test cleanly.
The headline guard is `test_emitted_js_is_syntactically_valid`: it runs `node
--check` over every engine's emitted point/count expression with a value full of
JS-breaking characters (`'`, `"`, `\\`, newline). That directly catches the
error-string escaping class of bug — an adapter that interpolates a raw value
into a single-quoted JS literal produces unparseable code and fails here.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/klew/scripts")
)
scene_adapters = pytest.importorskip("scene_adapters")

ENGINES = scene_adapters.supported_engines()
EXPECTED = {"sigma", "chartjs", "fabric", "pixi", "konva", "echarts", "cytoscape", "three", "phaser"}


def _scene(engine, value="Alpha", by="name", instance="window.__x"):
    return {"engine": engine, "instance": instance, "by": by, "value": value}


# --- registry -----------------------------------------------------------------

def test_expected_engines_registered():
    assert set(ENGINES) == EXPECTED


def test_unknown_engine_raises():
    with pytest.raises(ValueError):
        scene_adapters.point_expr(_scene("no-such-engine"))
    with pytest.raises(ValueError):
        scene_adapters.count_expr(_scene("no-such-engine"))


# --- expression shape ---------------------------------------------------------

@pytest.mark.parametrize("engine", ENGINES)
def test_point_expr_is_an_arrow_that_stashes_and_returns(engine):
    expr = scene_adapters.point_expr(_scene(engine))
    assert expr.startswith("() =>")
    assert "window.__ksel" in expr  # stashed for the CLI flow
    assert "return pt" in expr


@pytest.mark.parametrize("engine", ENGINES)
def test_count_expr_is_an_arrow_that_returns(engine):
    expr = scene_adapters.count_expr(_scene(engine))
    assert expr.startswith("() =>")
    assert "return" in expr


def test_default_instance_used_when_omitted():
    scene = {"engine": "sigma", "by": "label", "value": "X"}  # no instance
    assert scene_adapters.default_instance("sigma") in scene_adapters.point_expr(scene)


# --- escaping: value/by are always JSON-encoded, and the JS parses ------------

@pytest.mark.parametrize("engine", ENGINES)
def test_value_is_json_encoded_not_raw(engine):
    value = "O'Brien"
    expr = scene_adapters.point_expr(_scene(engine, value=value))
    assert json.dumps(value) in expr  # "O'Brien" (safely quoted), never a bare '


NODE = shutil.which("node")
TRICKY = "O'Brien \"the\" \\end\nline"  # apostrophe, quote, backslash, newline


@pytest.mark.skipif(NODE is None, reason="node not on PATH")
@pytest.mark.parametrize("engine", ENGINES)
def test_emitted_js_is_syntactically_valid(engine):
    """node --check every emitted expression with a JS-hostile value.

    An adapter that dropped a raw value into a single-quoted literal (the bug the
    fix addressed) emits unparseable JS and fails this — for point AND count.
    """
    scene = _scene(engine, value=TRICKY, by="name")
    for kind, expr in (("point", scene_adapters.point_expr(scene)),
                       ("count", scene_adapters.count_expr(scene))):
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
            fh.write("const __f = (" + expr + ");\n")
            path = fh.name
        try:
            r = subprocess.run([NODE, "--check", path], capture_output=True, text=True)
            assert r.returncode == 0, f"{engine} {kind} emitted invalid JS:\n{r.stderr}"
        finally:
            os.unlink(path)


# --- validate_scene -----------------------------------------------------------

def test_validate_scene_accepts_good():
    assert scene_adapters.validate_scene(_scene("sigma", by="label")) == []


@pytest.mark.parametrize("bad,needle", [
    ("not-a-dict", "must be an object"),
    ({"by": "label", "value": "X"}, "engine"),                       # missing engine
    ({"engine": "nope", "by": "label", "value": "X"}, "engine"),     # unknown engine
    ({"engine": "sigma", "value": "X"}, "by"),                       # missing by
    ({"engine": "sigma", "by": "label"}, "value"),                   # missing value
])
def test_validate_scene_flags_problems(bad, needle):
    problems = scene_adapters.validate_scene(bad)
    assert problems, f"expected a problem for {bad!r}"
    assert any(needle in p for p in problems)


# --- canonical selector -------------------------------------------------------

def test_canonical_selector_format():
    assert scene_adapters.canonical_selector("sigma", "label", "Alice") == "scene:sigma/label=Alice"
