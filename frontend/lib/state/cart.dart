import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/api_client.dart';
import '../models.dart';

class CartLine {
  final MenuItem item;
  int quantity;
  CartLine({required this.item, this.quantity = 1});
  int get lineTotal => item.priceMinor * quantity;
}

class CartState extends ChangeNotifier {
  final ApiClient? api;
  String? restaurantId;
  String? restaurantName;
  final List<CartLine> lines = [];

  CartState({this.api}) {
    unawaited(restore());
  }
  String deliveryAddress = '';
  String? pendingIdempotencyKey;
  Map<String, dynamic>? pendingRequest;
  bool checkoutInProgress = false;
  String? checkoutError;
  bool checkoutRetryable = false;

  void notify() => notifyListeners();

  int get subtotal => lines.fold(0, (s, l) => s + l.lineTotal);
  int get itemCount => lines.fold(0, (s, l) => s + l.quantity);
  bool get isEmpty => lines.isEmpty;

  Future<void> restore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final pendingRaw = prefs.getString('pending_checkout');
      if (pendingRaw != null && pendingRaw.isNotEmpty) {
        final pending = jsonDecode(pendingRaw) as Map<String, dynamic>;
        pendingIdempotencyKey = pending['key']?.toString();
        final request = pending['request'];
        if (request is Map) {
          pendingRequest = Map<String, dynamic>.from(request);
        }
      }
      final raw = prefs.getString('cart_draft');
      final data = raw == null || raw.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(raw) as Map<String, dynamic>;
      restaurantId = data['restaurant_id']?.toString() ??
          pendingRequest?['restaurant_id']?.toString();
      restaurantName = data['restaurant_name']?.toString();
      deliveryAddress = pendingRequest?['delivery_address']?.toString() ??
          data['delivery_address']?.toString() ?? '';
      final savedLines = pendingRequest != null
          ? (pendingRequest!['items'] as List? ?? []).cast<Map<String, dynamic>>()
          : (data['lines'] as List? ?? []).cast<Map<String, dynamic>>();
      if (restaurantId != null && savedLines.isNotEmpty) {
        final client = api;
        if (client == null) return;
        final response = await client.get('/restaurants/$restaurantId/menu', query: {'page': 1, 'page_size': 100});
        final items = (response['items'] as List).map((e) => MenuItem.fromJson(Map<String, dynamic>.from(e))).toList();
        final byId = {for (final item in items) item.id: item};
        for (final saved in savedLines) {
          final id = saved['menu_item_id']?.toString();
          final quantity = (saved['quantity'] as num?)?.toInt() ?? 1;
          if (id == null) continue;
          final item = byId[id];
          if (item == null || !item.isAvailable) continue;
          lines.add(CartLine(item: item, quantity: quantity.clamp(1, 20)));
        }
      }
      notifyListeners();
    } catch (_) {
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.remove('cart_draft');
      } catch (_) {}
    }
  }

  Future<void> persistPendingCheckout() async {
    final prefs = await SharedPreferences.getInstance();
    if (pendingIdempotencyKey == null || pendingRequest == null) {
      await prefs.remove('pending_checkout');
      return;
    }
    await prefs.setString('pending_checkout', jsonEncode({
      'key': pendingIdempotencyKey,
      'request': pendingRequest,
    }));
  }

  Future<void> clearPendingCheckout() async {
    pendingIdempotencyKey = null;
    pendingRequest = null;
    await persistPendingCheckout();
    notifyListeners();
  }

  Future<void> _saveDraft() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (isEmpty || restaurantId == null) {
        await prefs.remove('cart_draft');
        return;
      }
      final data = {
        'restaurant_id': restaurantId,
        'restaurant_name': restaurantName,
        'delivery_address': deliveryAddress,
        'lines': lines.map((l) => {'menu_item_id': l.item.id, 'quantity': l.quantity}).toList(),
      };
      await prefs.setString('cart_draft', jsonEncode(data));
    } catch (_) {}
  }

  void setRestaurant(String id, String name) {
    if (pendingIdempotencyKey != null) return;
    if (restaurantId != null && restaurantId != id) {
      lines.clear();
    }
    restaurantId = id;
    restaurantName = name;
    _saveDraft();
    notifyListeners();
  }

  void addItem(MenuItem item) {
    if (pendingIdempotencyKey != null) return;
    final existing = lines.where((l) => l.item.id == item.id).firstOrNull;
    if (existing != null) {
      if (existing.quantity < 20) existing.quantity++;
    } else {
      lines.add(CartLine(item: item));
    }
    _saveDraft();
    notifyListeners();
  }

  void updateQty(String menuItemId, int qty) {
    if (pendingIdempotencyKey != null) return;
    final idx = lines.indexWhere((l) => l.item.id == menuItemId);
    if (idx < 0) return;
    if (qty <= 0) {
      lines.removeAt(idx);
    } else {
      lines[idx].quantity = qty.clamp(1, 20);
    }
    _saveDraft();
    notifyListeners();
  }

  void remove(String menuItemId) {
    if (pendingIdempotencyKey != null) return;
    lines.removeWhere((l) => l.item.id == menuItemId);
    _saveDraft();
    notifyListeners();
  }

  void clear() {
    if (pendingIdempotencyKey != null) return;
    clearResolvedCheckout();
  }

  Future<void> clearResolvedCheckout() async {
    lines.clear();
    restaurantId = null;
    restaurantName = null;
    deliveryAddress = '';
    pendingIdempotencyKey = null;
    pendingRequest = null;
    await persistPendingCheckout();
    checkoutInProgress = false;
    checkoutError = null;
    checkoutRetryable = false;
    await _saveDraft();
    notifyListeners();
  }

  String generateIdempotencyKey() {
    final now = DateTime.now().microsecondsSinceEpoch;
    return 'qb-$now-${lines.length}';
  }

  Future<void> preparePendingCheckout(Map<String, dynamic> request) async {
    if (pendingIdempotencyKey != null && pendingRequest != null) {
      if (jsonEncode(pendingRequest) != jsonEncode(request)) {
        throw StateError('Resolve the pending checkout before changing its request.');
      }
      return;
    }
    pendingIdempotencyKey = generateIdempotencyKey();
    pendingRequest = jsonDecode(jsonEncode(request)) as Map<String, dynamic>;
    await persistPendingCheckout();
    notifyListeners();
  }

  Map<String, dynamic> buildRequest() {
    return {
      'restaurant_id': restaurantId,
      'delivery_address': deliveryAddress,
      'items': lines
          .map((l) => {'menu_item_id': l.item.id, 'quantity': l.quantity})
          .toList(),
    };
  }
}
