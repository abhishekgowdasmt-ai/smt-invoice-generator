import 'package:driver_app/screens/login_screen.dart';
import 'package:driver_app/services/api_client.dart';
import 'package:driver_app/services/auth_storage.dart';
import 'package:driver_app/state/auth_controller.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _MemoryStorage extends AuthStorage {
  String? token;

  @override
  Future<void> saveToken(String value) async => token = value;

  @override
  Future<String?> readToken() async => token;

  @override
  Future<void> clear() async => token = null;
}

void main() {
  testWidgets('login screen validates phone and password', (tester) async {
    final auth = AuthController(
      apiClient: ApiClient(baseUrl: 'http://127.0.0.1:5000'),
      storage: _MemoryStorage(),
    );
    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: auth,
        child: const MaterialApp(home: LoginScreen()),
      ),
    );
    await tester.tap(find.text('Sign in'));
    await tester.pump();
    expect(find.textContaining('valid 10-digit'), findsOneWidget);
  });
}
