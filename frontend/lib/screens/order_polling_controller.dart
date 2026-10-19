import 'dart:async';

/// Single-flight polling with lifecycle pause, immediate resume refresh, and
/// bounded backoff after transient request failures.
class OrderPollingController {
  OrderPollingController({
    required this.fetch,
    required this.isTerminal,
    this.interval = const Duration(seconds: 2),
    this.maxBackoff = const Duration(seconds: 30),
  });

  final Future<bool> Function() fetch;
  final bool Function() isTerminal;
  final Duration interval;
  final Duration maxBackoff;
  Timer? _timer;
  bool _active = false;
  bool _disposed = false;
  bool _inFlight = false;
  bool _refreshOnResume = false;
  int _failures = 0;

  bool get isActive => _active;
  bool get isInFlight => _inFlight;
  int get failureCount => _failures;

  Duration get nextDelay {
    if (_failures == 0) return interval;
    final multiplier = 1 << (_failures - 1).clamp(0, 30).toInt();
    final milliseconds = interval.inMilliseconds * multiplier;
    return Duration(
      milliseconds: milliseconds.clamp(0, maxBackoff.inMilliseconds).toInt(),
    );
  }

  void start() {
    if (_disposed || _active) return;
    _active = true;
    _run();
  }

  void pause() {
    _active = false;
    _timer?.cancel();
    _timer = null;
  }

  void resume() {
    if (_disposed || isTerminal()) return;
    _active = true;
    _refreshOnResume = true;
    _timer?.cancel();
    _timer = null;
    _run();
  }

  void dispose() {
    _disposed = true;
    pause();
  }

  Future<void> _run() async {
    if (!_active || _disposed || _inFlight) return;
    if (isTerminal()) {
      pause();
      return;
    }
    _inFlight = true;
    _refreshOnResume = false;
    try {
      final succeeded = await fetch();
      _failures = succeeded ? 0 : _failures + 1;
    } catch (_) {
      _failures++;
    } finally {
      _inFlight = false;
    }
    if (!_active || _disposed || isTerminal()) {
      if (isTerminal()) pause();
      return;
    }
    _timer?.cancel();
    _timer = Timer(_refreshOnResume ? Duration.zero : nextDelay, _run);
  }
}
