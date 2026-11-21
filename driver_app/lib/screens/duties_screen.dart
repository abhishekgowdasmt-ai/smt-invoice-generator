import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../state/driver_controller.dart';
import '../widgets/duty_card.dart';
import '../widgets/empty_state.dart';
import 'duty_detail_screen.dart';

class DutiesScreen extends StatefulWidget {
  const DutiesScreen({super.key});

  @override
  State<DutiesScreen> createState() => _DutiesScreenState();
}

class _DutiesScreenState extends State<DutiesScreen> {
  static const filters = <String, String>{
    'today': 'Today',
    'upcoming': 'Upcoming',
    'pending': 'Pending',
    'active': 'Active',
    'completed': 'Completed',
    'rejected': 'History',
  };

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriverController>().refreshDuties('today');
    });
  }

  @override
  Widget build(BuildContext context) {
    final driver = context.watch<DriverController>();
    return Column(
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          child: Row(
            children: filters.entries.map((entry) {
              final selected = driver.dutyFilter == entry.key;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(entry.value),
                  selected: selected,
                  onSelected: (_) => driver.refreshDuties(entry.key),
                ),
              );
            }).toList(),
          ),
        ),
        if (driver.errorMessage != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(driver.errorMessage!, style: const TextStyle(color: Color(0xFF9B2226))),
          ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () => driver.refreshDuties(),
            child: driver.loading && driver.duties.isEmpty
                ? ListView(
                    children: const [
                      SizedBox(height: 120),
                      Center(child: CircularProgressIndicator()),
                    ],
                  )
                : driver.duties.isEmpty
                    ? ListView(
                        children: [
                          SizedBox(
                            height: MediaQuery.of(context).size.height * 0.5,
                            child: EmptyState(
                              title: 'No duties in this filter',
                              onRetry: () => driver.refreshDuties(),
                            ),
                          ),
                        ],
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: driver.duties.length,
                        itemBuilder: (context, index) {
                          final duty = driver.duties[index];
                          return DutyCard(
                            duty: duty,
                            onTap: () {
                              Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => DutyDetailScreen(assignmentId: duty.assignmentId),
                                ),
                              );
                            },
                          );
                        },
                      ),
          ),
        ),
      ],
    );
  }
}
