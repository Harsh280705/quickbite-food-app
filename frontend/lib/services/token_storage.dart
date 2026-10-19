import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  static const _key = 'quickbite_access_token';
  static const _storage = FlutterSecureStorage();

  static Future<String?> read() async {
    if (kIsWeb) return null;
    return _storage.read(key: _key);
  }

  static Future<void> write(String token) async {
    if (kIsWeb) return;
    await _storage.write(key: _key, value: token);
  }

  static Future<void> delete() async {
    if (kIsWeb) return;
    await _storage.delete(key: _key);
  }
}
