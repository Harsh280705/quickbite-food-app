import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../config.dart';
import '../models.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class AdminHomeScreen extends StatefulWidget {
  final void Function(int index) onSelectTab;
  const AdminHomeScreen({super.key, required this.onSelectTab});
  @override
  State<AdminHomeScreen> createState() => _AdminHomeScreenState();
}

class _AdminHomeScreenState extends State<AdminHomeScreen> {
  AdminAnalytics? _analytics;
  List<Restaurant> _restaurants = [];
  Map<String, String> _restaurantNames = {};
  List<MenuItem> _menuItems = [];
  List<OrderSummary> _orders = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiClient>();
      final results = await Future.wait([
        api.get('/admin/analytics', query: {'days': 30}),
        api.get('/admin/restaurants', query: {'page': 1, 'page_size': 100}),
        api.get('/admin/menu-items', query: {'page': 1, 'page_size': 4}),
        api.get('/admin/orders', query: {'page': 1, 'page_size': 5}),
      ]);
      final restaurants = (results[1]['items'] as List)
          .map((e) => Restaurant.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      setState(() {
        _analytics = AdminAnalytics.fromJson(
          Map<String, dynamic>.from(results[0]),
        );
        _restaurants = restaurants.take(4).toList();
        _restaurantNames = {for (final r in restaurants) r.id: r.name};
        _menuItems = (results[2]['items'] as List)
            .map((e) => MenuItem.fromJson(Map<String, dynamic>.from(e)))
            .toList();
        _orders = (results[3]['items'] as List)
            .map((e) => OrderSummary.fromJson(Map<String, dynamic>.from(e)))
            .toList();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = _analytics;
    return Scaffold(
      backgroundColor: const Color(0xFFF4F7FC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text('Admin Home'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const LoadingView()
          : _error != null
          ? ErrorView(message: _error!, onRetry: _load)
          : SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Header(onRefresh: _load),
                  const SizedBox(height: AppSpacing.lg),
                  if (a != null) ...[
                    _KpiGrid(a: a),
                    const SizedBox(height: AppSpacing.lg),
                    LayoutBuilder(
                      builder: (context, c) {
                        final wide = c.maxWidth >= 980;
                        final activity = _activityChart(a);
                        final availability = _availabilityChart(a);
                        if (wide) {
                          return Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(flex: 3, child: activity),
                              const SizedBox(width: AppSpacing.lg),
                              Expanded(flex: 2, child: availability),
                            ],
                          );
                        }
                        return Column(
                          children: [
                            activity,
                            const SizedBox(height: AppSpacing.lg),
                            availability,
                          ],
                        );
                      },
                    ),
                    const SizedBox(height: AppSpacing.lg),
                  ],
                  LayoutBuilder(
                    builder: (context, c) {
                      final wide = c.maxWidth >= 980;
                      final restaurantPreview = _RestaurantPreview(
                        restaurants: _restaurants,
                        onTap: () => widget.onSelectTab(2),
                      );
                      final menuPreview = _MenuPreview(
                        items: _menuItems,
                        restaurantNames: _restaurantNames,
                        onTap: () => widget.onSelectTab(3),
                      );
                      if (wide) {
                        return Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(child: restaurantPreview),
                            const SizedBox(width: AppSpacing.lg),
                            Expanded(child: menuPreview),
                          ],
                        );
                      }
                      return Column(
                        children: [
                          restaurantPreview,
                          const SizedBox(height: AppSpacing.lg),
                          menuPreview,
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _RecentOrders(orders: _orders),
                  const SizedBox(height: AppSpacing.lg),
                  _QuickActions(onSelectTab: widget.onSelectTab),
                ],
              ),
            ),
    );
  }

  Widget _activityChart(AdminAnalytics a) {
    final points = <_Point>[];
    final counts = <String, int>{};
    for (final row in a.activity) {
      counts[row['date'].toString()] = (row['count'] as num).toInt();
    }
    final now = DateTime.now();
    for (var i = 29; i >= 0; i--) {
      final day = DateTime(
        now.year,
        now.month,
        now.day,
      ).subtract(Duration(days: i));
      final key = day.toIso8601String().substring(0, 10);
      points.add(_Point(day, counts[key] ?? 0));
    }
    final maxCount = points.fold<int>(0, (m, p) => p.count > m ? p.count : m);
    final total = points.fold<int>(0, (s, p) => s + p.count);
    return _Card(
      title: 'Order activity',
      subtitle: 'Daily accepted orders from persisted data.',
      child: total == 0
          ? const EmptyView(
              title: 'No recent activity',
              subtitle: 'Daily order counts will appear here.',
            )
          : SizedBox(
              height: 230,
              child: BarChart(
                BarChartData(
                  maxY: (maxCount + 1).toDouble(),
                  titlesData: FlTitlesData(
                    topTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false),
                    ),
                    rightTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false),
                    ),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 30,
                        getTitlesWidget: (v, m) => Text(
                          v.toInt().toString(),
                          style: const TextStyle(
                            fontSize: 10,
                            color: Color(0xFF6B6560),
                          ),
                        ),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 24,
                        getTitlesWidget: (v, m) {
                          final i = v.toInt();
                          if (i < 0 ||
                              i >= points.length ||
                              (i % 5 != 0 && i != points.length - 1))
                            return const SizedBox.shrink();
                          return Text(
                            '${points[i].day.month}/${points[i].day.day}',
                            style: const TextStyle(
                              fontSize: 10,
                              color: Color(0xFF6B6560),
                            ),
                          );
                        },
                      ),
                    ),
                  ),
                  borderData: FlBorderData(show: false),
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    horizontalInterval: maxCount > 5
                        ? (maxCount / 5).ceilToDouble()
                        : 1,
                  ),
                  barGroups: List.generate(
                    points.length,
                    (i) => BarChartGroupData(
                      x: i,
                      barRods: [
                        BarChartRodData(
                          toY: points[i].count.toDouble(),
                          color: const Color(0xFF3978D4),
                          width: 6,
                          borderRadius: const BorderRadius.vertical(
                            top: Radius.circular(3),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
    );
  }

  Widget _availabilityChart(AdminAnalytics a) {
    final sections = <PieChartSectionData>[];
    final colors = {
      'PENDING': const Color(0xFFB26A00),
      'PAID': const Color(0xFF3978D4),
      'CONFIRMED': const Color(0xFF2E7D32),
      'DRIVER_ASSIGNED': const Color(0xFF2E7D32),
      'PAYMENT_FAILED': const Color(0xFFC62828),
      'FAILED': const Color(0xFFC62828),
    };
    for (final s in a.statusCounts) {
      final status = s['status'].toString();
      final count = (s['count'] as int?) ?? 0;
      if (count > 0)
        sections.add(
          PieChartSectionData(
            value: count.toDouble(),
            color: colors[status] ?? const Color(0xFF3978D4),
            radius: 58,
            title: '',
          ),
        );
    }
    return _Card(
      title: 'Order status',
      subtitle: 'Persisted order distribution.',
      child: sections.isEmpty
          ? const EmptyView(
              title: 'No orders yet',
              subtitle: 'Status data will appear after orders are created.',
            )
          : SizedBox(
              height: 230,
              child: PieChart(
                PieChartData(
                  sections: sections,
                  centerSpaceRadius: 44,
                  sectionsSpace: 2,
                ),
              ),
            ),
    );
  }
}

class _Point {
  final DateTime day;
  final int count;
  const _Point(this.day, this.count);
}

class _Header extends StatelessWidget {
  final VoidCallback onRefresh;
  const _Header({required this.onRefresh});
  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Welcome back, Admin',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: const Color(0xFF183153),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Here is what is happening with QuickBite today.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: const Color(0xFF6B6560),
                ),
              ),
            ],
          ),
        ),
        Text(
          '${now.month}/${now.day}/${now.year}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(width: AppSpacing.md),
        IconButton(
          onPressed: onRefresh,
          icon: const Icon(Icons.refresh),
          tooltip: 'Refresh',
        ),
      ],
    );
  }
}

