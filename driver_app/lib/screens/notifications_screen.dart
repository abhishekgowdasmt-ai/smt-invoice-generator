import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../state/driver_controller.dart';
import '../widgets/empty_state.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriverController>().refreshNotifications();
    });
  }

  @override
  Widget build(BuildContext context) {
    final driver = context.watch<DriverController>();
    return RefreshIndicator(
      onRefresh: () => driver.refreshNotifications(),
      child: driver.notifications.isEmpty
          ? ListView(
              children: [
                SizedBox(
                  height: MediaQuery.of(context).size.height * 0.6,
                  child: EmptyState(
                    title: 'No notifications',
                    subtitle: 'New assignments and releases appear here.',
                    onRetry: () => driver.refreshNotifications(),
                  ),
                ),
              ],
            )
          : ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: driver.notifications.length,
              separatorBuilder: (context, index) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final note = driver.notifications[index];
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    note.title,
                    style: TextStyle(
                      fontWeight: note.isUnread ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                  subtitle: Text(note.body),
                  trailing: note.isUnread
                      ? const Icon(Icons.circle, size: 10, color: Color(0xFF2D6A4F))
                      : null,
                  onTap: () => driver.markRead(note.id),
                );
              },
            ),
    );
  }
}
