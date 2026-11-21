import 'package:flutter/foundation.dart';

import '../models/driver_profile.dart';
import '../services/api_client.dart';
import '../services/auth_storage.dart';
import '../services/driver_api.dart';

enum AuthStatus { unknown, signedOut, signedIn }

class AuthController extends ChangeNotifier {
  AuthController({
    required ApiClient apiClient,
    required this._storage,
    DriverApi? driverApi,
  })  : _apiClient = apiClient,
        _api = driverApi ?? DriverApi(apiClient);

  final ApiClient _apiClient;
  final AuthStorage _storage;
  final DriverApi _api;

  AuthStatus status = AuthStatus.unknown;
  DriverProfile? profile;
  String? errorMessage;
  bool busy = false;

  Future<void> restoreSession() async {
    final token = await _storage.readToken();
    if (token == null || token.isEmpty) {
      status = AuthStatus.signedOut;
      notifyListeners();
      return;
    }
    _apiClient.setToken(token);
    try {
      profile = await _api.profile();
      status = AuthStatus.signedIn;
      errorMessage = null;
    } on ApiException catch (error) {
      await _storage.clear();
      _apiClient.setToken(null);
      profile = null;
      status = AuthStatus.signedOut;
      errorMessage = error.statusCode == 401 ? null : error.message;
    }
    notifyListeners();
  }

  Future<bool> login(String phone, String password) async {
    busy = true;
    errorMessage = null;
    notifyListeners();
    try {
      final result = await _api.login(phone, password);
      final token = result['token'] as String?;
      if (token == null || token.isEmpty) {
        throw ApiException('Login did not return a session token.');
      }
      await _storage.saveToken(token);
      _apiClient.setToken(token);
      profile = await _api.profile();
      status = AuthStatus.signedIn;
      busy = false;
      notifyListeners();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      status = AuthStatus.signedOut;
      busy = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    await _api.logout();
    await _storage.clear();
    _apiClient.setToken(null);
    profile = null;
    status = AuthStatus.signedOut;
    notifyListeners();
  }

  void handleUnauthorized() {
    _storage.clear();
    _apiClient.setToken(null);
    profile = null;
    status = AuthStatus.signedOut;
    errorMessage = 'Session expired. Sign in again.';
    notifyListeners();
  }
}
