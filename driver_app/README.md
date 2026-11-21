# Shree Maruthi Travels — Driver App

Flutter Android application for authorized drivers. Talks to the existing Flask
+ PostgreSQL backend (`/api/driver/*`). Does not invent a separate operational
database.

## Requirements

| Tool | Version used in development |
|------|-----------------------------|
| Flutter SDK | 3.50.0 (stable) |
| Dart SDK | 3.14.0 |
| Android | API 24+ (minSdk from Flutter template) |

## Configuration

Pass the API base URL at build/run time (never commit secrets):

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:5000
```

| Environment | Suggested `API_BASE_URL` |
|-------------|--------------------------|
| Android emulator → host Flask | `http://10.0.2.2:5000` |
| Physical device on LAN | `http://<host-lan-ip>:5000` |
| Widget/unit tests | `http://127.0.0.1:5000` |

Backend must set `DRIVER_TOKEN` (≥32 chars) or allow local fallback to
`STAFF_TOKEN` with a different signing salt. Apply `dev-db/010_driver_app.sql`
to a disposable `*_test` database before driver API tests.

## Architecture

```
lib/
  main.dart
  config/app_config.dart
  theme/app_theme.dart
  models/
  services/          # HTTP + secure token storage
  state/             # Provider controllers
  routing/
  screens/
  widgets/
```

## Auth

Drivers log in with phone + password. Accounts are provisioned by an owner via
`POST /api/drivers/<id>/login-account`. Session tokens are stored in
`flutter_secure_storage`. Password reset is not offered (no backend flow).

## Push notifications

Optional Firebase Cloud Messaging is **not** wired with credentials. The app
works with authenticated API refresh and in-app notifications from
`driver_notifications`. See `docs/PUSH_NOTIFICATIONS.md`.

## Build

```bash
flutter pub get
flutter test
flutter build apk --dart-define=API_BASE_URL=https://your-api.example
```

If `ANDROID_HOME` / Android SDK platform-tools are missing, `flutter build apk`
will fail — report the exact SDK gap rather than claiming a successful APK.
