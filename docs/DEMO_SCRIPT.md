# Reproducible QuickBite Demo Procedure

Use an isolated development environment. This is a procedure, not evidence that a demo was run in the current session.

1. Follow the clean setup in the root README. Start PostgreSQL/RabbitMQ and run migrations and seed once. Start the Compose services and wait for API readiness.
2. Open the Web app and sign in with the fictional local customer account shown in README. Browse restaurants/menu, add an item, edit quantity, and enter a valid address.
3. Submit checkout and capture the 202 acknowledgement/order ID. Confirm current state through order detail and history; observe persisted notifications.
4. To demonstrate safe retry, simulate a lost response in an isolated test environment. Retry the saved checkout and verify the same key/payload produces the same order ID. Do not create a new key for an ambiguous outcome.
5. Stop the notification worker, place an order, verify the order proceeds independently, restart the worker, then verify notifications drain.
6. Use deterministic test-only worker modes for fail-twice/success and always-fail. Verify retry count/delay, terminal UI, and quarantine state.
7. Exercise worker crash and broker-outage recovery tests only with `QUICKBITE_TEST_ENV=1` and the isolated Compose project configured in README.
8. For scaling evidence, run at least two identical 100-order trials with one payment worker and two with three workers. Preserve every unique report; compare machine, stage delays, backlog, p50/p95, throughput, and completion.
9. Sign in as admin to inspect cross-customer orders; verify customer access is denied.
10. Repeat the customer flow in a narrow browser, Android emulator/device, and iOS simulator. Record screenshots or video only from actual runs. iOS needs macOS/Xcode.

No screenshot, runtime, recovery, or new load result was produced during this audit.
