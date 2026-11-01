# wobli-doctor

A daily check for a Flutter/Flame game that finds **the code which compiles,
passes the analyser, and still does nothing.**

Every rule in it comes from a bug that shipped in a real children's app and was
found by a child playing it — never by a tool, never by a code review. The tool
exists because that kept happening.

```
$ wobli-doctor ../woblero

wobli-doctor  ../woblero  2026-11-01 22:29
19 dart files, 897 audio files, 12 rules

--- BROKEN (1) ----------------------------------------
[BROKEN ] 'clap' is on the cut list but called directly at 1 place(s)
          lib/main.dart:8249
          The cut check returns early, so these produce no sound at
          all. Route them through a group picker, which filters the
          cut list before choosing and so falls back to a clip that
          was kept.

broken: 1  wrong: 0  risk: 0  note: 0
```

That finding is real. It was found on the first run, fixed, and the tool then
reported clean.

---

## The problem it solves

A static analyser answers *"is this valid Dart?"*. A test answers *"does this
function return what I said it would?"*. Neither answers the question that
actually matters in a game for three-year-olds:

> **When the child does this, does anything happen?**

In one evening of playtesting, nine separate faults were found in a published
game. Every one of them compiled. Every one passed `flutter analyze` with no
warnings. Not one would have been caught by a unit test, because nothing was
wrong with any individual function — what was wrong was the *connection between
two files*, or a flag, or a name in a string.

| What was wrong | Why no tool saw it |
| --- | --- |
| A tap handler that returned before doing anything | Valid Dart. The guard was correct for drags. |
| Eight laughs that played nothing | The clip was on a "do not play" list; the call site did not know |
| A hiccup sound that had never once played | `sfx('hiccup_el')`, file named `hiccup.wav` — it is a string |
| The "wild" dance that never happened | A field read in three places, set by a screen that had been deleted |
| Half the squeeze sounds measurably harsh | They were bought, so nobody measured them |
| A breathing exercise interrupting a child's fun | Working exactly as written, and wrong anyway |
| The version in the parent panel | Hardcoded, two releases stale |

`wobli-doctor` is twelve rules, one per fault class, each carrying the story of
the bug that produced it.

---

## Install and run

Python 3.10+. Only the audio rule needs third-party packages.

```bash
git clone https://github.com/brankica5/wobli-doctor
cd wobli-doctor
pip install -r requirements.txt       # numpy + soundfile, for measuring audio

python -m wobli_doctor.cli /path/to/your/flutter/project
```

Useful flags:

```bash
--why                     print the real bug behind every rule, and exit
--only missing-clip       run one rule (repeatable)
--skip harsh-sound        skip one (repeatable)
--json report.json        machine-readable output as well
--fail-on wrong           exit non-zero at this level or worse
```

`--fail-on` is what makes it usable in CI: `broken` by default, so a build fails
only when something a child does gets no response at all.

---

## How it works

Three pieces, and that is the whole design.

### 1. `Project` — read the code once

```python
project = Project("../woblero")
project.dart        # {path: source} for every .dart file under lib/
project.source      # all of it concatenated, for cross-file questions
project.audio_files()
```

Rules get the whole project as one string as well as per-file, because **the
bugs this tool looks for are a mismatch *between* two files** — a sound named in
Dart with no file in `assets/`, a flag in one file gating behaviour in another.
A per-file linter structurally cannot see them.

### 2. `Rule` — one check, with its reason attached

```python
class MissingClip(Rule):
    name = "missing-clip"
    title = "A sound is asked for by name and the file is not there"
    born_from = """
    hiccup_el was called at three places. The file is hiccup.wav. The hiccup
    had never once played, and nothing anywhere said so.
    """

    def run(self, project):
        ...
        yield self.finding(Level.BROKEN, "...", where, detail)
```

`born_from` is not decoration. **A check whose reason you cannot state is a
check nobody will keep** — the first time it is noisy, someone deletes it. Run
`--why` and the tool tells you why every one of its own rules exists.

### 3. `Finding` — severity by what a child experiences

