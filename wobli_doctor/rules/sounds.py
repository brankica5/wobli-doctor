"""Rules about sound: named but missing, present but unreachable, crossed off
but still called, and measurably unpleasant.

Four separate bugs in one evening, all of them silent to the compiler.
"""
from __future__ import annotations

import os
import re

from .base import Finding, Level, Project, Rule


class MissingClip(Rule):
    name = "missing-clip"
    title = "A sound is asked for by name and the file is not there"
    born_from = """
    hiccup_el was called at three places. The file is hiccup.wav. The hiccup
    had never once played, and nothing anywhere said so: audioplayers fails
    quietly, the analyser sees a string, and a silent sound is indistinguishable
    from a sound you were not listening for.
    """

    CALLS = (
        r"sfx\(\s*'([A-Za-z0-9_\-]+)'",
        r"sfxSolo\(\s*'([A-Za-z0-9_\-]+)'",
        r"sfxAny\(\s*'[^']*'\s*,\s*(?:const\s*)?\[([^\]]*)\]",
        r"voice\(\s*'([A-Za-z0-9_\-]+)'",
        r"startLoop\(\s*'([A-Za-z0-9_\-]+)'",
    )

    def run(self, project: Project):
        have = {os.path.splitext(p.name)[0] for p in project.audio_files()}
        called: set[str] = set()
        for pat in self.CALLS:
            for m in re.finditer(pat, project.source, re.S):
                chunk = m.group(1)
                if "," in chunk or "'" in chunk:
                    called |= set(re.findall(r"'([A-Za-z0-9_\-]+)'", chunk))
                else:
                    called.add(chunk)
        for m in re.finditer(
                r"voiceAny\(\s*'[^']*'\s*,\s*(?:const\s*)?\[([^\]]*)\]",
                project.source, re.S):
            called |= set(re.findall(r"'([A-Za-z0-9_\-]+)'", m.group(1)))

        for name in sorted(called - have):
            where = ""
            for path, text in project.dart.items():
                i = text.find(f"'{name}'")
                if i >= 0:
                    where = f"{project.rel(path)}:{project.line_of(path, i)}"
                    break
            yield self.finding(
                Level.BROKEN,
                f"'{name}' is played but no file of that name exists",
                where,
                "This call is silent every time it runs.")


class SwallowedByCutList(Rule):
    name = "swallowed-by-cuts"
    title = "A clip on the cut list is still called directly, so it plays nothing"
    born_from = """
    Branka crossed wob_giggle off her list weeks ago. voiceAny filters the cut
    list BEFORE it picks, so groups merely listing that clip quietly choose
    another - that half worked. But eleven places called sfx('wob_giggle')
    directly, sfx checks the cut list and returns, and those eleven laughs had
    been SILENT ever since. Not repetitive: absent.
    """

    def run(self, project: Project):
        m = re.search(r"_cut\s*=\s*\{(.*?)\}", project.source, re.S)
        if not m:
            return
        cut = set(re.findall(r"'([A-Za-z0-9_\-]+)'", m.group(1)))
        if not cut:
            return
        for name in sorted(cut):
            direct: list[str] = []
            for path, text in project.dart.items():
                for hit in re.finditer(
                        r"\.(?:sfx|sfxSolo|voice)\(\s*'" + re.escape(name) + r"'",
                        text):
                    direct.append(
                        f"{project.rel(path)}:{project.line_of(path, hit.start())}")
            if direct:
                yield self.finding(
                    Level.BROKEN,
                    f"'{name}' is on the cut list but called directly "
                    f"at {len(direct)} place(s)",
                    ", ".join(direct[:4]) + (" ..." if len(direct) > 4 else ""),
                    "The cut check returns early, so these produce no sound at\n"
                    "all. Route them through a group picker, which filters the\n"
                    "cut list before choosing and so falls back to a clip that\n"
                    "was kept.")


class UnreachableClip(Rule):
    name = "unreachable-clip"
    title = "An audio file no code can name"
    born_from = """
    Reported as a note and never as something to delete, on purpose. An audit
    of mine matched literal strings only, called note_1..7 and lick_1..3
    unused, and deleted them - the pentatonic scale the game plays constantly.
    Woblero builds clip names at the moment of use, so this rule treats an
    interpolated name as a PREFIX FAMILY and counts every file under it as
    reachable. It still cannot see a name assembled from a variable it never
    sees, which is exactly why it only ever reports.
    """

    def run(self, project: Project):
        literals = project.literals()
        families = project.name_families()
        dead = []
        for p in project.audio_files():
            stem = os.path.splitext(p.name)[0]
            if stem in literals:
                continue
            if any(stem.startswith(f) for f in families):
                continue
            dead.append(p)
        if not dead:
            return
        mb = sum(p.stat().st_size for p in dead) / 1048576
        yield self.finding(
            Level.NOTE,
            f"{len(dead)} audio files are never named by any code ({mb:.1f} MB)",
            "", "\n".join(
                [f"- {project.rel(p)}" for p in dead[:8]]
                + ([f"... and {len(dead) - 8} more"] if len(dead) > 8 else [])
                + ["",
                   "NOT a deletion list. Check each one by hand: a name built",
                   "at runtime from a variable can be invisible here."]))


class HarshSound(Rule):
    name = "harsh-sound"
    title = "A sound measures outside the palette's own limits"
    born_from = """
    squish_el_3 and _4 - real recordings, bought and shipped - sit at 60-61%
    of their energy above 5 kHz with crests of 22.6 and 32.8. _playSquish
    picks between four, so a child got one of those on every second squeeze,
    on the most-touched interaction in the game. Nobody had ever measured
    them: they were bought, so they were assumed fine.
    """

    HI_LIMIT = 0.35     # fraction of energy above 5 kHz
    CREST_LIMIT = 9.0   # peak over RMS
    ATTACK_MIN_MS = 5.0

    def run(self, project: Project):
        try:
            from ..audio import measure
        except Exception as exc:  # numpy/soundfile missing
            yield self.finding(
                Level.NOTE, "audio measurement unavailable", "", str(exc))
            return
        for p in project.audio_files():
            m = measure(p)
            if m is None:
                continue
            bad = []
            if m.above_5k > self.HI_LIMIT:
                bad.append(f"{m.above_5k * 100:.0f}% above 5 kHz "
                           f"(limit {self.HI_LIMIT * 100:.0f}%) - thin, not textured")
            if m.crest > self.CREST_LIMIT:
                bad.append(f"crest {m.crest:.1f} (limit {self.CREST_LIMIT:.0f}) "
                           "- a spike an ear flinches at")
            if m.attack_ms < self.ATTACK_MIN_MS:
                bad.append(f"attack {m.attack_ms:.1f} ms "
                           f"(min {self.ATTACK_MIN_MS:.0f}) - heard as a click")
            if bad:
                yield self.finding(
                    Level.WRONG,
                    f"{p.name} is outside the palette's limits",
                    project.rel(p),
                    "\n".join(f"- {b}" for b in bad))
