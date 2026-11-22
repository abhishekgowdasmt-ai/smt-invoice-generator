import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../models/duty.dart';
import '../state/driver_controller.dart';
import '../widgets/status_chip.dart';

class DutyDetailScreen extends StatefulWidget {
  const DutyDetailScreen({super.key, required this.assignmentId});

  final String assignmentId;

  @override
  State<DutyDetailScreen> createState() => _DutyDetailScreenState();
}

class _DutyDetailScreenState extends State<DutyDetailScreen> {
  Duty? duty;
  bool loading = true;
  String? error;
  final _startKm = TextEditingController();
  final _endKm = TextEditingController();
  final _rejectReason = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _startKm.dispose();
    _endKm.dispose();
    _rejectReason.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    final result = await context.read<DriverController>().loadDuty(widget.assignmentId);
    if (!mounted) return;
    setState(() {
      duty = result;
      loading = false;
      error = result == null ? context.read<DriverController>().errorMessage : null;
      if (result?.readings.startKm != null) {
        _startKm.text = '${result!.readings.startKm}';
      }
    });
  }

  Future<void> _accept() async {
    final driver = context.read<DriverController>();
    final updated = await driver.accept(widget.assignmentId);
    if (!mounted) return;
    if (updated == null) {
      _toast(driver.errorMessage ?? 'Accept failed');
      return;
    }
    setState(() => duty = updated);
    _toast('Duty accepted');
  }

  Future<void> _reject() async {
    final reason = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Reject duty'),
          content: TextField(
            controller: _rejectReason,
            decoration: const InputDecoration(
              labelText: 'Reason (optional)',
              hintText: 'Unavailable / wrong area / other',
            ),
            maxLines: 3,
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, _rejectReason.text.trim()),
              child: const Text('Reject'),
            ),
          ],
        );
      },
    );
    if (!mounted) return;
    if (reason == null) return;
    final driver = context.read<DriverController>();
    final updated = await driver.reject(
          widget.assignmentId,
          reason: reason.isEmpty ? null : reason,
        );
    if (!mounted) return;
    if (updated == null) {
      _toast(driver.errorMessage ?? 'Reject failed');
      return;
    }
    setState(() => duty = updated);
    _toast('Duty rejected');
  }

  Future<void> _start() async {
    final value = double.tryParse(_startKm.text.trim());
    if (value == null || value < 0) {
      _toast('Enter a valid start kilometre reading');
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Start trip'),
        content: Text('Start kilometre: $value\nConfirm only when you begin the trip.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Start')),
        ],
      ),
    );
    if (!mounted) return;
    if (confirmed != true) return;
    final driver = context.read<DriverController>();
    final updated = await driver.startTrip(widget.assignmentId, value);
    if (!mounted) return;
    if (updated == null) {
      _toast(driver.errorMessage ?? 'Start failed');
      return;
    }
    setState(() => duty = updated);
    _toast('Trip started');
  }

  Future<void> _complete() async {
    final value = double.tryParse(_endKm.text.trim());
    if (value == null || value < 0) {
      _toast('Enter a valid end kilometre reading');
      return;
    }
    final start = duty?.readings.startKm;
    if (start != null && value < start) {
      _toast('End kilometre cannot be lower than start kilometre');
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Complete trip'),
        content: Text('End kilometre: $value\nThis submits the reading to the server.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Complete')),
        ],
      ),
    );
    if (!mounted) return;
    if (confirmed != true) return;
    final driver = context.read<DriverController>();
    final updated = await driver.completeTrip(widget.assignmentId, value);
    if (!mounted) return;
    if (updated == null) {
      _toast(driver.errorMessage ?? 'Complete failed');
      return;
    }
    setState(() => duty = updated);
    _toast('Trip completed');
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Duty details')),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : duty == null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(error ?? 'Duty not found'),
                      const SizedBox(height: 12),
                      OutlinedButton(onPressed: _load, child: const Text('Retry')),
                    ],
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            duty!.bookingReference,
                            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                          ),
                        ),
                        StatusChip(duty!.assignmentStatus, status: duty!.assignmentStatus),
                      ],
                    ),
                    const SizedBox(height: 12),
                    _line('Trip date', duty!.tripDate),
                    _line('Pickup time', duty!.pickupTime),
                    _line('Pickup', duty!.pickupLocation),
                    _line('Route', duty!.route),
                    _line('Passenger', duty!.passengerName),
                    _line('Passenger phone', duty!.passengerPhone),
                    _line('Company', duty!.companyName),
                    _line('Duty type', duty!.dutyType),
                    _line('Cab type', duty!.cabType),
                    _line('Remarks', duty!.remarks),
                    _line('Booking status', duty!.bookingStatus),
                    if (duty!.vehicle != null) ...[
                      const SizedBox(height: 8),
                      const Text('Vehicle', style: TextStyle(fontWeight: FontWeight.w700)),
                      _line('Registration', duty!.vehicle!.registrationNumber),
                      _line('Model', duty!.vehicle!.model),
                      _line('Fuel', duty!.vehicle!.fuelType),
                    ],
                    if (duty!.tripSession != null) ...[
                      const SizedBox(height: 8),
                      const Text('Trip session', style: TextStyle(fontWeight: FontWeight.w700)),
                      _line('Status', duty!.tripSession!.status),
                      _line('Started', duty!.tripSession!.startedAt),
                      _line('Ended', duty!.tripSession!.endedAt),
                    ],
                    const SizedBox(height: 8),
                    const Text('Kilometre readings', style: TextStyle(fontWeight: FontWeight.w700)),
                    _line('Start km', duty!.readings.startKm?.toString()),
                    _line('End km', duty!.readings.endKm?.toString()),
                    _line('Total km', duty!.readings.totalKm?.toString()),
                    const SizedBox(height: 20),
                    if (duty!.isPending) ...[
                      ElevatedButton(onPressed: _accept, child: const Text('Accept duty')),
                      const SizedBox(height: 8),
                      OutlinedButton(onPressed: _reject, child: const Text('Reject duty')),
                    ],
                    if (duty!.isAccepted && !duty!.hasActiveTrip) ...[
                      TextField(
                        controller: _startKm,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'Start kilometre'),
                      ),
                      const SizedBox(height: 8),
                      ElevatedButton(onPressed: _start, child: const Text('Start trip')),
                    ],
                    if (duty!.hasActiveTrip) ...[
                      TextField(
                        controller: _endKm,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'End kilometre'),
                      ),
                      const SizedBox(height: 8),
                      ElevatedButton(onPressed: _complete, child: const Text('Complete trip')),
                    ],
                  ],
                ),
    );
  }

  Widget _line(String label, String? value) {
    if (value == null || value.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 120, child: Text(label, style: const TextStyle(color: Color(0xFF5C6670)))),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
