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

## Deploy on Cloudflare

QuickBite's Flutter Web frontend is deployed on Cloudflare Pages.

**Live website:** https://quickbite-web.pages.dev/

### Deploy the frontend

Run the following command from the repository root after building Flutter Web:

```bash
npx wrangler pages deploy frontend/build/web --project-name=quickbite-web --branch=main
```

If authentication is required, authenticate with your Cloudflare account. Ensure the `quickbite-web` Pages project exists and that `frontend/build/web` contains the latest production build.

### Build with the production API URL

Replace `YOUR_PUBLIC_API_URL` with the actual HTTPS URL of the reachable FastAPI backend.

```bash
cd frontend
flutter pub get
flutter build web --release --dart-define=API_BASE_URL=https://YOUR_PUBLIC_API_URL
```

Then return to the repository root and deploy:

```bash
cd ..
npx wrangler pages deploy frontend/build/web --project-name=quickbite-web --branch=main
```

### Backend and local services

Cloudflare Pages hosts the static Flutter Web frontend. The existing FastAPI backend, PostgreSQL database, RabbitMQ, and background workers must be running and reachable for API-dependent functionality.

Start the existing local services with:

```bash
docker compose up -d --build
docker compose ps
```

If using Cloudflare Tunnel to expose a backend running on your PC, keep the backend and tunnel running while using the website. Configure the production API URL and backend CORS using the actual HTTPS tunnel hostname and the frontend origin:

`https://quickbite-web.pages.dev`

Do not use a placeholder API URL in the production build. A temporary Cloudflare Quick Tunnel URL can change when the tunnel restarts.

### Verify deployment

1. Open https://quickbite-web.pages.dev/.
2. Confirm the latest frontend loads.
3. Test login, restaurant and menu loading, images, cart, checkout, and order history.
4. Check the browser Network tab for API errors.
5. Confirm the backend and required workers are healthy.

**Important:** Deploying the frontend does not automatically deploy the backend or start local services.
