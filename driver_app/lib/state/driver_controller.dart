import 'package:flutter/foundation.dart';

import '../models/driver_profile.dart';
import '../models/duty.dart';
import '../services/api_client.dart';
import '../services/driver_api.dart';

class DriverController extends ChangeNotifier {
  DriverController(this._api);

  final DriverApi _api;

  bool loading = false;
  String? errorMessage;
  bool live = true;
  DriverProfile? dashboardDriver;
  List<Duty> todayDuties = [];
  List<Duty> pendingDuties = [];
  List<Duty> upcomingDuties = [];
  Duty? activeTrip;
  List<Duty> completedDuties = [];
  List<AppNotification> notifications = [];
  List<Duty> duties = [];
  List<PayoutItem> payouts = [];
  String dutyFilter = 'today';

  Future<void> refreshDashboard() async {
    loading = true;
    errorMessage = null;
    notifyListeners();
    try {
      final json = await _api.dashboard();
      live = json['live'] != false;
      final driver = json['driver'];
      if (driver is Map<String, dynamic>) {
        dashboardDriver = DriverProfile.fromJson(driver);
      }
      todayDuties = _duties(json['today_duties']);
      pendingDuties = _duties(json['pending_responses']);
      upcomingDuties = _duties(json['upcoming_duties']);
      completedDuties = _duties(json['completed_duties']);
      final active = json['active_trip'];
      activeTrip = active is Map<String, dynamic> ? Duty.fromJson(active) : null;
      notifications = _notes(json['notifications']);
    } on ApiException catch (error) {
      errorMessage = error.message;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> refreshDuties([String? filter]) async {
    if (filter != null) dutyFilter = filter;
    loading = true;
    errorMessage = null;
    notifyListeners();
    try {
      duties = await _api.duties(filter: dutyFilter);
      live = true;
    } on ApiException catch (error) {
      errorMessage = error.message;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<Duty?> loadDuty(String assignmentId) async {
    try {
      return await _api.duty(assignmentId);
    } on ApiException catch (error) {
      errorMessage = error.message;
      notifyListeners();
      return null;
    }
  }

  Future<Duty?> accept(String assignmentId) => _mutate(() => _api.accept(assignmentId));

  Future<Duty?> reject(String assignmentId, {String? reason}) =>
      _mutate(() => _api.reject(assignmentId, reason: reason));

  Future<Duty?> startTrip(String assignmentId, double startKm) =>
      _mutate(() => _api.startTrip(assignmentId, startKm));

  Future<Duty?> completeTrip(String assignmentId, double endKm) =>
      _mutate(() => _api.completeTrip(assignmentId, endKm));

  Future<void> refreshNotifications() async {
    try {
      notifications = await _api.notifications();
      errorMessage = null;
    } on ApiException catch (error) {
      errorMessage = error.message;
    }
    notifyListeners();
  }

  Future<void> markRead(String id) async {
    await _api.markNotificationRead(id);
    await refreshNotifications();
  }

  Future<void> refreshPayouts() async {
    loading = true;
    errorMessage = null;
    notifyListeners();
    try {
      payouts = await _api.payouts();
    } on ApiException catch (error) {
      errorMessage = error.message;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<Duty?> _mutate(Future<Duty> Function() action) async {
    try {
      final duty = await action();
      errorMessage = null;
      await refreshDashboard();
      await refreshDuties();
      return duty;
    } on ApiException catch (error) {
      errorMessage = error.message;
      notifyListeners();
      return null;
    }
  }

  List<Duty> _duties(dynamic raw) {
    if (raw is! List) return [];
    return raw.whereType<Map<String, dynamic>>().map(Duty.fromJson).toList();
  }

  List<AppNotification> _notes(dynamic raw) {
    if (raw is! List) return [];
    return raw.whereType<Map<String, dynamic>>().map(AppNotification.fromJson).toList();
  }
}
