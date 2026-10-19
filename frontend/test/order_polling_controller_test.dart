import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/screens/order_polling_controller.dart';

Future<void> _waitUntil(bool Function() condition) async {
  for (var i = 0; i < 100 && !condition(); i++) {
    await Future<void>.delayed(const Duration(milliseconds: 2));
  }
  expect(condition(), isTrue, reason: 'condition did not become true');
}

void main() {
  test('polls until a terminal order state is observed', () async {
    var calls = 0;
    var terminal = false;
    final controller = OrderPollingController(
      interval: const Duration(milliseconds: 1),
      fetch: () async {
        calls++;
        terminal = calls == 2;
        return true;
      },
      isTerminal: () => terminal,
    );

    controller.start();
    await _waitUntil(() => !controller.isActive);
    expect(calls, 2);
    controller.dispose();
  });

  test('pauses in background and refreshes immediately on resume', () async {
    var calls = 0;
    final controller = OrderPollingController(
      interval: const Duration(milliseconds: 30),
      fetch: () async {
        calls++;
        return true;
      },
      isTerminal: () => false,
    );

    controller.start();
    await _waitUntil(() => calls == 1);
    controller.pause();
    await Future<void>.delayed(const Duration(milliseconds: 5));
    expect(calls, 1);

    controller.resume();
    await _waitUntil(() => calls == 2);
    controller.dispose();
  });

  test('backs off after failures and resets after success', () async {
    var calls = 0;
    final controller = OrderPollingController(
      interval: const Duration(milliseconds: 10),
      maxBackoff: const Duration(milliseconds: 25),
      fetch: () async {
        calls++;
        return calls >= 3;
      },
      isTerminal: () => false,
    );

    controller.start();
    await _waitUntil(() => controller.failureCount == 1);
    expect(controller.nextDelay, const Duration(milliseconds: 10));
    await _waitUntil(() => controller.failureCount == 2);
    expect(controller.nextDelay, const Duration(milliseconds: 20));
    await _waitUntil(() => calls >= 3 && controller.failureCount == 0);
    expect(controller.nextDelay, const Duration(milliseconds: 10));
    controller.dispose();
  });

  test('does not overlap requests and performs a deferred resume refresh', () async {
    final gate = Completer<bool>();
    var calls = 0;
    final controller = OrderPollingController(
      interval: const Duration(seconds: 1),
      fetch: () {
        calls++;
        return calls == 1 ? gate.future : Future.value(true);
      },
      isTerminal: () => false,
    );

    controller.start();
    await _waitUntil(() => controller.isInFlight);
    controller.pause();
    controller.resume();
    gate.complete(true);
    await _waitUntil(() => calls == 2);
    expect(calls, 2);
    controller.dispose();
  });

  test('dispose cancels future polling', () async {
    var calls = 0;
    final controller = OrderPollingController(
      interval: const Duration(milliseconds: 100),
      fetch: () async {
        calls++;
        return true;
      },
      isTerminal: () => false,
    );
    controller.start();
    await _waitUntil(() => calls == 1);
    controller.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 110));
    expect(calls, 1);
  });
}
