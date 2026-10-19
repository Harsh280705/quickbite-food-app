import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config.dart';

class ApiException implements Exception {
  final int statusCode;
  final String code;
  final String message;
  final Map<String, dynamic> details;
  final String? requestId;
  ApiException({
    required this.statusCode,
    required this.code,
    required this.message,
    this.details = const {},
    this.requestId,
  });

  @override
  String toString() => 'ApiException($statusCode,$code): $message';
}

class ApiClient {
  final http.Client _client;
  String? _accessToken;
  void Function()? onUnauthorized;

  ApiClient({http.Client? client}) : _client = client ?? http.Client();

  String? get accessToken => _accessToken;
  void setAccessToken(String? token) => _accessToken = token;

  Map<String, String> _headers({String? idempotencyKey}) {
    final h = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (_accessToken != null) h['Authorization'] = 'Bearer $_accessToken';
    if (idempotencyKey != null) h['Idempotency-Key'] = idempotencyKey;
    return h;
  }

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final base = Uri.parse(AppConfig.apiV1 + path);
    if (query == null) return base;
    return base.replace(queryParameters: query.map((k, v) => MapEntry(k, v.toString())));
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    final res = await _client
        .get(_uri(path, query), headers: _headers())
        .timeout(const Duration(seconds: 10));
    return _decode(res);
  }

  Future<dynamic> post(String path,
      {Object? body, String? idempotencyKey}) async {
    final res = await _client
        .post(_uri(path),
            headers: _headers(idempotencyKey: idempotencyKey),
            body: body == null ? null : jsonEncode(body))
        .timeout(const Duration(seconds: 10));
    return _decode(res);
  }

  Future<dynamic> patch(String path, {Object? body}) async {
    final res = await _client
        .patch(_uri(path),
            headers: _headers(),
            body: body == null ? null : jsonEncode(body))
        .timeout(const Duration(seconds: 10));
    return _decode(res);
  }

  dynamic _decode(http.Response res) {
    dynamic body;
    if (res.body.isNotEmpty) {
      try {
        body = jsonDecode(res.body);
      } catch (_) {
        body = res.body;
      }
    }
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return body;
    }
    if (res.statusCode == 401) {
      _accessToken = null;
      onUnauthorized?.call();
    }
    if (body is Map<String, dynamic>) {
      throw ApiException(
        statusCode: res.statusCode,
        code: body['code']?.toString() ?? 'error',
        message: body['message']?.toString() ?? res.reasonPhrase ?? 'Request failed',
        details: (body['details'] is Map) ? Map<String, dynamic>.from(body['details']) : {},
        requestId: body['request_id']?.toString(),
      );
    }
    throw ApiException(
      statusCode: res.statusCode,
      code: 'http_error',
      message: res.reasonPhrase ?? 'Request failed',
    );
  }

  void dispose() => _client.close();
}
