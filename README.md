# QuickBite

QuickBite is a full-stack food ordering application with a Flutter web/mobile frontend, FastAPI backend, PostgreSQL, RabbitMQ workers, and Docker Compose for local development. It supports restaurant browsing, menus, cart, checkout, order tracking, notifications, and admin management.

## Technology stack

- Flutter / Dart (web, Android and iOS)
- FastAPI / Python
- PostgreSQL
- RabbitMQ
- Docker Compose
- Nginx (frontend container)

## Project structure

```text
.
├── backend/          # FastAPI app, workers, migrations, tests
├── frontend/         # Flutter app
│   ├── android/      # Android project
│   ├── ios/          # iOS project (build on macOS with Xcode)
│   ├── lib/          # Dart source
│   ├── test/         # Flutter tests
│   └── web/          # Web entry point and assets
├── compose.yaml      # Local full-stack Docker Compose
├── infra/            # Nginx and deployment support files
└── scripts/          # Helper scripts
```

## Prerequisites

- Docker and Docker Compose
- Flutter SDK 3.41.x
- Python 3.11+
- Git

## Environment configuration

Copy the example files and adjust values:

```bash
cp .env.example .env
```

For Android device testing, set `API_BASE_URL` at build time instead of committing it.

## Run with Docker

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
docker compose down
```

The web app is available on port `8080` by default; the API on `8000`.

## Run the backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Run the website

```bash
cd frontend
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
flutter build web --release --dart-define=API_BASE_URL=https://YOUR-PUBLIC-API-DOMAIN
```

Build output: `frontend/build/web`.

## Run the Android app

```bash
cd frontend
flutter devices
flutter run -d <device-id> --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Use `http://10.0.2.2:8000` for an emulator, or `http://<PC_LAN_IPV4>:8000` for a physical phone.

## Run the iOS app

iOS builds require macOS with Xcode and CocoaPods. From the frontend directory:

```bash
cd frontend
flutter pub get
cd ios
pod install
cd ..
flutter run -d <ios-device-or-simulator> --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

The iOS project is located at `frontend/ios/`. Do not build iOS on Windows.

## Cloudflare Pages

Cloudflare Pages hosts only the compiled static Flutter Web output (`frontend/build/web`). The FastAPI backend and supporting services must be hosted separately. Configure `PRODUCTION_API_BASE_URL`, `CLOUDFLARE_API_TOKEN`, and `CLOUDFLARE_ACCOUNT_ID` as GitHub Actions secrets.