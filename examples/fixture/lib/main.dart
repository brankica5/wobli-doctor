// A deliberately broken fixture: every fault here is one the real game shipped.
//
// It exists so the rules are tested against known-bad code on every push. If a
// rule stops finding its own fault, CI fails - which matters more than it
// sounds, because a check that silently stops working is worse than no check.
//
// This file does not run. It is not a game; it is twelve bugs in Dart shaped
// like one.

/// A sound the project has crossed off and must never play.
const Set<String> _cut = {'wob_giggle', 'clap'};

/// FAULT: shown in the parent panel, while pubspec.yaml says 1.0.0+4.
const String kAppVersion = '1.0.0 (2)';

/// FAULT: const flag whose false branch holds whole features.
const bool kE2Bare = true;

/// FAULT: nothing reads this at all.
const bool kOldStudio = false;

class SlimeGame {
  int _touchPointer = -1;

  /// FAULT (tap-gated-on-drag): registered for taps as well, and a tap
  /// dispatches with no pointer, so this returns before doing anything.
  bool _pickFlower(Object f, Object p) {
    if (_touchPointer < 0) return false;
    return true;
  }

  /// NOT a fault: the same guard, but it hands off to the tap path. The rule
  /// has to tell these two apart.
  bool _pickBerry(Object f, Object p) {
    if (_touchPointer < 0) return _armBerry(f, p);
    return true;
  }

  bool _armBerry(Object f, Object p) => true;

  /// FAULT (read-never-written): chooses the second routine, and nothing has
  /// assigned it since the screen that did was deleted.
  int _songIndex = 0;

  void dance() {
    final wild = _songIndex == 1;
    if (wild) _wildRoutine();
    if (_songIndex > 0) _encore();
    if (_songIndex != 2) _plainRoutine();
  }

  void _wildRoutine() {}
  void _encore() {}
  void _plainRoutine() {}

  /// FAULT (empty-handler): wired up as a release callback, does nothing.
  void _letGoOfHand(Object p) {}

  void register() {
    addTarget(release: _letGoOfHand);
    addTarget(release: _letGoOfHand);
  }

  void addTarget({Object? release}) {}

  /// FAULT (defined-never-called): the parent's way to wake him, reachable
  /// from nowhere.
  void parentWake() {}

  /// FAULT (missing-clip): the file is hiccup.wav.
  void hiccup() {
    sound.sfx('hiccup_el');
  }

  /// FAULT (swallowed-by-cuts): on the cut list, called directly, silent.
  void laugh() {
    sound.sfx('wob_giggle');
  }

  /// NOT a fault: a group picker filters the cut list before choosing.
  void laughProperly() {
    sound.voiceAny('giggle', const ['wob_giggle', 'pk_giggle_1']);
  }

  /// NOT a fault (unreachable-clip): the name is built at runtime, so
  /// note_1..note_7 are all reachable even though no literal names them.
  void sing(int n) {
    sound.sfx('note_${(n - 1) % 7 + 1}');
  }

  /// FAULT (overlay-by-name): 'kitchen' is not in the builder map.
  void showKitchen() {
    overlays.add('kitchen');
  }

  /// FAULT (stale-comment): [_oldMixer] has not existed for two releases.
  /// See [_oldMixer] for how the colours used to combine.
  void mix() {}

  final overlays = _Overlays();
  final sound = _Sound();
}

class _Overlays {
  void add(String name) {}
}

class _Sound {
  void sfx(String name) {}
  void voiceAny(String key, List<String> names) {}
}

final registry = {
  'settings': (ctx, SlimeGame game) => 'SettingsOverlay',
};
