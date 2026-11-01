"""Every rule must find its own fault in the fixture, and must NOT find the
near-miss sitting next to it.

The second half is the point. A rule that fires on everything is not a check,
it is noise with a line number, and the first day someone learns to ignore it
is the day it stops being worth running. So each test asserts both.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from wobli_doctor.cli import ALL_RULES              # noqa: E402
from wobli_doctor.rules.base import Level, Project  # noqa: E402

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "examples" / "fixture"


def findings(rule_name: str):
    project = Project(FIXTURE)
    rule = next(r for r in ALL_RULES if r.name == rule_name)
    return list(rule.run(project))


def summaries(rule_name: str) -> str:
    return "\n".join(f.summary + " " + f.detail for f in findings(rule_name))


# --- each rule finds its own fault ---------------------------------------

def test_missing_clip_finds_the_wrong_name():
    assert "hiccup_el" in summaries("missing-clip")


def test_cut_list_finds_the_direct_call():
    assert "wob_giggle" in summaries("swallowed-by-cuts")


def test_tap_gate_finds_the_dead_handler():
    assert "_pickFlower" in summaries("tap-gated-on-drag")


def test_read_never_written_finds_the_dead_field():
    assert "_songIndex" in summaries("read-never-written")


def test_empty_handler_finds_the_no_op():
    assert "_letGoOfHand" in summaries("empty-handler")


def test_overlay_finds_the_unregistered_name():
    assert "kitchen" in summaries("overlay-by-name")


def test_version_drift_finds_the_stale_string():
    assert "1.0.0 (2)" in summaries("version-drift")


def test_stale_comment_finds_the_ghost():
    assert "_oldMixer" in summaries("stale-comment")


def test_harsh_sound_finds_the_ping():
    out = summaries("harsh-sound")
    assert "harsh_ping" in out, "needs numpy/soundfile installed"


def test_defined_never_called_finds_parent_wake():
    assert "parentWake" in summaries("defined-never-called")


# --- and must not fire on the near-miss beside it -------------------------

def test_tap_gate_ignores_a_guard_that_hands_off():
    """_pickBerry has the same guard but returns the tap path, which works.

    This is the false positive the tool shipped with for ten minutes.
    """
    assert "_pickBerry" not in summaries("tap-gated-on-drag")


def test_cut_list_ignores_a_group_picker():
    """laughProperly lists the cut clip inside voiceAny, which filters first."""
    out = findings("swallowed-by-cuts")
    assert all("laughProperly" not in f.detail for f in out)
    assert "clap" not in summaries("swallowed-by-cuts"), \
        "clap is only ever named inside a voiceAny list here"


def test_runtime_names_are_not_called_unreachable():
    """note_1..7 are named only as 'note_${(n - 1) % 7 + 1}'.

    The regex that got this wrong is the one that deleted the pentatonic
    scale from the real game. If this test ever fails, the tool is about to
    tell someone to delete their music.
    """
    out = summaries("unreachable-clip")
    for i in range(1, 8):
        assert f"note_{i}.wav" not in out


def test_levels_are_about_the_child_not_the_compiler():
    """A missing sound is BROKEN; an unreachable file is only a NOTE."""
    assert all(f.level is Level.BROKEN for f in findings("missing-clip"))
    assert all(f.level is Level.NOTE for f in findings("unreachable-clip"))
