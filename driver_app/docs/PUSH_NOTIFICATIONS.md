# Optional push notifications

In-app notifications from `GET /api/driver/notifications` are the supported
path. Firebase Cloud Messaging (or another provider) is optional.

## Required if enabling FCM later

1. Create a Firebase project for Shree Maruthi Travels.
2. Register an Android app with package `com.shreemaruthitravels.driver_app`.
3. Download `google-services.json` into `android/app/` (do not commit secrets
   that are not meant for the client; follow Firebase client guidelines).
4. Add FlutterFire / `firebase_messaging` dependencies compatible with Flutter
   3.50 / Dart 3.14.
5. Store server keys only on the Flask host; never embed bridge or WhatsApp
   secrets in the APK.

Until that is configured, the app polls authenticated APIs and shows in-app
notification rows created by the PostgreSQL assignment trigger.
