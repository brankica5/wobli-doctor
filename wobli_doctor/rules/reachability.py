"""Rules about code that runs, compiles and does nothing.

Every one of these passes `flutter analyze` without a word, because what is
wrong is not the syntax but whether a child can ever reach it.
"""
from __future__ import annotations

import re

from .base import Finding, Level, Project, Rule


class TapGatedOnDrag(Rule):
    name = "tap-gated-on-drag"
    title = "A touch handler that only a drag can ever satisfy"
    born_from = """
    The flower and the sun sat dead for MONTHS. Both handlers opened with
    `if (_touchPointer < 0) return false;` and the tap path dispatches without
    a pointer, so that test is true for every tap and the handler returned
    immediately. Painting is the heart of the game and it was invisible to a
    child who tapped. Two different children found it by tapping flowers that
    did nothing; no tool ever did.
    """

    #: A field that is set only while a drag is in flight.
    DRAG_FLAGS = ("_touchPointer", "_paintPointer", "_dragPointer")

    def run(self, project: Project):
        for path, text in project.dart.items():
            for m in re.finditer(
                    r"^\s{2}(?:bool|void)\s+(_\w+)\s*\([^)]*\)\s*\{\s*\n"
                    r"\s*if\s*\(\s*(" + "|".join(self.DRAG_FLAGS) + r")\s*<\s*0\s*\)"
                    # ONLY a bare bail-out counts. The first version of
                    # this rule matched any `return` and flagged
                    # _pickFlower, whose guard reads
                    # `return _armFlower(f, p)` - the tap path, doing
                    # the actual work. A check that cries wolf is worse
                    # than no check, so it has to see that NOTHING
                    # happens, not merely that the function leaves.
                    r"\s*return\s*(?:false|null|true)?\s*;",
                    text, re.M):
                yield self.finding(
                    Level.BROKEN,
                    f"{m.group(1)}() returns immediately unless a drag is in "
                    f"flight ({m.group(2)} < 0)",
                    f"{project.rel(path)}:{project.line_of(path, m.start())}",
                    "If this handler is registered for taps as well, every tap\n"
                    "hits this line and nothing happens. Check whether the tap\n"
                    "path dispatches with a pointer id.")


class OverlayByName(Rule):
    name = "overlay-by-name"
    title = "An overlay is added or removed by a name nothing registers"
    born_from = """
    Eight calls named overlays - add('food'), add('creative'), add('musicButton')
    - that were no longer registered at all. They are strings, so the analyser
    and the compiler both pass them without a word. None of them ran, because
    each sat behind a flag that happened to be switched the right way - and
    flipping that flag back would have thrown on the first frame.
    """

    def run(self, project: Project):
        registered = set(re.findall(
            r"'([a-zA-Z]\w*)'\s*:\s*\(\s*\w+\s*,\s*\w+\s+\w+\s*\)\s*=>",
            project.source))
        if not registered:
            return
        for path, text in project.dart.items():
            for m in re.finditer(
                    r"overlays\s*\.\s*(add|remove|isActive)\(\s*'(\w+)'\s*\)", text):
                if m.group(2) not in registered:
                    yield self.finding(
                        Level.RISK,
                        f"overlays.{m.group(1)}('{m.group(2)}') names an overlay "
                        "that is not registered",
                        f"{project.rel(path)}:{project.line_of(path, m.start())}",
                        "Registered: " + ", ".join(sorted(registered)) + "\n"
                        "A string the compiler cannot see. If this line ever\n"
                        "runs, it throws.")


