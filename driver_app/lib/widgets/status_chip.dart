import 'package:material_ui/material_ui.dart';

import '../theme/app_theme.dart';

class StatusChip extends StatelessWidget {
  const StatusChip(this.label, {super.key, this.status});

  final String label;
  final String? status;

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.statusColor(status ?? label);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 12),
      ),
    );
  }
}
