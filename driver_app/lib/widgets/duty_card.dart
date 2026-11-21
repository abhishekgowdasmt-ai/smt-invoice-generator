import 'package:material_ui/material_ui.dart';

import '../models/duty.dart';
import 'status_chip.dart';

class DutyCard extends StatelessWidget {
  const DutyCard({super.key, required this.duty, this.onTap});

  final Duty duty;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      duty.bookingReference,
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
                    ),
                  ),
                  StatusChip(duty.assignmentStatus, status: duty.assignmentStatus),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                [
                  if (duty.tripDate != null) duty.tripDate!,
                  if (duty.pickupTime != null) duty.pickupTime!,
                ].join(' · '),
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              if (duty.pickupLocation != null && duty.pickupLocation!.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(duty.pickupLocation!),
              ],
              if (duty.companyName != null) ...[
                const SizedBox(height: 6),
                Text(duty.companyName!, style: const TextStyle(color: Color(0xFF5C6670))),
              ],
              if (duty.vehicle?.registrationNumber != null) ...[
                const SizedBox(height: 6),
                Text('Vehicle ${duty.vehicle!.registrationNumber}'),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