class _KpiGrid extends StatelessWidget {
  final AdminAnalytics a;
  const _KpiGrid({required this.a});
  @override
  Widget build(BuildContext context) {
    final compactAndroid = isCompactAndroid(context);
    final metrics = <_Metric>[
      _Metric(
        'Total restaurants',
        '${a.totalRestaurants}',
        Icons.storefront,
        const Color(0xFF3978D4),
      ),
      _Metric(
        'Menu items',
        '${a.totalMenuItems}',
        Icons.restaurant_menu,
        const Color(0xFF3978D4),
      ),
      _Metric(
        'Available dishes',
        '${a.availableMenuItems}',
        Icons.check_circle,
        const Color(0xFF2E7D32),
      ),
      _Metric(
        'Out of stock',
        '${a.outOfStockMenuItems}',
        Icons.remove_shopping_cart,
        const Color(0xFFB26A00),
      ),
      _Metric(
        'Discontinued',
        '${a.discontinuedMenuItems}',
        Icons.block,
        const Color(0xFFC62828),
      ),
      _Metric(
        "Today's orders",
        '${a.todayOrders}',
        Icons.receipt_long,
        const Color(0xFF3978D4),
      ),
    ];
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: compactAndroid
          ? const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: AppSpacing.md,
              crossAxisSpacing: AppSpacing.md,
              childAspectRatio: 1.8,
            )
          : const SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 230,
              mainAxisSpacing: AppSpacing.md,
              crossAxisSpacing: AppSpacing.md,
              childAspectRatio: 2.35,
            ),
      itemCount: metrics.length,
      itemBuilder: (_, i) => _MetricCard(metric: metrics[i]),
    );
  }
}

