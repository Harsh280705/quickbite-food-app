# QuickBite Flutter client

The Compose web build uses same-origin `/api` and `/static` paths through Nginx.
Android emulators use `http://10.0.2.2:8000` by default. A physical Android
phone must use `API_BASE_URL=http://<Windows-PC-LAN-IPv4>:8000`; the emulator
alias and `localhost` both point to the phone itself on a physical device. An
iOS simulator uses `http://127.0.0.1:8000` only when FastAPI runs on the same
Mac. If the backend is on another host, configure that host's reachable LAN URL.
The app resolves restaurant and menu image URLs against the same API base URL as
catalog requests.

For a deployed mobile build, provide the HTTPS API URL at build time:

```sh
flutter build apk --dart-define=API_BASE_URL=https://api.example.com
flutter build ios --dart-define=API_BASE_URL=https://api.example.com
```