class ReadButNeverWritten(Rule):
    name = "read-never-written"
    title = "A field that gates behaviour and nothing ever sets"
    born_from = """
    _songIndex chose the 'wild' dance - a clear repeating routine a child can
    copy. _dancedBefore opened an idle thought read in four places. Both were
    set by a screen that had been deleted, so both were permanently at their
    default and both behaviours were silently off. The code reads, the
    behaviour never happens, and nothing says so.
    """

    SKIP = {"_rng", "_random"}

    def run(self, project: Project):
        # `late final x = ...` is assigned AT its declaration and is correct
        # Dart; flagging it told a clean field it was broken. Only a plain
        # mutable declaration can be the fault this rule looks for.
        decl = re.compile(
            r"^\s{2}(?!late)(?!final)(?:bool|int|double|String)\s+"
            r"(_\w+)\s*=\s*([^;]+);", re.M)
        for path, text in project.dart.items():
            for m in decl.finditer(text):
                name, init = m.group(1), m.group(2).strip()
                if name in self.SKIP or len(name) < 4:
                    continue
                writes = len(re.findall(
                    # postfix AND prefix: ++_mealN is an assignment too, and
                    # missing it reported a counter that increments on every
                    # meal as a field nothing ever sets
                    r"(?:\+\+|--)\s*" + re.escape(name) + r"(?![\w])"
                    r"|(?<![\w.])" + re.escape(name) +
                    r"\s*(?:=(?!=)|\+\+|--|\+=|-=|\*=)", project.source))
                reads = len(re.findall(
                    r"(?<![\w.])" + re.escape(name) + r"(?![\w=])", project.source))
                # one write is the declaration itself
                if writes <= 1 and reads >= 3:
                    yield self.finding(
                        Level.WRONG,
                        f"{name} is read {reads - 1}x and never assigned "
                        f"after its declaration",
                        f"{project.rel(path)}:{project.line_of(path, m.start())}",
                        f"It is always {init}. Whatever it was meant to switch\n"
                        "on can never happen. Either something that used to set\n"
                        "it has gone, or it was never wired up.")


class DefinedNeverCalled(Rule):
    name = "defined-never-called"
    title = "A method nobody calls"
    born_from = """
    parentWake() was written as the way a parent lets a sleeping Wobli up from
    behind the gate, and was described in review as exactly that. Nothing
    anywhere called it: there was no way back up except killing the app, which
    also reset the clock, so the bedtime limit undid itself.
    """

    FRAMEWORK = {
        "update", "render", "onLoad", "onMount", "onRemove", "toString", "paint",
        "shouldRepaint", "createState", "initState", "dispose", "build",
        "didUpdateWidget", "onTapDown", "onTapUp", "onTapCancel", "onDragStart",
        "onDragUpdate", "onDragEnd", "onDragCancel", "onGameResize", "onMouseMove",
        "onLongTapDown", "onDoubleTapDown", "onScaleStart", "onScaleUpdate",
        "onScaleEnd",
    }

    def run(self, project: Project):
        decl = re.compile(
            r"^\s{2}(?:(?:Future|Stream)<[^>]*>|void|bool|double|int|String|Color|"
            r"Vector2|Offset)\s+(_?[a-zA-Z]\w*)\s*\(", re.M)
        for path, text in project.dart.items():
            for m in decl.finditer(text):
                name = m.group(1)
                if name in self.FRAMEWORK or name.startswith("build"):
                    continue
                uses = len(re.findall(
                    r"(?<![\w.])" + re.escape(name) + r"\s*\(", project.source))
                uses += len(re.findall(r"\." + re.escape(name) + r"\b", project.source))
                # a tear-off passed as a callback counts as a use
                uses += len(re.findall(
                    r"(?<![\w.(])" + re.escape(name) + r"(?![\w(])", project.source))
                if uses <= 1:
                    yield self.finding(
                        Level.RISK,
                        f"{name}() is defined and never called",
                        f"{project.rel(path)}:{project.line_of(path, m.start())}",
                        "Either it is dead and can go, or something that was\n"
                        "meant to reach it never did - which is the more\n"
                        "interesting of the two.")


class EmptyHandler(Rule):
    name = "empty-handler"
    title = "A handler that is wired up and does nothing"
    born_from = """
    _letGoOfHand(Vector2 p) {} is registered as the release callback on two
    touch targets and has an empty body. It looks connected from every angle:
    the registration is there, the name says what it is for, and nothing in a
    review would catch it.
    """

    def run(self, project: Project):
        for path, text in project.dart.items():
            for m in re.finditer(
                    # a trailing comment on the same line means somebody has
                    # already said why it is empty - which is exactly what
                    # this rule's own advice asks for, so honour it
                    r"^\s{2}(?:void|bool)\s+(_?\w+)\s*\([^)]*\)\s*\{\s*\}"
                    r"(?![ 	]*//)", text, re.M):
                name = m.group(1)
                wired = len(re.findall(
                    r"[:(]\s*" + re.escape(name) + r"\b", project.source))
                if wired:
                    yield self.finding(
                        Level.WRONG,
                        f"{name}() has an empty body but is wired up "
                        f"{wired}x as a callback",
                        f"{project.rel(path)}:{project.line_of(path, m.start())}",
                        "Everything about this looks connected except what it\n"
                        "does. If it is deliberately a no-op, say so in a\n"
                        "comment so the next reader does not have to find out.")
