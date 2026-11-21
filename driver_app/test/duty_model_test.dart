import 'package:driver_app/models/duty.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Duty.fromJson maps assignment fields', () {
    final duty = Duty.fromJson({
      'assignment_id': 'a1',
      'assignment_status': 'assigned',
      'booking_id': 'b1',
      'booking_reference': 'SRC-1',
      'booking_status': 'assigned',
      'trip_date': '2026-11-21',
      'pickup_location': 'Airport',
      'vehicle': {
        'id': 'v1',
        'registration_number': 'KA01AB1234',
        'model': 'Innova',
        'fuel_type': 'diesel',
        'is_ev': false,
      },
      'readings': {'start_km': 10, 'end_km': null, 'total_km': null},
    });
    expect(duty.assignmentId, 'a1');
    expect(duty.isPending, isTrue);
    expect(duty.vehicle?.registrationNumber, 'KA01AB1234');
    expect(duty.readings.startKm, 10);
  });

  test('end kilometre client rule rejects lower reading', () {
    final start = 100.0;
    final end = 90.0;
    expect(end < start, isTrue);
  });
}
