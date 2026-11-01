"""wobli-doctor - a daily check for a Flutter/Flame children's game.

Run it against a project and it reports the things that compile, analyse
cleanly, and still do nothing.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

from .rules.base import Level, Project, Rule
from .rules import drift, reachability, sounds

ALL_RULES: list[Rule] = [
    sounds.MissingClip(),
    sounds.SwallowedByCutList(),
    sounds.HarshSound(),
    sounds.UnreachableClip(),
    reachability.TapGatedOnDrag(),
    reachability.OverlayByName(),
    reachability.ReadButNeverWritten(),
    reachability.EmptyHandler(),
    reachability.DefinedNeverCalled(),
    drift.VersionDrift(),
    drift.CommentDescribesNothing(),
    drift.FlagSilencesBehaviour(),
]

ORDER = [Level.BROKEN, Level.WRONG, Level.RISK, Level.NOTE]


def _why() -> int:
    for rule in ALL_RULES:
        print(f"\n## {rule.name} - {rule.title}")
        print((rule.born_from or "").strip("\n"))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wobli-doctor",
        description="Find the code that runs, compiles, and does nothing.")
    ap.add_argument("project", nargs="?", default=".",
                    help="path to the Flutter project (default: .)")
    ap.add_argument("--only", action="append", metavar="RULE",
                    help="run only these rules (repeatable)")
    ap.add_argument("--skip", action="append", metavar="RULE", default=[],
                    help="skip these rules (repeatable)")
    ap.add_argument("--json", metavar="FILE", help="also write findings as JSON")
    ap.add_argument("--why", action="store_true",
                    help="print the real bug each rule was born from, and exit")
    ap.add_argument("--fail-on", default="broken",
                    choices=[l.value for l in Level] + ["never"],
                    help="exit non-zero at this level or worse (default: broken)")
    args = ap.parse_args(argv)

    if args.why:
        return _why()

    project = Project(args.project)
    rules = [r for r in ALL_RULES
             if (not args.only or r.name in args.only) and r.name not in args.skip]

    findings = []
    for rule in rules:
        try:
            findings += list(rule.run(project))
        except Exception as exc:  # a broken rule must not hide the others
            print(f"  ! rule {rule.name} crashed: {exc}", file=sys.stderr)

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"wobli-doctor  {project.root}  {stamp}")
    print(f"{len(project.dart)} dart files, {len(project.audio_files())} audio files, "
          f"{len(rules)} rules\n")

    for level in ORDER:
        batch = [f for f in findings if f.level is level]
        if not batch:
            continue
        print(f"--- {level.value.upper()} ({len(batch)}) " + "-" * 40)
        for f in batch:
            print(f)
            print()

    counts = {l.value: sum(1 for f in findings if f.level is l) for l in ORDER}
    print("  ".join(f"{k}: {v}" for k, v in counts.items()))
    if not findings:
        print("nothing to report")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"project": str(project.root), "when": stamp,
             "findings": [{"rule": f.rule, "level": f.level.value,
                           "summary": f.summary, "where": f.where,
                           "detail": f.detail} for f in findings]},
            indent=2, ensure_ascii=False), encoding="utf-8")

    if args.fail_on == "never":
        return 0
    limit = ORDER.index(Level(args.fail_on))
    return 1 if any(ORDER.index(f.level) <= limit for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
