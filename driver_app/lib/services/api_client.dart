import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.code});

  final String message;
  final int? statusCode;
  final String? code;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        baseUrl = (baseUrl ?? AppConfig.apiBaseUrl).replaceAll(RegExp(r'/$'), '');

  final http.Client _client;
  final String baseUrl;
  String? _token;

  void setToken(String? token) {
    _token = token;
  }

  Map<String, String> _headers({bool auth = true}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (auth && _token != null && _token!.isNotEmpty) {
      headers['Authorization'] = 'Bearer $_token';
    }
    return headers;
  }

  Future<Map<String, dynamic>> get(String path, {bool auth = true}) async {
    return _send(() => _client.get(Uri.parse('$baseUrl$path'), headers: _headers(auth: auth)));
  }

  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
    bool auth = true,
  }) async {
    return _send(
      () => _client.post(
        Uri.parse('$baseUrl$path'),
        headers: _headers(auth: auth),
        body: jsonEncode(body ?? <String, dynamic>{}),
      ),
    );
  }

  Future<Map<String, dynamic>> _send(Future<http.Response> Function() send) async {
    late http.Response response;
    try {
      response = await send().timeout(const Duration(seconds: 25));
    } on Exception {
      throw ApiException(
        'Cannot reach the server. Check your connection and try again.',
        statusCode: 0,
      );
    }
    Map<String, dynamic> payload;
    try {
      final decoded = jsonDecode(response.body);
      payload = decoded is Map<String, dynamic> ? decoded : <String, dynamic>{};
    } on FormatException {
      throw ApiException('Unexpected server response.', statusCode: response.statusCode);
    }
    if (response.statusCode == 401) {
      throw ApiException(
        payload['message'] as String? ?? 'Session expired. Sign in again.',
        statusCode: 401,
      );
    }
    if (response.statusCode >= 400) {
      throw ApiException(
        payload['message'] as String? ?? 'Request failed.',
        statusCode: response.statusCode,
        code: payload['code'] as String?,
      );
    }
    if (payload['success'] == false) {
      throw ApiException(
        payload['message'] as String? ?? 'Request failed.',
        statusCode: response.statusCode,
        code: payload['code'] as String?,
      );
    }
    return payload;
  }
}
