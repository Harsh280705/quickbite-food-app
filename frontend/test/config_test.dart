import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/config.dart';

void main() {
  String resolve({
    bool web = false,
    TargetPlatform platform = TargetPlatform.android,
    bool release = false,
    String configured = '',
  }) => AppConfig.resolveApiBaseUrl(
        isWeb: web,
        platform: platform,
        isRelease: release,
        configured: configured,
      );

  test('debug web defaults to local backend', () {
    expect(resolve(web: true, platform: TargetPlatform.linux), 'http://localhost:8000');
  });

  test('emulator uses explicit emulator host configuration', () {
    expect(
      resolve(configured: 'http://10.0.2.2:8000'),
      'http://10.0.2.2:8000',
    );
  });

  test('physical Android requires explicit LAN API URL', () {
    expect(
      () => resolve(),
      throwsA(isA<StateError>().having(
        (error) => error.message,
        'message',
        contains('PC_LAN_IPV4'),
      )),
    );
    expect(
      resolve(configured: 'http://192.168.1.25:8000'),
      'http://192.168.1.25:8000',
    );
  });

  test('explicit override is trimmed and trailing slash normalized', () {
    expect(
      resolve(configured: '  https://api.example.com///  ', release: true),
      'https://api.example.com',
    );
  });

  test('rejects malformed URLs, localhost on Android, and HTTP release URLs', () {
    expect(() => resolve(configured: 'not a URL'), throwsA(isA<StateError>()));
    expect(
      () => resolve(configured: 'http://localhost:8000'),
      throwsA(isA<StateError>()),
    );
    expect(
      () => resolve(configured: 'http://api.example.com', release: true),
      throwsA(isA<StateError>()),
    );
  });

  test('production web defaults to same-origin proxy', () {
    expect(resolve(web: true, release: true, platform: TargetPlatform.linux), '');
  });
}
