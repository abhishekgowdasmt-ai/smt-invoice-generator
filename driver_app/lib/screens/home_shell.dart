import 'package:material_ui/material_ui.dart';

import '../config/app_config.dart';
import 'dashboard_screen.dart';
import 'duties_screen.dart';
import 'notifications_screen.dart';
import 'payouts_screen.dart';
import 'profile_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;

  static const titles = ['Dashboard', 'Duties', 'Alerts', 'Payouts', 'Profile'];

  @override
  Widget build(BuildContext context) {
    final pages = const [
      DashboardScreen(),
      DutiesScreen(),
      NotificationsScreen(),
      PayoutsScreen(),
      ProfileScreen(),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(AppConfig.appName, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            Text(titles[index], style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: index,
        onTap: (value) => setState(() => index = value),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.assignment_outlined), label: 'Duties'),
          BottomNavigationBarItem(icon: Icon(Icons.notifications_outlined), label: 'Alerts'),
          BottomNavigationBarItem(icon: Icon(Icons.payments_outlined), label: 'Payouts'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), label: 'Profile'),
        ],
      ),
    );
  }
}
