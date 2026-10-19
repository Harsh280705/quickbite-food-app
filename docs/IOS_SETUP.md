# iOS Setup — QuickBite

## Status
Native iOS compilation and simulator validation are BLOCKED on the current Windows development machine because Xcode and the iOS Simulator require macOS.

This document provides the exact steps to complete iOS validation on a Mac or authorized hosted macOS runner.

## Prerequisites (macOS)
- macOS with Xcode (latest stable)
- Flutter 3.41.7 / Dart 3.11.5
- CocoaPods (`sudo gem install cocoapods`)
- A valid Apple Developer account for device signing (not needed for simulator)

## Steps
1. Clone/copy the QuickBite project to the Mac.
2. `cd frontend`
3. `flutter doctor -v` — ensure Xcode and CocoaPods are recognized.
4. `flutter pub get`
5. `cd ios && pod install` (if Podfile exists; this project currently uses Swift Package Manager via Flutter)
6. `flutter analyze`
7. `flutter test`
8. `flutter devices` — note an iPhone simulator ID.
9. `flutter build ios --simulator --debug`
10. `flutter run -d <IOS_SIMULATOR_DEVICE_ID>`
11. Configure backend URL for the simulator. Use `--dart-define=API_BASE_URL=http://127.0.0.1:8000` only when FastAPI runs on the same Mac; otherwise use the reachable LAN IP of the backend host or HTTPS.
12. Ensure the FastAPI backend is reachable from the Mac and Docker Desktop provides PostgreSQL/RabbitMQ.

## API networking on iOS Simulator
The simulator shares the Mac host network, so `http://127.0.0.1:8000` reaches a backend running on that Mac. For a backend on another machine, use that machine's reachable LAN address. NSAllowsLocalNetworking is enabled in the Debug Info.plist for local HTTP development only; release environments must use HTTPS.

## Signing / release
- Open `ios/Runner.xcworkspace` in Xcode for signing configuration.
- Set bundle identifier and team in Xcode.
- Archive via Xcode or `flutter build ipa`.

## Common issues
- CocoaPods version mismatch: run `pod repo update`.
- Deployment target errors: update `IPHONEOS_DEPLOYMENT_TARGET` in Xcode build settings.
- ATS blocking HTTP: NSAllowsLocalNetworking already enabled; for non-local dev use HTTPS.
- Simulator not listed: `xcrun simctl list devices`.

## Commands actually executed on Windows
- `flutter doctor -v` (no iOS/Xcode toolchain detected → BLOCKED)
- `flutter analyze`, `flutter test`, `flutter build web`, `flutter build apk --debug` (PASS)
- `flutter build ios --simulator --debug` NOT RUN (no macOS/Xcode)
