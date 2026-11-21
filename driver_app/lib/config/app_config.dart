class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:5000',
  );

  static const String appName = 'Shree Maruthi Travels';
  static const String appSubtitle = 'Driver';
}
