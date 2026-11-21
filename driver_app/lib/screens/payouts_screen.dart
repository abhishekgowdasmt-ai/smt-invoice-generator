import 'package:material_ui/material_ui.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../state/driver_controller.dart';
import '../widgets/empty_state.dart';
import '../widgets/status_chip.dart';

class PayoutsScreen extends StatefulWidget {
  const PayoutsScreen({super.key});

  @override
  State<PayoutsScreen> createState() => _PayoutsScreenState();
}

class _PayoutsScreenState extends State<PayoutsScreen> {
  final _currency = NumberFormat.currency(locale: 'en_IN', symbol: '₹');

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DriverController>().refreshPayouts();
    });
  }

  @override
  Widget build(BuildContext context) {
    final driver = context.watch<DriverController>();
    return RefreshIndicator(
      onRefresh: () => driver.refreshPayouts(),
      child: driver.loading && driver.payouts.isEmpty
          ? ListView(
              children: const [
                SizedBox(height: 120),
                Center(child: CircularProgressIndicator()),
              ],
            )
          : driver.payouts.isEmpty
              ? ListView(
                  children: [
                    SizedBox(
                      height: MediaQuery.of(context).size.height * 0.6,
                      child: EmptyState(
                        title: 'No payout history',
                        subtitle: 'Paid duties appear here after supervisors record payouts.',
                        onRetry: () => driver.refreshPayouts(),
                      ),
                    ),
                  ],
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: driver.payouts.length,
                  itemBuilder: (context, index) {
                    final payout = driver.payouts[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    payout.bookingReference,
                                    style: const TextStyle(fontWeight: FontWeight.w700),
                                  ),
                                ),
                                StatusChip(payout.status, status: payout.status),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(_currency.format(payout.amount), style: const TextStyle(fontSize: 18)),
                            if (payout.dutyDate != null) Text('Duty date: ${payout.dutyDate}'),
                            if (payout.paidAt != null) Text('Paid: ${payout.paidAt}'),
                            if (payout.reference != null && payout.reference!.isNotEmpty)
                              Text('Reference: ${payout.reference}'),
                          ],
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}
