# Testing and verification

## Safety

Backend API and recovery tests create accounts/orders and manipulate workers or RabbitMQ. They skip unless `QUICKBITE_TEST_ENV=1`; set that only after starting the isolated `quickbite-test` Compose project described in the root README. These tests use ports 8001/55433/5673, a separate Compose network, and separate named volumes. They must not target `quickbite-local` or a non-test database.

## Checks run for this change

- `python -m pytest backend/tests/test_password_hashing.py -v`: the hash round-trip, legacy-hash and malformed-hash cases passed after correcting a Passlib parsing mismatch. The complete file did not finish within the available execution window, so successful-login migration coverage remains unverified here.
- `docker compose --env-file .env.test.example config --quiet`: passed.
- `python -m compileall -q backend/app backend/tests scripts`: passed.
- Flutter format/analyze/widget tests were not verified in this session; Flutter formatting did not return output within 60 seconds and was stopped.
- Docker services, API/recovery tests, migrations, web/Android builds, and runtime flows were not run. Docker Desktop engine access is unavailable in this environment. Native iOS build and simulator require macOS/Xcode.

Do not interpret the checks above as a full assignment pass.

## Safe local checks

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pytest tests/test_password_hashing.py -v -p no:cacheprovider
Pop-Location
Push-Location frontend
flutter analyze
flutter test
flutter build web
flutter build apk --debug
Pop-Location
```

## Isolated API and recovery suite

Follow the isolated-stack setup in the root README, including exporting the `QUICKBITE_TEST_*` variables before invoking `pytest`. These tests are intentionally destructive only to their own isolated test data. Keep the test Compose project separate and stop it without `down -v` when preserving results.

## Asset manifest integrity

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -c "import json;from pathlib import Path;from PIL import Image; m=json.loads(Path('data/image_manifest.json').read_text()); fs=[Path('static/images')/x['file'] for x in list(m['restaurants'].values())+list(m['menu_items'].values())]; print('files',len(fs),'missing',sum(not f.exists() for f in fs))"
Pop-Location
```
