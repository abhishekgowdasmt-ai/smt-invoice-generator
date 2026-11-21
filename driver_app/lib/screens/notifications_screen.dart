import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../models/driver_profile.dart';
import '../state/driver_controller.dart';
import '../widgets/empty_state.dart';
import 'duty_detail_screen.dart';

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

  String _formatTimestamp(String? raw) {
    if (raw == null || raw.isEmpty) return '';
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return raw;
    final local = parsed.toLocal();
    final y = local.year.toString().padLeft(4, '0');
    final m = local.month.toString().padLeft(2, '0');
    final d = local.day.toString().padLeft(2, '0');
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '$y-$m-$d $hh:$mm';
  }

  Future<void> _openNotification(AppNotification note) async {
    final driver = context.read<DriverController>();
    if (note.isUnread) {
      await driver.markRead(note.id);
    }
    final assignmentId = note.assignmentId;
    if (assignmentId == null || assignmentId.isEmpty) {
      return;
    }
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DutyDetailScreen(assignmentId: assignmentId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final driver = context.watch<DriverController>();
    if (driver.errorMessage != null && driver.notifications.isEmpty) {
      return RefreshIndicator(
        onRefresh: () => driver.refreshNotifications(),
        child: ListView(
          children: [
            SizedBox(
              height: MediaQuery.of(context).size.height * 0.6,
              child: EmptyState(
                title: 'Could not load alerts',
                subtitle: driver.errorMessage!,
                onRetry: () => driver.refreshNotifications(),
              ),
            ),
          ],
        ),
      );
    }
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
                final stamp = _formatTimestamp(note.createdAt);
                final hasDuty = (note.assignmentId ?? '').isNotEmpty;
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    note.title,
                    style: TextStyle(
                      fontWeight: note.isUnread ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(note.body),
                      if (stamp.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            stamp,
                            style: TextStyle(
                              color: Theme.of(context).hintColor,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      if (hasDuty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(
                            'Open linked duty',
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.primary,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                    ],
                  ),
                  isThreeLine: true,
                  trailing: note.isUnread
                      ? const Icon(Icons.circle, size: 10, color: Color(0xFF2D6A4F))
                      : null,
                  onTap: () => _openNotification(note),
                );
              },
            ),
    );
  }
}
