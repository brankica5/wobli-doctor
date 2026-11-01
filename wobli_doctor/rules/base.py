"""The rule framework.

Every rule in this tool was born from a bug that actually shipped in a
children's game and was found by a child or by its author playing it - never
by the compiler, and never by a generic linter. Each rule therefore carries
the story of the bug it came from, because a check whose reason you cannot
state is a check nobody will keep.
"""
from __future__ import annotations

import dataclasses
import enum
import pathlib
import re
import typing


class Level(enum.Enum):
    """How much a finding matters to a child holding the phone."""

    BROKEN = "broken"      # something a child does gets no response at all
    WRONG = "wrong"        # it responds, but with the wrong thing
    RISK = "risk"          # fine today, will break on the next change
    NOTE = "note"          # worth knowing, nothing is wrong


@dataclasses.dataclass(frozen=True)
class Finding:
    """One thing worth telling a human about."""

    rule: str
    level: Level
    summary: str
    where: str = ""
    detail: str = ""

    def __str__(self) -> str:
        head = f"[{self.level.value.upper():7}] {self.summary}"
        if self.where:
            head += f"\n          {self.where}"
        if self.detail:
            for line in self.detail.strip().splitlines():
                head += f"\n          {line}"
        return head


class Project:
    """A Flutter/Flame project on disk, read once and shared by every rule.

    Rules get the whole source as one string as well as per-file, because the
    bugs this tool looks for are usually a mismatch BETWEEN two files - a
    sound named in Dart with no file in assets, a flag in one file gating
    behaviour in another.
    """

    def __init__(self, root: str | pathlib.Path):
        self.root = pathlib.Path(root)
        if not (self.root / "pubspec.yaml").exists():
            raise SystemExit(f"{self.root} has no pubspec.yaml - not a Flutter project")
        self.dart: dict[pathlib.Path, str] = {}
        for p in sorted((self.root / "lib").rglob("*.dart")):
            try:
                self.dart[p] = p.read_text(encoding="utf-8")
            except OSError:
                continue
        self.source = "\n".join(self.dart.values())
        self.pubspec = (self.root / "pubspec.yaml").read_text(encoding="utf-8")

    def rel(self, path: pathlib.Path) -> str:
        try:
            return str(path.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def line_of(self, path: pathlib.Path, index: int) -> int:
        """1-based line number of a character offset, for pointing at code."""
        return self.dart[path].count("\n", 0, index) + 1

    def audio_files(self) -> list[pathlib.Path]:
        out: list[pathlib.Path] = []
        for folder in ("sfx", "voice", "audio"):
            d = self.root / "assets" / folder
            if d.is_dir():
                out += [p for p in sorted(d.iterdir())
                        if p.suffix.lower() in (".wav", ".mp3", ".ogg", ".m4a")]
        return out

    # --- helpers every rule needs ----------------------------------------

    _LITERAL = re.compile(r"'([A-Za-z0-9_][A-Za-z0-9_\-]{1,58})'")
    # ANY expression inside ${...}, not just one starting with a letter.
    #
    # The first version required a letter after `${`, so it failed on
    # 'note_${(n - 1) % 7 + 1}' - which begins with a bracket - and reported
    # note_1..7 as unreachable. That is the EXACT regex whose earlier cousin
    # deleted the pentatonic scale from the real game. The fixture caught it
    # on the first run, which is the entire argument for having a fixture.
    _INTERP = re.compile(
        r"'([A-Za-z0-9_]*?)\$(?:\{[^}']*\}|[A-Za-z_]\w*)([A-Za-z0-9_]*)'")

    _COMMENT = re.compile(r"^\s*///?.*$", re.M)

    def code_only(self) -> str:
        """The source with comment lines removed.

        A rule asking "does this name still exist?" must not count the
        comment that mentions it, or a stale comment proves itself right -
        which is exactly how stale-comment failed its own test: the fixture
        names the ghost twice, so counting raw occurrences found two and
        concluded the identifier was alive.
        """
        if not hasattr(self, "_code_cache"):
            self._code_cache = self._COMMENT.sub("", self.source)
        return self._code_cache

    def literals(self) -> set[str]:
        """Every plain quoted string in the project."""
        return set(self._LITERAL.findall(self.source))

    def name_families(self) -> set[str]:
        """Stems of names the code BUILDS at runtime: 'note_${n}' -> 'note_'.

        This exists because an earlier audit of mine matched literals only,
        reported note_1..7 and lick_1..3 as unused, and deleted them - the
        pentatonic scale the game plays constantly. Any check that decides a
        file is unreachable has to understand interpolation or it will tell
        someone to delete their music.
        """
        return {m.group(1) for m in self._INTERP.finditer(self.source) if m.group(1)}


class Rule:
    """One check. Subclasses set the metadata and implement run()."""

    name: str = "unnamed"
    title: str = ""
    #: The real bug this rule exists because of. Printed by `--why`.
    born_from: str = ""

    def run(self, project: Project) -> typing.Iterable[Finding]:  # pragma: no cover
        raise NotImplementedError

    def finding(self, level: Level, summary: str, where: str = "",
                detail: str = "") -> Finding:
        return Finding(self.name, level, summary, where, detail)
