import 'package:driver_app/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('API base URL is configured via dart-define default', () {
    expect(AppConfig.apiBaseUrl, isNotEmpty);
    expect(AppConfig.appName, contains('Maruthi'));
  });
}