| Level | Means |
| --- | --- |
| `BROKEN` | The child does something and gets no response at all |
| `WRONG` | There is a response, and it is the wrong one |
| `RISK` | Fine today; will break the next time someone changes this |
| `NOTE` | Worth knowing, nothing is wrong |

Deliberately **not** error/warning/info. Those grade how upset the compiler is.
This grades how the game feels to a four-year-old, which is the only measure
that matters here.

---

## The rules

Run `wobli-doctor --why` for the full story of each.

**Sound**
- `missing-clip` — a sound played by a name with no file behind it
- `swallowed-by-cuts` — a clip on the project's "do not play" list, still called
  directly, so it produces silence
- `harsh-sound` — measures every file: energy above 5 kHz, crest factor, attack
  time. Catches harshness in bought recordings nobody thought to check
- `unreachable-clip` — files no code names. **Reports, never recommends
  deleting** — see below

**Reachability**
- `tap-gated-on-drag` — a handler that bails out unless a drag is in flight,
  registered for taps as well
- `overlay-by-name` — a screen added by a string name nothing registers
- `read-never-written` — a field that gates behaviour and nothing ever sets
- `empty-handler` — a callback that is wired up and has an empty body
- `defined-never-called` — a method nobody reaches

**Drift**
- `version-drift` — the version shown in the app against `pubspec.yaml`
- `stale-comment` — a comment naming an identifier that no longer exists
- `flag-silences-behaviour` — a `const bool` whose other branch is unreachable

---

## Two mistakes this tool is built around

Both are mine, both happened while building it, and both are the reason parts of
it look the way they do.

### It once told someone to delete their music

An earlier version matched **literal strings only**. Woblero builds clip names
at the moment of use — `sfx('note_${(n - 1) % 7 + 1}')` — so it reported
`note_1` through `note_7` as unreachable. Those are the pentatonic scale the
game plays constantly. They were deleted. The song stopped.

So `unreachable-clip` understands interpolation and treats an interpolated name
as a **prefix family**, counting every file under it as reachable. It still
cannot see a name assembled from a variable, which is exactly why **it is the
one rule that only ever reports and never recommends an action.**

A tool that is confidently wrong about deletion is worse than no tool.

### Its first run cried wolf

The first version of `tap-gated-on-drag` matched any `return` after the guard
and flagged this:

```dart
bool _pickFlower(WorldFlower f, Vector2 p) {
  if (_touchPointer < 0) return _armFlower(f, p);   // <- not a bug
```

That returns the *tap* path, which does the work. The rule now requires a bare
`return;` / `return false;` — it has to see that **nothing happens**, not merely
that the function leaves.

One false positive in the first ten minutes is a useful reminder: the cost of a
noisy rule is paid every single day, by someone learning to ignore it.

---

## Measuring sound

`harsh-sound` reports four numbers, each with a reason:

| Measure | Limit | Why |
| --- | --- | --- |
| Energy above 5 kHz | 35% | Above that a sound stops being a texture and turns thin |
| Crest (peak ÷ RMS) | 9 | Higher is a spike an ear flinches at, not leans into |
| Attack to 80% | ≥ 5 ms | Faster is heard as a click however warm the rest is |
| Unevenness | *reported only* | High = alive and granular; low = a smooth wash. Neither is better |

That last distinction was learned the hard way. Unevenness was the measure that
mattered for a wet *separation* sound. It was then applied by reflex to a silky
*friction* sound, where smooth is correct. **A metric that was right once is not
right everywhere**, and a tool that enforces one everywhere teaches bad habits.

There is also `audio.loop_seam()`, which measures the discontinuity where a loop
joins itself — written after a first attempt compared the *mean level* of the
first and last 20 ms, reported 3–6%, and nearly caused a perfectly seamless loop
to be "fixed". The real jump at the join was zero. It measured loudness
variation, not discontinuity.

---

## Running it daily

A scheduled task on the machine the game is developed on:

```bash
python -m wobli_doctor.cli ~/woblero --json ~/reports/$(date +%F).json
```

The repository's own CI runs the tool against the fixture in `examples/` on
every push, so the rules are checked against known-bad code.

---

## Licence

MIT. See `LICENSE`.
