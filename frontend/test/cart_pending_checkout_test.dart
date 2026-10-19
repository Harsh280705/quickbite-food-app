import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:frontend/state/cart.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  test('pending key and exact checkout payload survive CartState recreation', () async {
    final first = CartState();
    const payload = <String, dynamic>{
      'restaurant_id': 'rest-1',
      'delivery_address': '12 Lake Road, Bengaluru',
      'items': [
        {'menu_item_id': 'item-1', 'quantity': 2},
      ],
    };

    await first.preparePendingCheckout(payload);
    final key = first.pendingIdempotencyKey;
    first.dispose();

    final restored = CartState();
    await restored.restore();

    expect(restored.pendingIdempotencyKey, key);
    expect(restored.pendingRequest, payload);
    expect(restored.deliveryAddress, payload['delivery_address']);
    restored.dispose();
  });

  test('retry preparation preserves the same key and rejects changed payloads', () async {
    final cart = CartState();
    const request = <String, dynamic>{
      'restaurant_id': 'rest-1',
      'delivery_address': '12 Lake Road, Bengaluru',
      'items': [
        {'menu_item_id': 'item-1', 'quantity': 1},
      ],
    };
    await cart.preparePendingCheckout(request);
    final key = cart.pendingIdempotencyKey;

    await cart.preparePendingCheckout(request);
    expect(cart.pendingIdempotencyKey, key);

    await expectLater(
      cart.preparePendingCheckout({...request, 'delivery_address': '99 New Street, Bengaluru'}),
      throwsStateError,
    );
    expect(cart.pendingIdempotencyKey, key);
    expect(cart.pendingRequest, request);
    cart.dispose();
  });

  test('resolved checkout removes persisted pending state', () async {
    final cart = CartState();
    await cart.preparePendingCheckout(const {
      'restaurant_id': 'rest-1',
      'delivery_address': '12 Lake Road, Bengaluru',
      'items': [
        {'menu_item_id': 'item-1', 'quantity': 1},
      ],
    });

    await cart.clearResolvedCheckout();
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('pending_checkout'), isNull);
    cart.dispose();
  });
}