class _Metric {
  final String label;
  final String value;
  final IconData icon;
  final Color accent;
  const _Metric(this.label, this.value, this.icon, this.accent);
}

class _MetricCard extends StatelessWidget {
  final _Metric metric;
  const _MetricCard({required this.metric});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(AppRadii.lg),
        border: Border.all(color: const Color(0xFFDCE7F7)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: metric.accent.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(AppRadii.md),
            ),
            child: Icon(metric.icon, color: metric.accent, size: 20),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  metric.value,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: const Color(0xFF183153),
                  ),
                ),
                Text(
                  metric.label,
                  style: Theme.of(context).textTheme.bodySmall,
                  maxLines: isCompactAndroid(context) ? 2 : 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Card extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget child;
  const _Card({
    required this.title,
    required this.subtitle,
    required this.child,
  });
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(AppRadii.lg),
        border: Border.all(color: const Color(0xFFDCE7F7)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(color: const Color(0xFF183153)),
          ),
          const SizedBox(height: 2),
          Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: AppSpacing.md),
          child,
        ],
      ),
    );
  }
}

class _RestaurantPreview extends StatelessWidget {
  final List<Restaurant> restaurants;
  final VoidCallback onTap;
  const _RestaurantPreview({required this.restaurants, required this.onTap});
  @override
  Widget build(BuildContext context) {
    return _Card(
      title: 'Restaurant management',
      subtitle: 'Recently loaded restaurants.',
      child: Column(
        children: [
          if (restaurants.isEmpty)
            const EmptyView(
              title: 'No restaurants',
              subtitle: 'Restaurants will appear here.',
            )
          else
            ...restaurants.map((r) {
              final resolved = r.imageUrl == null
                  ? null
                  : (r.imageUrl!.startsWith('http')
                        ? r.imageUrl!
                        : '${AppConfig.apiBaseUrl}${r.imageUrl}');
              return Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(AppRadii.sm),
                      child: resolved == null
                          ? Container(
                              width: 44,
                              height: 44,
                              color: const Color(0xFFEAF3FF),
                              child: const Icon(Icons.storefront, size: 20),
                            )
                          : Image.network(
                              resolved,
                              width: 44,
                              height: 44,
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => Container(
                                width: 44,
                                height: 44,
                                color: const Color(0xFFEAF3FF),
                                child: const Icon(Icons.storefront, size: 20),
                              ),
                            ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            r.name,
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(fontWeight: FontWeight.w600),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            r.cuisine,
                            style: Theme.of(context).textTheme.bodySmall,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    _Badge(
                      label: r.acceptsOrders
                          ? (r.isActive ? 'Active' : 'Inactive')
                          : 'Paused',
                      color: r.acceptsOrders && r.isActive
                          ? const Color(0xFF2E7D32)
                          : const Color(0xFFB26A00),
                    ),
                  ],
                ),
              );
            }),
          const SizedBox(height: AppSpacing.sm),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: onTap,
              child: const Text('Manage restaurants'),
            ),
          ),
        ],
      ),
    );
  }
}

