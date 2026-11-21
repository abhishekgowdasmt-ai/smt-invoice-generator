class VehicleInfo {
  VehicleInfo({
    required this.id,
    this.registrationNumber,
    this.model,
    this.fuelType,
    this.isEv = false,
  });

  final String id;
  final String? registrationNumber;
  final String? model;
  final String? fuelType;
  final bool isEv;

  factory VehicleInfo.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return VehicleInfo(id: '');
    }
    return VehicleInfo(
      id: '${json['id'] ?? ''}',
      registrationNumber: json['registration_number'] as String?,
      model: json['model'] as String?,
      fuelType: json['fuel_type'] as String?,
      isEv: json['is_ev'] == true,
    );
  }
}

class TripSessionInfo {
  TripSessionInfo({
    required this.id,
    required this.status,
    this.startedAt,
    this.endedAt,
  });

  final String id;
  final String status;
  final String? startedAt;
  final String? endedAt;

  factory TripSessionInfo.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return TripSessionInfo(id: '', status: '');
    }
    return TripSessionInfo(
      id: '${json['id'] ?? ''}',
      status: '${json['status'] ?? ''}',
      startedAt: json['started_at'] as String?,
      endedAt: json['ended_at'] as String?,
    );
  }

  bool get isActive => status == 'active';
}

class DutyReadings {
  DutyReadings({this.startKm, this.endKm, this.totalKm});

  final double? startKm;
  final double? endKm;
  final double? totalKm;

  factory DutyReadings.fromJson(Map<String, dynamic>? json) {
    double? asDouble(dynamic value) {
      if (value == null) return null;
      if (value is num) return value.toDouble();
      return double.tryParse('$value');
    }

    return DutyReadings(
      startKm: asDouble(json?['start_km']),
      endKm: asDouble(json?['end_km']),
      totalKm: asDouble(json?['total_km']),
    );
  }
}

class Duty {
  Duty({
    required this.assignmentId,
    required this.assignmentStatus,
    required this.bookingId,
    required this.bookingReference,
    required this.bookingStatus,
    this.tripDate,
    this.pickupTime,
    this.pickupLocation,
    this.route,
    this.passengerName,
    this.passengerPhone,
    this.dutyType,
    this.cabType,
    this.remarks,
    this.companyName,
    this.notes,
    this.rejectionReason,
    this.vehicle,
    this.tripSession,
    DutyReadings? readings,
  }) : readings = readings ?? DutyReadings();

  final String assignmentId;
  final String assignmentStatus;
  final String bookingId;
  final String bookingReference;
  final String bookingStatus;
  final String? tripDate;
  final String? pickupTime;
  final String? pickupLocation;
  final String? route;
  final String? passengerName;
  final String? passengerPhone;
  final String? dutyType;
  final String? cabType;
  final String? remarks;
  final String? companyName;
  final String? notes;
  final String? rejectionReason;
  final VehicleInfo? vehicle;
  final TripSessionInfo? tripSession;
  final DutyReadings readings;

  factory Duty.fromJson(Map<String, dynamic> json) {
    final vehicleJson = json['vehicle'];
    final sessionJson = json['trip_session'];
    return Duty(
      assignmentId: '${json['assignment_id'] ?? ''}',
      assignmentStatus: '${json['assignment_status'] ?? ''}',
      bookingId: '${json['booking_id'] ?? ''}',
      bookingReference: '${json['booking_reference'] ?? json['booking_id'] ?? ''}',
      bookingStatus: '${json['booking_status'] ?? ''}',
      tripDate: json['trip_date'] as String?,
      pickupTime: json['pickup_time'] as String?,
      pickupLocation: json['pickup_location'] as String?,
      route: json['route'] as String?,
      passengerName: json['passenger_name'] as String?,
      passengerPhone: json['passenger_phone'] as String?,
      dutyType: json['duty_type'] as String?,
      cabType: json['cab_type'] as String?,
      remarks: json['remarks'] as String?,
      companyName: json['company_name'] as String?,
      notes: json['notes'] as String?,
      rejectionReason: json['rejection_reason'] as String?,
      vehicle: vehicleJson is Map<String, dynamic>
          ? VehicleInfo.fromJson(vehicleJson)
          : null,
      tripSession: sessionJson is Map<String, dynamic>
          ? TripSessionInfo.fromJson(sessionJson)
          : null,
      readings: DutyReadings.fromJson(
        json['readings'] is Map<String, dynamic>
            ? json['readings'] as Map<String, dynamic>
            : null,
      ),
    );
  }

  bool get isPending => assignmentStatus == 'assigned';
  bool get isAccepted => assignmentStatus == 'accepted';
  bool get hasActiveTrip => tripSession?.isActive == true;
}
