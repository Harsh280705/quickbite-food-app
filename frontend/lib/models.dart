class UserMe {
  final String id;
  final String email;
  final String fullName;
  final String role;
  UserMe({required this.id, required this.email, required this.fullName, required this.role});
  factory UserMe.fromJson(Map<String, dynamic> j) => UserMe(
        id: j['id'],
        email: j['email'],
        fullName: j['full_name'],
        role: j['role'],
      );
}

class Restaurant {
  final String id;
  final String name;
  final String description;
  final String cuisine;
  final int rating;
  final bool isActive;
  final bool acceptsOrders;
  final String? imageUrl;
  Restaurant({required this.id, required this.name, required this.description,
      required this.cuisine, required this.rating, required this.isActive,
      this.acceptsOrders = true, this.imageUrl});
  factory Restaurant.fromJson(Map<String, dynamic> j) => Restaurant(
        id: j['id'],
        name: j['name'],
        description: j['description'] ?? '',
        cuisine: j['cuisine'] ?? '',
        rating: j['rating'] ?? 0,
        isActive: j['is_active'] ?? true,
        acceptsOrders: j['accepts_orders'] ?? true,
        imageUrl: j['image_url'],
      );
}

class MenuItem {
  final String id;
  final String restaurantId;
  final String name;
  final String description;
  final int priceMinor;
  final String currency;
  final bool isAvailable;
  final bool isDiscontinued;
  final String? imageUrl;
  MenuItem({required this.id, required this.restaurantId, required this.name,
      required this.description, required this.priceMinor, required this.currency,
      required this.isAvailable, this.isDiscontinued = false, this.imageUrl});
  factory MenuItem.fromJson(Map<String, dynamic> j) => MenuItem(
        id: j['id'],
        restaurantId: j['restaurant_id'],
        name: j['name'],
        description: j['description'] ?? '',
        priceMinor: j['price_minor'],
        currency: j['currency'] ?? 'INR',
        isAvailable: j['is_available'] ?? true,
        isDiscontinued: j['is_discontinued'] ?? false,
        imageUrl: j['image_url'],
      );
  bool get isOrderable => isAvailable && !isDiscontinued;
}

class Page<T> {
  final List<T> items;
  final int page;
  final int pageSize;
  final int total;
  final bool hasMore;
  Page({required this.items, required this.page, required this.pageSize, required this.total, this.hasMore = false});
}

class OrderSummary {
  final String id;
  final String restaurantId;
  final String? restaurantName;
  final String? customerEmail;
  final String status;
  final int version;
  final String currency;
  final int totalAmountMinor;
  final String? failureCode;
  final String createdAt;
  final int itemCount;
  OrderSummary({required this.id, required this.restaurantId, this.restaurantName,
      this.customerEmail, required this.status, required this.version, required this.currency,
      required this.totalAmountMinor, this.failureCode, required this.createdAt,
      required this.itemCount});
  factory OrderSummary.fromJson(Map<String, dynamic> j) => OrderSummary(
        id: j['id'],
        restaurantId: j['restaurant_id'],
        restaurantName: j['restaurant_name'],
        customerEmail: j['customer_email'],
        status: j['status'],
        version: j['version'],
        currency: j['currency'],
        totalAmountMinor: j['total_amount_minor'],
        failureCode: j['failure_code'],
        createdAt: j['created_at'],
        itemCount: j['item_count'] ?? 0,
      );
}

class OrderItem {
  final String menuItemId;
  final String itemName;
  final int unitPriceMinor;
  final int quantity;
  final int lineTotalMinor;
  OrderItem({required this.menuItemId, required this.itemName, required this.unitPriceMinor,
      required this.quantity, required this.lineTotalMinor});
  factory OrderItem.fromJson(Map<String, dynamic> j) => OrderItem(
        menuItemId: j['menu_item_id'],
        itemName: j['item_name'],
        unitPriceMinor: j['unit_price_minor'],
        quantity: j['quantity'],
        lineTotalMinor: j['line_total_minor'],
      );
}

