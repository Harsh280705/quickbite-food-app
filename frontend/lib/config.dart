import 'package:flutter/foundation.dart';

class AppConfig {
  static String get apiBaseUrl => resolveApiBaseUrl(
        isWeb: kIsWeb,
        platform: defaultTargetPlatform,
        isRelease: kReleaseMode,
        configured: const String.fromEnvironment('API_BASE_URL'),
      );

  /// Resolves the one API origin used by every ApiClient request.
  ///
  /// Android does not expose a reliable emulator-versus-physical-device flag
  /// to Flutter. Require an explicit URL on Android so a physical device can
  /// never silently target its own loopback or an emulator-only host alias.
  static String resolveApiBaseUrl({
    required bool isWeb,
    required TargetPlatform platform,
    required bool isRelease,
    required String configured,
  }) {
    final value = configured.trim();
    if (value.isEmpty) {
      if (isRelease) {
        if (isWeb) return ''; // Production web uses the same-origin Nginx proxy.
        throw StateError('Release builds require an HTTPS API_BASE_URL.');
      }
      if (isWeb) return 'http://localhost:8000';
      if (platform == TargetPlatform.android) {
        throw StateError(
          'Android API_BASE_URL is required. Use http://10.0.2.2:8000 for '
          'an Android emulator, or http://<PC_LAN_IPV4>:8000 for a physical phone.',
        );
      }
      if (platform == TargetPlatform.iOS) return 'http://127.0.0.1:8000';
      return 'http://127.0.0.1:8000';
    }

    final uri = Uri.tryParse(value);
    if (uri == null ||
        !uri.isAbsolute ||
        !{'http', 'https'}.contains(uri.scheme.toLowerCase()) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path.replaceAll('/', '').isNotEmpty)) {
      throw StateError(
        'API_BASE_URL must be an absolute http(s) origin without a path, query, or fragment.',
      );
    }
    if (isRelease && uri.scheme.toLowerCase() != 'https') {
      throw StateError('Release builds require an HTTPS API_BASE_URL.');
    }
    if (platform == TargetPlatform.android && _isLoopbackHost(uri.host)) {
      throw StateError(
        'Android cannot reach the development PC at localhost or 127.0.0.1. '
        'Use http://10.0.2.2:8000 for an emulator or the PC LAN IPv4 for a physical phone.',
      );
    }
    return uri.origin;
  }

  static bool _isLoopbackHost(String host) {
    final normalized = host.toLowerCase();
    return normalized == 'localhost' ||
        normalized == '::1' ||
        normalized.startsWith('127.');
  }

  static String get apiV1 => '$apiBaseUrl/api/v1';

  static bool get isWeb => kIsWeb;
}