class _MenuPreview extends StatelessWidget {
  final List<MenuItem> items;
  final Map<String, String> restaurantNames;
  final VoidCallback onTap;
  const _MenuPreview({
    required this.items,
    required this.restaurantNames,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) {
    return _Card(
      title: 'Menu management',
      subtitle: 'Recently loaded dishes.',
      child: Column(
        children: [
          if (items.isEmpty)
            const EmptyView(
              title: 'No menu items',
              subtitle: 'Menu items will appear here.',
            )
          else
            ...items.map((m) {
              final resolved = m.imageUrl == null
                  ? null
                  : (m.imageUrl!.startsWith('http')
                        ? m.imageUrl!
                        : '${AppConfig.apiBaseUrl}${m.imageUrl}');
              return Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(AppRadii.sm),
                      child: resolved == null
                          ? Container(
                              width: 44,
                              height: 44,
                              color: const Color(0xFFEAF3FF),
                              child: const Icon(
                                Icons.restaurant_menu,
                                size: 20,
                              ),
                            )
                          : Image.network(
                              resolved,
                              width: 44,
                              height: 44,
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => Container(
                                width: 44,
                                height: 44,
                                color: const Color(0xFFEAF3FF),
                                child: const Icon(
                                  Icons.restaurant_menu,
                                  size: 20,
                                ),
                              ),
                            ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            m.name,
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(fontWeight: FontWeight.w600),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            restaurantNames[m.restaurantId] ??
                                'Restaurant menu item',
                            style: Theme.of(context).textTheme.bodySmall,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                    Text(
                      '${m.currency} ${(m.priceMinor / 100).toStringAsFixed(2)}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF183153),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    _Badge(
                      label: m.isDiscontinued
                          ? 'Discontinued'
                          : (m.isAvailable ? 'Available' : 'Out of stock'),
                      color: m.isDiscontinued
                          ? const Color(0xFFC62828)
                          : (m.isAvailable
                                ? const Color(0xFF2E7D32)
                                : const Color(0xFFB26A00)),
                    ),
                  ],
                ),
              );
            }),
          const SizedBox(height: AppSpacing.sm),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: onTap,
              child: const Text('Manage menu'),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecentOrders extends StatelessWidget {
  final List<OrderSummary> orders;
  const _RecentOrders({required this.orders});
  @override
  Widget build(BuildContext context) {
    return _Card(
      title: 'Recent orders',
      subtitle: 'Latest persisted order records.',
      child: orders.isEmpty
          ? const EmptyView(
              title: 'No orders yet',
              subtitle: 'Recent orders will appear here.',
            )
          : Column(
              children: orders
                  .map(
                    (o) => Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Order ${o.id.toString().substring(0, 8)}',
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(fontWeight: FontWeight.w600),
                            ),
                          ),
                          Text(
                            o.createdAt
                                .toString()
                                .substring(0, 16)
                                .replaceFirst('T', ' '),
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                          const SizedBox(width: AppSpacing.md),
                          PriceText(
                            minor: o.totalAmountMinor,
                            currency: o.currency,
                            bold: true,
                          ),
                          const SizedBox(width: AppSpacing.md),
                          _Badge(
                            label: o.status,
                            color:
                                o.status == 'DRIVER_ASSIGNED' ||
                                    o.status == 'PAID' ||
                                    o.status == 'CONFIRMED'
                                ? const Color(0xFF2E7D32)
                                : (o.status == 'PENDING'
                                      ? const Color(0xFFB26A00)
                                      : const Color(0xFFC62828)),
                          ),
                        ],
                      ),
                    ),
                  )
                  .toList(),
            ),
    );
  }
}

class _QuickActions extends StatelessWidget {
  final void Function(int index) onSelectTab;
  const _QuickActions({required this.onSelectTab});
  @override
  Widget build(BuildContext context) {
    return _Card(
      title: 'Quick actions',
      subtitle: 'Open the main admin workspaces.',
      child: Wrap(
        spacing: AppSpacing.md,
        runSpacing: AppSpacing.md,
        children: [
          _ActionChip(
            icon: Icons.analytics_outlined,
            label: 'Analytics',
            onTap: () => onSelectTab(1),
          ),
          _ActionChip(
            icon: Icons.storefront_outlined,
            label: 'Restaurants',
            onTap: () => onSelectTab(2),
          ),
          _ActionChip(
            icon: Icons.restaurant_menu_outlined,
            label: 'Menu',
            onTap: () => onSelectTab(3),
          ),
        ],
      ),
    );
  }
}

class _ActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _ActionChip({
    required this.icon,
    required this.label,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 18),
      label: Text(label),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;
  final Color color;
  const _Badge({required this.label, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