class OrderDetail {
  final String id;
  final String customerId;
  final String restaurantId;
  final String? restaurantName;
  final String deliveryAddress;
  final String currency;
  final int totalAmountMinor;
  final String status;
  final int version;
  final String? failureCode;
  final String? failureMessage;
  final String? driverId;
  final String? driverName;
  final String? driverVehicle;
  final String createdAt;
  final String updatedAt;
  final List<OrderItem> items;
  OrderDetail({required this.id, required this.customerId, required this.restaurantId,
      this.restaurantName, required this.deliveryAddress, required this.currency,
      required this.totalAmountMinor, required this.status, required this.version,
      this.failureCode, this.failureMessage, this.driverId, this.driverName,
      this.driverVehicle, required this.createdAt, required this.updatedAt,
      required this.items});
  factory OrderDetail.fromJson(Map<String, dynamic> j) => OrderDetail(
        id: j['id'],
        customerId: j['customer_id'],
        restaurantId: j['restaurant_id'],
        restaurantName: j['restaurant_name'],
        deliveryAddress: j['delivery_address'],
        currency: j['currency'],
        totalAmountMinor: j['total_amount_minor'],
        status: j['status'],
        version: j['version'],
        failureCode: j['failure_code'],
        failureMessage: j['failure_message'],
        driverId: j['driver_id'],
        driverName: j['driver_name'],
        driverVehicle: j['driver_vehicle'],
        createdAt: j['created_at'],
        updatedAt: j['updated_at'],
        items: (j['items'] as List? ?? [])
            .map((e) => OrderItem.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
      );
}

class HistoryEntry {
  final String? fromStatus;
  final String toStatus;
  final int version;
  final String actor;
  final String note;
  final String createdAt;
  HistoryEntry({this.fromStatus, required this.toStatus, required this.version,
      required this.actor, required this.note, required this.createdAt});
  factory HistoryEntry.fromJson(Map<String, dynamic> j) => HistoryEntry(
        fromStatus: j['from_status'],
        toStatus: j['to_status'],
        version: j['version'],
        actor: j['actor'],
        note: j['note'] ?? '',
        createdAt: j['created_at'],
      );
}

class Notification {
  final String id;
  final String? orderId;
  final String eventType;
  final String title;
  final String body;
  final String status;
  final String createdAt;
  Notification({required this.id, this.orderId, required this.eventType,
      required this.title, required this.body, required this.status,
      required this.createdAt});
  factory Notification.fromJson(Map<String, dynamic> j) => Notification(
        id: j['id'],
        orderId: j['order_id'],
        eventType: j['event_type'],
        title: j['title'],
        body: j['body'],
        status: j['status'],
        createdAt: j['created_at'],
      );
}

class CheckoutAccepted {
  final String orderId;
  final String status;
  final int totalAmountMinor;
  final String currency;
  final int version;
  final String detail;
  CheckoutAccepted({required this.orderId, required this.status,
      required this.totalAmountMinor, required this.currency, required this.version,
      required this.detail});
  factory CheckoutAccepted.fromJson(Map<String, dynamic> j) => CheckoutAccepted(
        orderId: j['order_id'],
        status: j['status'],
        totalAmountMinor: j['total_amount_minor'],
        currency: j['currency'],
        version: j['version'],
        detail: j['detail'] ?? '',
      );
}

class AdminSummary {
  final int totalOrders;
  final List<Map<String, dynamic>> statusCounts;
  final int pendingOutbox;
  final int pendingRetries;
  final int quarantined;
  AdminSummary({required this.totalOrders, required this.statusCounts,
      required this.pendingOutbox, required this.pendingRetries,
      required this.quarantined});
  factory AdminSummary.fromJson(Map<String, dynamic> j) => AdminSummary(
        totalOrders: j['total_orders'] ?? 0,
        statusCounts: (j['status_counts'] as List? ?? []).map((e) => Map<String, dynamic>.from(e)).toList(),
        pendingOutbox: j['pending_outbox'] ?? 0,
        pendingRetries: j['retry_backlog'] ?? 0,
        quarantined: j['quarantine_count'] ?? 0,
      );
}


class AdminAnalytics {
  final int totalOrders;
  final int totalCustomers;
  final int totalRestaurants;
    final int totalMenuItems;
    final int availableMenuItems;
    final int outOfStockMenuItems;
    final int discontinuedMenuItems;
    final int todayOrders;
    final List<Map<String, dynamic>> statusCounts;
  final int awaitingProcessing;
  final int paidOrders;
  final int confirmedOrders;
  final int driverAssignedOrders;
  final int failedOrders;
  final int paymentFailedOrders;
  final int quarantineCount;
  final int retryBacklog;
  final int pendingOutbox;
  final int processedEvents;
  final List<Map<String, dynamic>> activity;
  final String generatedAt;
  AdminAnalytics({
    required this.totalOrders,
    required this.totalCustomers,
    required this.totalRestaurants,
      required this.totalMenuItems,
      this.availableMenuItems = 0,
      this.outOfStockMenuItems = 0,
      this.discontinuedMenuItems = 0,
      this.todayOrders = 0,
      required this.statusCounts,
    required this.awaitingProcessing,
    required this.paidOrders,
    required this.confirmedOrders,
    required this.driverAssignedOrders,
    required this.failedOrders,
    required this.paymentFailedOrders,
    required this.quarantineCount,
    required this.retryBacklog,
    required this.pendingOutbox,
    required this.processedEvents,
    required this.activity,
    required this.generatedAt,
  });
  factory AdminAnalytics.fromJson(Map<String, dynamic> j) => AdminAnalytics(
        totalOrders: j['total_orders'] ?? 0,
        totalCustomers: j['total_customers'] ?? 0,
        totalRestaurants: j['total_restaurants'] ?? 0,
          totalMenuItems: j['total_menu_items'] ?? 0,
          availableMenuItems: j['available_menu_items'] ?? 0,
          outOfStockMenuItems: j['out_of_stock_menu_items'] ?? 0,
          discontinuedMenuItems: j['discontinued_menu_items'] ?? 0,
          todayOrders: j['today_orders'] ?? 0,
        statusCounts: (j['status_counts'] as List? ?? []).map((e) => Map<String, dynamic>.from(e)).toList(),
        awaitingProcessing: j['awaiting_processing'] ?? 0,
        paidOrders: j['paid_orders'] ?? 0,
        confirmedOrders: j['confirmed_orders'] ?? 0,
        driverAssignedOrders: j['driver_assigned_orders'] ?? 0,
        failedOrders: j['failed_orders'] ?? 0,
        paymentFailedOrders: j['payment_failed_orders'] ?? 0,
        quarantineCount: j['quarantine_count'] ?? 0,
        retryBacklog: j['retry_backlog'] ?? 0,
        pendingOutbox: j['pending_outbox'] ?? 0,
        processedEvents: j['processed_events'] ?? 0,
        activity: (j['activity'] as List? ?? []).map((e) => Map<String, dynamic>.from(e)).toList(),
        generatedAt: j['generated_at']?.toString() ?? '',
      );
}
