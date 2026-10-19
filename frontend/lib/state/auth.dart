import 'dart:async';
import 'package:flutter/foundation.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../services/token_storage.dart';

class AuthState extends ChangeNotifier {
  final ApiClient api;
  UserMe? user;
  bool loading = false;
  bool restoring = true;
  String? error;

  AuthState(this.api) {
    api.onUnauthorized = handleUnauthorized;
    _restore();
  }

  void handleUnauthorized() {
    final hadSession = user != null || api.accessToken != null;
    api.setAccessToken(null);
    user = null;
    if (hadSession) {
      error = 'Your session expired. Please sign in again.';
      unawaited(TokenStorage.delete());
      notifyListeners();
    }
  }

  bool get isAuthenticated => user != null && api.accessToken != null;

  Future<void> _restore() async {
    try {
      final token = await TokenStorage.read();
      if (token != null && token.isNotEmpty) {
        api.setAccessToken(token);
        final res = await api.get('/me');
        user = UserMe.fromJson(Map<String, dynamic>.from(res));
      }
    } catch (_) {
      api.setAccessToken(null);
      user = null;
      await TokenStorage.delete();
    } finally {
      restoring = false;
      notifyListeners();
    }
  }

  Future<bool> login(String email, String password) async {
    if (loading) return false;
    loading = true;
    error = null;
    notifyListeners();
    try {
      final res = await api.post('/auth/login', body: {
        'email': email,
        'password': password,
      });
      api.setAccessToken(res['access_token']);
      user = UserMe.fromJson(Map<String, dynamic>.from(res['user']));
      await TokenStorage.write(res['access_token']);
      loading = false;
      notifyListeners();
      return true;
    } catch (e) {
      error = e.toString();
      loading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> register(String fullName, String email, String password) async {
    if (loading) return false;
    loading = true;
    error = null;
    notifyListeners();
    try {
      final res = await api.post('/auth/register', body: {
        'full_name': fullName,
        'email': email,
        'password': password,
      });
      api.setAccessToken(res['access_token']);
      user = UserMe.fromJson(Map<String, dynamic>.from(res['user']));
      await TokenStorage.write(res['access_token']);
      loading = false;
      notifyListeners();
      return true;
    } catch (e) {
      error = e.toString();
      loading = false;
      notifyListeners();
      return false;
    }
  }

  void logout() {
    api.setAccessToken(null);
    user = null;
    unawaited(TokenStorage.delete());
    notifyListeners();
  }
}
