import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:frontend/api/api_client.dart';
import 'package:frontend/screens/restaurant_list_screen.dart';
import 'package:frontend/state/auth.dart';
import 'package:frontend/state/cart.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('next and previous arrows load the selected pages', (
    tester,
  ) async {
    final requests = <Uri>[];
    await _pumpRestaurantScreen(tester, (request) async {
      requests.add(request.url);
      return _pageResponse(request.url);
    });

    expect(find.text('Page 1 of 3'), findsOneWidget);
    expect(find.text('Restaurant 01'), findsOneWidget);
    expect(
      tester
          .widget<IconButton>(
            find.ancestor(
              of: find.byTooltip('Previous page'),
              matching: find.byType(IconButton),
            ),
          )
          .onPressed,
      isNull,
    );

    await tester.tap(find.byTooltip('Next page'));
    await tester.pumpAndSettle();
    expect(find.text('Page 2 of 3'), findsOneWidget);
    expect(find.text('Restaurant 13'), findsOneWidget);
    expect(find.text('Restaurant 01'), findsNothing);

    await tester.tap(find.byTooltip('Next page'));
    await tester.pumpAndSettle();
    expect(find.text('Page 3 of 3'), findsOneWidget);
    expect(find.text('Restaurant 25'), findsOneWidget);
    expect(
      tester
          .widget<IconButton>(
            find.ancestor(
              of: find.byTooltip('Next page'),
              matching: find.byType(IconButton),
            ),
          )
          .onPressed,
      isNull,
    );

    await tester.tap(find.byTooltip('Previous page'));
    await tester.pumpAndSettle();
    expect(find.text('Page 2 of 3'), findsOneWidget);
    expect(find.text('Restaurant 13'), findsOneWidget);
    expect(
      requests.map((uri) => uri.queryParameters['page']),
      containsAllInOrder(['1', '1', '2', '3', '2']),
    );
  });

  testWidgets('search and cuisine filters restart at page one', (tester) async {
    final requests = <Uri>[];
    await _pumpRestaurantScreen(tester, (request) async {
      requests.add(request.url);
      return _pageResponse(request.url);
    });

    await tester.tap(find.byTooltip('Next page'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Restaurant 25');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();

    expect(find.text('Page 1 of 1'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(Card),
        matching: find.text('Restaurant 25'),
      ),
      findsOneWidget,
    );
    expect(requests.last.queryParameters['search'], 'Restaurant 25');
    expect(requests.last.queryParameters['page'], '1');

    await tester.enterText(find.byType(TextField), '');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Next page'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilterChip, 'Bengali'));
    await tester.pumpAndSettle();

    expect(find.text('Page 1 of 2'), findsOneWidget);
    expect(requests.last.queryParameters['cuisine'], 'Bengali');
    expect(requests.last.queryParameters['page'], '1');
  });

  testWidgets('empty filtered results display the empty state', (tester) async {
    await _pumpRestaurantScreen(tester, (request) async {
      final response = _pageResponse(request.url);
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      if (request.url.queryParameters['search'] == 'missing') {
        body['items'] = [];
        body['total'] = 0;
        body['has_more'] = false;
      }
      return http.Response(jsonEncode(body), response.statusCode);
    });

    await tester.enterText(find.byType(TextField), 'missing');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();

    expect(find.text('No restaurants found'), findsOneWidget);
  });

  testWidgets('a failed page can be retried without falling back to page one', (
    tester,
  ) async {
    var pageTwoAttempts = 0;
    await _pumpRestaurantScreen(tester, (request) async {
      if (request.url.queryParameters['page'] == '2' &&
          ++pageTwoAttempts == 1) {
        return http.Response('{"message":"temporary failure"}', 503);
      }
      return _pageResponse(request.url);
    });

    await tester.tap(find.byTooltip('Next page'));
    await tester.pumpAndSettle();
    expect(find.text('Retry'), findsOneWidget);

    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(find.text('Page 2 of 3'), findsOneWidget);
    expect(find.text('Restaurant 13'), findsOneWidget);
    expect(pageTwoAttempts, 2);
  });

  testWidgets('rapid next requests while a page is loading are ignored', (
    tester,
  ) async {
    final pageTwoResponse = Completer<http.Response>();
    var pageTwoRequests = 0;
    await _pumpRestaurantScreen(tester, (request) async {
      if (request.url.queryParameters['page'] == '2') {
        pageTwoRequests++;
        return pageTwoResponse.future;
      }
      return _pageResponse(request.url);
    });

    final nextButton = tester.widget<IconButton>(
      find.ancestor(
        of: find.byTooltip('Next page'),
        matching: find.byType(IconButton),
      ),
    );
    nextButton.onPressed!();
    nextButton.onPressed!();
    await tester.pump();
    expect(pageTwoRequests, 1);

    pageTwoResponse.complete(
      _pageResponse(
        Uri.parse('http://localhost/api/v1/restaurants?page=2&page_size=12'),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Page 2 of 3'), findsOneWidget);
    expect(pageTwoRequests, 1);
  });

  testWidgets('phone listing keeps actions and paging controls within width', (
    tester,
  ) async {
    await _pumpRestaurantScreen(
      tester,
      (request) async => _pageResponse(request.url),
      viewport: const Size(390, 844),
    );

    expect(find.byTooltip('More options'), findsOneWidget);
    expect(find.text('Browse mode'), findsOneWidget);
    expect(find.byTooltip('Previous page'), findsOneWidget);
    expect(find.byTooltip('Next page'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('phone infinite scroll loads each remaining page once', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({
      'restaurant_browse_mode': 'infinite',
    });
    final requests = <Uri>[];
    await _pumpRestaurantScreen(tester, (request) async {
      requests.add(request.url);
      return _pageResponse(request.url);
    }, viewport: const Size(390, 844));

    for (final restaurant in ['Restaurant 13', 'Restaurant 25']) {
      await tester.dragUntilVisible(
        find.text(restaurant),
        find.byType(CustomScrollView),
        const Offset(0, -500),
      );
      await tester.pumpAndSettle();
      expect(find.text(restaurant), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
    expect(find.text('End of results'), findsOneWidget);
    expect(
      requests.where((uri) => uri.queryParameters['page'] == '2').length,
      1,
    );
    expect(
      requests.where((uri) => uri.queryParameters['page'] == '3').length,
      1,
    );
  });
}

Future<void> _pumpRestaurantScreen(
  WidgetTester tester,
  Future<http.Response> Function(http.Request) handler, {
  Size viewport = const Size(1440, 1000),
}) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = viewport;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final api = ApiClient(client: MockClient(handler));
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        Provider<ApiClient>.value(value: api),
        ChangeNotifierProvider<AuthState>.value(value: AuthState(api)),
        ChangeNotifierProvider<CartState>.value(value: CartState(api: api)),
      ],
      child: const MaterialApp(home: RestaurantListScreen()),
    ),
  );
  await tester.pumpAndSettle();
}

http.Response _pageResponse(Uri uri) {
  final all = List.generate(25, (index) {
    final number = index + 1;
    return {
      'id': 'restaurant-$number',
      'name': 'Restaurant ${number.toString().padLeft(2, '0')}',
      'description': '',
      'cuisine': number.isOdd ? 'Bengali' : 'Italian',
      'rating': 450,
      'is_active': true,
      'accepts_orders': true,
      'image_url': null,
    };
  });
  final search = uri.queryParameters['search']?.toLowerCase();
  final cuisine = uri.queryParameters['cuisine'];
  final filtered = all.where((restaurant) {
    return (search == null ||
            (restaurant['name']! as String).toLowerCase().contains(search)) &&
        (cuisine == null || restaurant['cuisine'] == cuisine);
  }).toList();
  final page = int.tryParse(uri.queryParameters['page'] ?? '1') ?? 1;
  final pageSize = int.tryParse(uri.queryParameters['page_size'] ?? '12') ?? 12;
  final start = (page - 1) * pageSize;
  final items = start >= filtered.length
      ? <Map<String, Object?>>[]
      : filtered.skip(start).take(pageSize).toList();
  return http.Response(
    jsonEncode({
      'items': items,
      'page': page,
      'page_size': pageSize,
      'total': filtered.length,
      'has_more': start + items.length < filtered.length,
    }),
    200,
  );
}
