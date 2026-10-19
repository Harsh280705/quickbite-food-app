import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class AdminOrdersScreen extends StatefulWidget {
  final VoidCallback? onBack;
  const AdminOrdersScreen({super.key, this.onBack});
  @override
  State<AdminOrdersScreen> createState() => _AdminOrdersScreenState();
}

class _AdminOrdersScreenState extends State<AdminOrdersScreen> {
  List<OrderSummary> _items = [];
  AdminAnalytics? _analytics;
  String? _statusFilter;
  int _page = 1;
  int _total = 0;
  bool _loading = true;
  String? _error;
  DateTime? _lastUpdated;

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
      final q = <String, dynamic>{'page': _page, 'page_size': 20};
      if (_statusFilter != null) q['status'] = _statusFilter;
      final res = await api.get('/admin/orders', query: q);
      final list = (res['items'] as List)
          .map((e) => OrderSummary.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      final a = await api.get('/admin/analytics', query: {'days': 30});
      setState(() {
        _items = list;
        _total = res['total'];
        _analytics = AdminAnalytics.fromJson(Map<String, dynamic>.from(a));
        _loading = false;
        _lastUpdated = DateTime.now();
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'DRIVER_ASSIGNED':
      case 'PAID':
      case 'CONFIRMED':
        return AppColors.success;
      case 'PENDING':
        return AppColors.warning;
      case 'PAYMENT_FAILED':
      case 'FAILED':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }

  List<_ActivityPoint> _activityPoints(AdminAnalytics a) {
    final counts = <String, int>{};
    for (final row in a.activity) {
      counts[row['date'].toString()] = (row['count'] as num).toInt();
    }
    final now = DateTime.now();
    final points = <_ActivityPoint>[];
    for (var i = 29; i >= 0; i--) {
      final day = DateTime(
        now.year,
        now.month,
        now.day,
      ).subtract(Duration(days: i));
      final key = day.toIso8601String().substring(0, 10);
      points.add(_ActivityPoint(day: day, count: counts[key] ?? 0));
    }
    return points;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: widget.onBack == null
            ? null
            : BackButton(onPressed: widget.onBack),
        title: const Text('Admin Analytics'),
        actions: [
          IconButton(
            tooltip: 'Refresh dashboard',
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
        ],
      ),
      body: _loading
          ? const LoadingView()
          : _error != null
          ? ErrorView(message: _error!, onRetry: _load)
          : LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 980;
                final analytics = _analytics!;
                final points = _activityPoints(analytics);
                return SingleChildScrollView(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _Header(
                        lastUpdated: _lastUpdated,
                        filter: _statusFilter,
                        onFilterChanged: (v) {
                          _statusFilter = v;
                          _page = 1;
                          _load();
                        },
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      _KpiGrid(analytics: analytics),
                      const SizedBox(height: AppSpacing.lg),
                      if (wide)
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: _StatusCard(
                                analytics: analytics,
                                statusColor: _statusColor,
                              ),
                            ),
                            const SizedBox(width: AppSpacing.lg),
                            Expanded(child: _ActivityCard(points: points)),
                          ],
                        )
                      else
                        Column(
                          children: [
                            _StatusCard(
                              analytics: analytics,
                              statusColor: _statusColor,
                            ),
                            const SizedBox(height: AppSpacing.lg),
                            _ActivityCard(points: points),
                          ],
                        ),
                      const SizedBox(height: AppSpacing.lg),
                      _OrdersCard(
                        items: _items,
                        total: _total,
                        page: _page,
                        statusFilter: _statusFilter,
                        onFilterChanged: (v) {
                          _statusFilter = v;
                          _page = 1;
                          _load();
                        },
                        onPrevious: _page > 1
                            ? () {
                                _page--;
                                _load();
                              }
                            : null,
                        onNext: (_page * 20 < _total)
                            ? () {
                                _page++;
                                _load();
                              }
                            : null,
                      ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}

class _Header extends StatelessWidget {
  final DateTime? lastUpdated;
  final String? filter;
  final ValueChanged<String?> onFilterChanged;
  const _Header({
    required this.lastUpdated,
    required this.filter,
    required this.onFilterChanged,
  });
  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Admin Analytics',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'A summary of QuickBite order activity, operational status, and processing health.',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: AppSpacing.md),
          Wrap(
            spacing: AppSpacing.md,
            runSpacing: AppSpacing.sm,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              DropdownButton<String?>(
                value: filter,
                hint: const Text('All statuses'),
                items:
                    [
                          null,
                          'PENDING',
                          'PAID',
                          'CONFIRMED',
                          'DRIVER_ASSIGNED',
                          'PAYMENT_FAILED',
                          'FAILED',
                        ]
                        .map(
                          (s) => DropdownMenuItem(
                            value: s,
                            child: Text(s ?? 'All statuses'),
                          ),
                        )
                        .toList(),
                onChanged: onFilterChanged,
              ),
              if (lastUpdated != null)
                Text(
                  'Last updated: ${lastUpdated!.toIso8601String().substring(0, 19).replaceFirst('T', ' ')}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _KpiGrid extends StatelessWidget {
  final AdminAnalytics analytics;
  const _KpiGrid({required this.analytics});
  @override
  Widget build(BuildContext context) {
    final compactAndroid = isCompactAndroid(context);
    final metrics = <_Metric>[
      _Metric(
        'Total orders',
        '${analytics.totalOrders}',
        Icons.receipt_long,
        AppColors.textPrimary,
      ),
      _Metric(
        'Customers',
        '${analytics.totalCustomers}',
        Icons.people,
        AppColors.textPrimary,
      ),
      _Metric(
        'Restaurants',
        '${analytics.totalRestaurants}',
        Icons.storefront,
        AppColors.textPrimary,
      ),
      _Metric(
        'Menu items',
        '${analytics.totalMenuItems}',
        Icons.restaurant_menu,
        AppColors.textPrimary,
      ),
      _Metric(
        'Awaiting processing',
        '${analytics.awaitingProcessing}',
        Icons.hourglass_top,
        AppColors.warning,
      ),
      _Metric(
        'Driver assigned',
        '${analytics.driverAssignedOrders}',
        Icons.delivery_dining,
        AppColors.success,
      ),
      _Metric(
        'Payment failed',
        '${analytics.paymentFailedOrders}',
        Icons.payment,
        AppColors.error,
      ),
      _Metric(
        'Failed',
        '${analytics.failedOrders}',
        Icons.error_outline,
        AppColors.error,
      ),
      _Metric(
        'Quarantined',
        '${analytics.quarantineCount}',
        Icons.block,
        AppColors.error,
      ),
      _Metric(
        'Retry backlog',
        '${analytics.retryBacklog}',
        Icons.refresh,
        AppColors.warning,
      ),
      _Metric(
        'Pending outbox',
        '${analytics.pendingOutbox}',
        Icons.outbox,
        AppColors.warning,
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
              childAspectRatio: 1.7,
            )
          : const SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 250,
              mainAxisSpacing: AppSpacing.md,
              crossAxisSpacing: AppSpacing.md,
              childAspectRatio: 2.05,
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
    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
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
                  metric.label,
                  style: Theme.of(context).textTheme.bodySmall,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  metric.value,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final AdminAnalytics analytics;
  final Color Function(String) statusColor;
  const _StatusCard({required this.analytics, required this.statusColor});
  @override
  Widget build(BuildContext context) {
    final total = analytics.totalOrders;
    final sections = analytics.statusCounts
        .where((s) => (s['count'] as int? ?? 0) > 0)
        .map((s) {
          final status = s['status'].toString();
          final count = (s['count'] as int?) ?? 0;
          return PieChartSectionData(
            value: count.toDouble(),
            color: statusColor(status),
            title: '',
            radius: 62,
            showTitle: false,
          );
        })
        .toList();
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Order status distribution',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Actual persisted order statuses.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.md),
          if (sections.isEmpty)
            const EmptyView(
              title: 'No orders yet',
              subtitle: 'Status data will appear after orders are created.',
            )
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final sideBySide = constraints.maxWidth >= 520;
                final chart = SizedBox(
                  height: 230,
                  child: PieChart(
                    PieChartData(
                      sections: sections,
                      centerSpaceRadius: 46,
                      sectionsSpace: 2,
                      pieTouchData: PieTouchData(enabled: true),
                    ),
                  ),
                );
                final legend = Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: analytics.statusCounts.map((s) {
                    final status = s['status'].toString();
                    final count = (s['count'] as int?) ?? 0;
                    final percent = total == 0 ? 0 : (count / total * 100);
                    return Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: Row(
                        children: [
                          Container(
                            width: 12,
                            height: 12,
                            decoration: BoxDecoration(
                              color: statusColor(status),
                              borderRadius: BorderRadius.circular(3),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Text(
                              status,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ),
                          Text(
                            '$count',
                            style: Theme.of(context).textTheme.bodySmall
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          SizedBox(
                            width: 46,
                            child: Text(
                              '${percent.toStringAsFixed(1)}%',
                              textAlign: TextAlign.right,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                );
                if (sideBySide) {
                  return Row(
                    children: [
                      Expanded(child: chart),
                      const SizedBox(width: AppSpacing.lg),
                      Expanded(child: legend),
                    ],
                  );
                }
                return Column(
                  children: [
                    chart,
                    const SizedBox(height: AppSpacing.md),
                    legend,
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}

class _ActivityPoint {
  final DateTime day;
  final int count;
  const _ActivityPoint({required this.day, required this.count});
}

class _ActivityCard extends StatelessWidget {
  final List<_ActivityPoint> points;
  const _ActivityCard({required this.points});
  @override
  Widget build(BuildContext context) {
    final maxCount = points.fold<int>(0, (m, p) => p.count > m ? p.count : m);
    final total = points.fold<int>(0, (s, p) => s + p.count);
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Order activity, last 30 days',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Daily accepted orders from persisted data.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.md),
          if (total == 0)
            const EmptyView(
              title: 'No recent activity',
              subtitle: 'Daily order counts will appear here.',
            )
          else
            SizedBox(
              height: 250,
              child: BarChart(
                BarChartData(
                  maxY: (maxCount + 1).toDouble(),
                  barTouchData: BarTouchData(
                    enabled: true,
                    touchTooltipData: BarTouchTooltipData(
                      getTooltipItem: (group, groupIndex, rod, rodIndex) {
                        final point = points[group.x.toInt()];
                        return BarTooltipItem(
                          '${point.day.month}/${point.day.day}\n${point.count} orders',
                          const TextStyle(color: Colors.white, fontSize: 12),
                        );
                      },
                    ),
                  ),
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
                        reservedSize: 34,
                        getTitlesWidget: (value, meta) => Text(
                          value.toInt().toString(),
                          style: const TextStyle(
                            fontSize: 10,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 28,
                        getTitlesWidget: (value, meta) {
                          final index = value.toInt();
                          if (index < 0 || index >= points.length)
                            return const SizedBox.shrink();
                          if (index % 5 != 0 && index != points.length - 1)
                            return const SizedBox.shrink();
                          final day = points[index].day;
                          return Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              '${day.month}/${day.day}',
                              style: const TextStyle(
                                fontSize: 10,
                                color: AppColors.textSecondary,
                              ),
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
                    (index) => BarChartGroupData(
                      x: index,
                      barRods: [
                        BarChartRodData(
                          toY: points[index].count.toDouble(),
                          color: AppColors.accent,
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
        ],
      ),
    );
  }
}

class _OrdersCard extends StatelessWidget {
  final List<OrderSummary> items;
  final int total;
  final int page;
  final String? statusFilter;
  final ValueChanged<String?> onFilterChanged;
  final VoidCallback? onPrevious;
  final VoidCallback? onNext;
  const _OrdersCard({
    required this.items,
    required this.total,
    required this.page,
    required this.statusFilter,
    required this.onFilterChanged,
    required this.onPrevious,
    required this.onNext,
  });
  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'Recent orders',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text(
                '$total total',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Paginated order records with status filtering.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.md),
          if (items.isEmpty)
            const EmptyView(
              title: 'No orders',
              subtitle: 'Orders will appear here once customers place them.',
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: items.length,
              separatorBuilder: (_, __) =>
                  const Divider(height: 1, color: AppColors.border),
              itemBuilder: (_, i) {
                final o = items[i];
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Order ${o.id.toString().substring(0, 8)}',
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                          ),
                          StatusChip(status: o.status),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        o.customerEmail ?? 'Customer',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              o.createdAt
                                  .toString()
                                  .substring(0, 16)
                                  .replaceFirst('T', ' '),
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ),
                          PriceText(
                            minor: o.totalAmountMinor,
                            currency: o.currency,
                            bold: true,
                          ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            ),
          const SizedBox(height: AppSpacing.md),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                onPressed: onPrevious,
                icon: const Icon(Icons.chevron_left),
              ),
              Text('Page $page'),
              IconButton(
                onPressed: onNext,
                icon: const Icon(Icons.chevron_right),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
