import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import 'config/app_config.dart';
import 'routing/app_router.dart';
import 'services/api_client.dart';
import 'services/auth_storage.dart';
import 'services/driver_api.dart';
import 'state/auth_controller.dart';
import 'state/driver_controller.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final apiClient = ApiClient();
  final storage = AuthStorage();
  final driverApi = DriverApi(apiClient);
  final auth = AuthController(apiClient: apiClient, storage: storage, driverApi: driverApi);
  final driver = DriverController(driverApi);
  await auth.restoreSession();
  runApp(DriverApp(auth: auth, driver: driver));
}

class DriverApp extends StatelessWidget {
  const DriverApp({super.key, required this.auth, required this.driver});

  final AuthController auth;
  final DriverController driver;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: auth),
        ChangeNotifierProvider.value(value: driver),
      ],
      child: MaterialApp(
        title: '${AppConfig.appName} Driver',
        theme: AppTheme.light(),
        home: const AppRoot(),
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}
