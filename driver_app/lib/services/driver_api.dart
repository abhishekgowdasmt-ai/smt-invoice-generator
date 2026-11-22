import '../models/driver_profile.dart';
import '../models/duty.dart';
import 'api_client.dart';

class DriverApi {
  DriverApi(this._client);

  final ApiClient _client;

  Future<Map<String, dynamic>> login(String phone, String password) {
    return _client.post(
      '/api/driver/login',
      auth: false,
      body: {'phone': phone, 'password': password},
    );
  }

  Future<Map<String, dynamic>> requestOtp(String phone, String purpose) {
    return _client.post(
      '/api/driver/otp/request',
      auth: false,
      body: {'phone': phone, 'purpose': purpose},
    );
  }

  Future<Map<String, dynamic>> loginWithOtp(String phone, String code) {
    return _client.post(
      '/api/driver/otp/login',
      auth: false,
      body: {'phone': phone, 'code': code},
    );
  }

  Future<Map<String, dynamic>> resetPasswordWithOtp({
    required String phone,
    required String code,
    required String newPassword,
  }) {
    return _client.post(
      '/api/driver/otp/reset-password',
      auth: false,
      body: {
        'phone': phone,
        'code': code,
        'new_password': newPassword,
      },
    );
  }

  Future<void> logout() async {
    try {
      await _client.post('/api/driver/logout');
    } on ApiException {
      // Local sign-out still proceeds.
    }
  }

  Future<DriverProfile> profile() async {
    final json = await _client.get('/api/driver/profile');
    final driver = json['driver'];
    if (driver is! Map<String, dynamic>) {
      throw ApiException('Profile was not returned by the server.');
    }
    return DriverProfile.fromJson(driver);
  }

  Future<Map<String, dynamic>> dashboard() => _client.get('/api/driver/dashboard');

  Future<List<Duty>> duties({String filter = 'all'}) async {
    final json = await _client.get('/api/driver/duties?filter=$filter');
    final list = json['duties'];
    if (list is! List) return [];
    return list
        .whereType<Map<String, dynamic>>()
        .map(Duty.fromJson)
        .toList();
  }

  Future<Duty> duty(String assignmentId) async {
    final json = await _client.get('/api/driver/duties/$assignmentId');
    final duty = json['duty'];
    if (duty is! Map<String, dynamic>) {
      throw ApiException('Duty was not returned by the server.');
    }
    return Duty.fromJson(duty);
  }

  Future<Duty> accept(String assignmentId) async {
    final json = await _client.post('/api/driver/duties/$assignmentId/accept');
    final duty = json['duty'];
    if (duty is! Map<String, dynamic>) {
      throw ApiException(json['message'] as String? ?? 'Accept failed.');
    }
    return Duty.fromJson(duty);
  }

  Future<Duty> reject(String assignmentId, {String? reason}) async {
    final json = await _client.post(
      '/api/driver/duties/$assignmentId/reject',
      body: {'reason': reason ?? 'Rejected by driver'},
    );
    final duty = json['duty'];
    if (duty is! Map<String, dynamic>) {
      throw ApiException(json['message'] as String? ?? 'Reject failed.');
    }
    return Duty.fromJson(duty);
  }

  Future<Duty> startTrip(String assignmentId, double startKm) async {
    final json = await _client.post(
      '/api/driver/duties/$assignmentId/start',
      body: {'start_km': startKm},
    );
    final duty = json['duty'];
    if (duty is! Map<String, dynamic>) {
      throw ApiException(json['message'] as String? ?? 'Start failed.');
    }
    return Duty.fromJson(duty);
  }

  Future<Duty> completeTrip(String assignmentId, double endKm) async {
    final json = await _client.post(
      '/api/driver/duties/$assignmentId/complete',
      body: {'end_km': endKm},
    );
    final duty = json['duty'];
    if (duty is! Map<String, dynamic>) {
      throw ApiException(json['message'] as String? ?? 'Complete failed.');
    }
    return Duty.fromJson(duty);
  }

  Future<List<AppNotification>> notifications() async {
    final json = await _client.get('/api/driver/notifications');
    final list = json['notifications'];
    if (list is! List) return [];
    return list
        .whereType<Map<String, dynamic>>()
        .map(AppNotification.fromJson)
        .toList();
  }

  Future<void> markNotificationRead(String id) async {
    await _client.post('/api/driver/notifications/$id/read');
  }

  Future<List<PayoutItem>> payouts() async {
    final json = await _client.get('/api/driver/payouts');
    final list = json['payouts'];
    if (list is! List) return [];
    return list
        .whereType<Map<String, dynamic>>()
        .map(PayoutItem.fromJson)
        .toList();
  }
}
