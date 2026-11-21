import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../state/auth_controller.dart';
import '../state/driver_controller.dart';
import '../widgets/duty_card.dart';
import '../widgets/empty_state.dart';
import '../widgets/status_chip.dart';
import 'duty_detail_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriverController>().refreshDashboard();
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final driver = context.watch<DriverController>();
    final profile = driver.dashboardDriver ?? auth.profile;

    return RefreshIndicator(
      onRefresh: () => driver.refreshDashboard(),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (profile != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 28,
                      backgroundColor: const Color(0xFF1B4332),
                      child: Text(
                        profile.displayName.isNotEmpty
                            ? profile.displayName.substring(0, 1).toUpperCase()
                            : 'D',
                        style: const TextStyle(color: Colors.white, fontSize: 22),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            profile.displayName,
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              StatusChip(
                                profile.verificationStatus,
                                status: profile.verificationStatus,
                              ),
                              StatusChip(
                                profile.active ? 'active' : 'inactive',
                                status: profile.active ? 'active' : 'disabled',
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          if (driver.errorMessage != null) ...[
            const SizedBox(height: 12),
            Text(driver.errorMessage!, style: const TextStyle(color: Color(0xFF9B2226))),
          ],
          if (driver.activeTrip != null) ...[
            const SizedBox(height: 16),
            const Text('Active trip', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
            const SizedBox(height: 8),
            DutyCard(
              duty: driver.activeTrip!,
              onTap: () => _open(driver.activeTrip!.assignmentId),
            ),
          ],
          const SizedBox(height: 8),
          const Text("Today's duties", style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 8),
          if (driver.loading && driver.todayDuties.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (driver.todayDuties.isEmpty)
            const EmptyState(title: 'No duties for today')
          else
            ...driver.todayDuties.map(
              (duty) => DutyCard(duty: duty, onTap: () => _open(duty.assignmentId)),
            ),
          const SizedBox(height: 8),
          const Text('Pending responses', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 8),
          if (driver.pendingDuties.isEmpty)
            const Text('None pending', style: TextStyle(color: Color(0xFF5C6670)))
          else
            ...driver.pendingDuties.map(
              (duty) => DutyCard(duty: duty, onTap: () => _open(duty.assignmentId)),
            ),
          const SizedBox(height: 16),
          const Text('Upcoming', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 8),
          if (driver.upcomingDuties.isEmpty)
            const Text('No upcoming duties', style: TextStyle(color: Color(0xFF5C6670)))
          else
            ...driver.upcomingDuties.take(5).map(
                  (duty) => DutyCard(duty: duty, onTap: () => _open(duty.assignmentId)),
                ),
          const SizedBox(height: 16),
          const Text('Recent notifications', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 8),
          if (driver.notifications.isEmpty)
            const Text('No notifications yet', style: TextStyle(color: Color(0xFF5C6670)))
          else
            ...driver.notifications.take(5).map(
                  (note) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(note.title),
                    subtitle: Text(note.body),
                    dense: true,
                  ),
                ),
        ],
      ),
    );
  }

  void _open(String assignmentId) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => DutyDetailScreen(assignmentId: assignmentId)),
    );
  }
}
