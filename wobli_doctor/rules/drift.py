"""Rules about things that were true once and quietly stopped being true.

A comment, a constant or a flag that no longer matches the code around it is
worse than no comment at all: it actively misleads the next person, who is
usually the same person, six weeks later.
"""
from __future__ import annotations

import re

from .base import Finding, Level, Project, Rule


class VersionDrift(Rule):
    name = "version-drift"
    title = "The version shown in the app does not match the build"
    born_from = """
    The parent panel read '1.0.0 (9)' while pubspec said 1.0.0+10. It is
    hardcoded, so it goes stale on every single release - and it is the number
    a parent quotes when they report a problem, which sends support chasing
    the wrong build.
    """

    def run(self, project: Project):
        m = re.search(r"^version:\s*([\d.]+)\+(\d+)", project.pubspec, re.M)
        if not m:
            return
        real, build = m.group(1), m.group(2)
        for path, text in project.dart.items():
            for c in re.finditer(
                    r"(k\w*[Vv]ersion)\s*=\s*'([^']+)'", text):
                shown = c.group(2)
                if real in shown and build in re.findall(r"\d+", shown):
                    continue
                yield self.finding(
                    Level.WRONG,
                    f"{c.group(1)} says '{shown}', pubspec says {real}+{build}",
                    f"{project.rel(path)}:{project.line_of(path, c.start())}",
                    "Hardcoded, so it will drift again on the next release.\n"
                    "Read it from the build instead (package_info_plus) or add\n"
                    "it to whatever bumps the version.")


class FlagSilencesBehaviour(Rule):
    name = "flag-silences-behaviour"
    title = "A const flag that can only ever take one branch"
    born_from = """
    kE2Bare switched off three buttons at once, and everything behind them -
    the kitchen, the paint studio, the pickers - stayed in the file, reached by
    nothing, for months. Separately, kBigBubbleEnabled fired a breathing
    exercise whenever a child played hard for four seconds: not a child who
    needs calming, a child enjoying herself, interrupted to be told to breathe.
    A flag is a decision somebody made once; this prints them so they can be
    made again on purpose.
    """

    def run(self, project: Project):
        for path, text in project.dart.items():
            for m in re.finditer(
                    r"^const\s+bool\s+(k\w+)\s*=\s*\n?\s*(true|false)\s*;", text, re.M):
                name, value = m.group(1), m.group(2)
                dead = "false" if value == "true" else "true"
                uses = len(re.findall(
                    r"(?<![\w])" + re.escape(name) + r"(?![\w])", project.source)) - 1
                if uses == 0:
                    yield self.finding(
                        Level.NOTE,
                        f"{name} is {value} and nothing reads it",
                        f"{project.rel(path)}:{project.line_of(path, m.start())}",
                        "A decision with nothing left attached to it.")
                else:
                    yield self.finding(
                        Level.NOTE,
                        f"{name} = {value}, gating {uses} place(s); "
                        f"the '{dead}' side is unreachable",
                        f"{project.rel(path)}:{project.line_of(path, m.start())}",
                        "Not a fault - a standing decision. Worth re-reading\n"
                        "when its branch holds whole features.")


class CommentDescribesNothing(Rule):
    name = "stale-comment"
    title = "A comment naming code that is no longer there"
    born_from = """
    A doc comment on the cloud said the water 'empties and fills again slowly
    on its own' - and nothing in the project has ever written that field.
    Another said 'flip this to false and all four are back', months after all
    four had been deleted. Comments like these are the single thing that has
    misled me most: they read as evidence, and they are only memory.
    """

    #: Names a comment mentions in backticks or [brackets] should exist.
    REF = re.compile(r"///.*?[\[`](_?[a-zA-Z]\w{3,})[\]`]")

    def run(self, project: Project):
        for path, text in project.dart.items():
            for m in self.REF.finditer(text):
                name = m.group(1)
                # counted in CODE only: a comment that mentions the ghost
                # twice would otherwise prove itself right
                hits = len(re.findall(
                    r"(?<![\w.])" + re.escape(name) + r"(?![\w])",
                    project.code_only()))
                if hits == 0:
                    yield self.finding(
                        Level.RISK,
                        f"a comment points at `{name}`, which does not exist",
                        f"{project.rel(path)}:{project.line_of(path, m.start())}",
                        "The code moved and the comment did not. Next reader\n"
                        "will believe it.")
