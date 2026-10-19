import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../config.dart';
import '../models.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class OrderHistoryScreen extends StatefulWidget {
  const OrderHistoryScreen({super.key});
  @override
  State<OrderHistoryScreen> createState() => _OrderHistoryScreenState();
}

class _OrderHistoryScreenState extends State<OrderHistoryScreen> {
  List<OrderSummary> _items = [];
  final Map<String, String?> _restaurantImages = {};
  int _page = 1;
  int _total = 0;
  bool _loading = true;
  String? _error;
  String _filter = 'all';

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
      if (_restaurantImages.isEmpty) {
        final restaurantResponse = await api.get(
          '/restaurants',
          query: {'page': 1, 'page_size': 100},
        );
        for (final raw in restaurantResponse['items'] as List) {
          final item = Map<String, dynamic>.from(raw);
          _restaurantImages[item['id'].toString()] = item['image_url']
              ?.toString();
        }
      }
      final response = await api.get(
        '/orders',
        query: {'page': _page, 'page_size': 20},
      );
      final list = (response['items'] as List)
          .map((e) => OrderSummary.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      setState(() {
        _items = list;
        _total = response['total'];
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  List<OrderSummary> get _filteredItems {
    switch (_filter) {
      case 'in_progress':
        return _items
            .where(
              (o) =>
                  o.status == 'PENDING' ||
                  o.status == 'PAID' ||
                  o.status == 'CONFIRMED',
            )
            .toList();
      case 'completed':
        return _items.where((o) => o.status == 'DRIVER_ASSIGNED').toList();
      case 'failed':
        return _items
            .where((o) => o.status == 'PAYMENT_FAILED' || o.status == 'FAILED')
            .toList();
      default:
        return _items;
    }
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'DRIVER_ASSIGNED':
        return 'Driver assigned';
      case 'PAYMENT_FAILED':
        return 'Payment failed';
      case 'FAILED':
        return 'Failed';
      default:
        return status
            .replaceAll('_', ' ')
            .toLowerCase()
            .replaceRange(0, 1, status.substring(0, 1));
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'DRIVER_ASSIGNED':
        return AppColors.success;
      case 'PENDING':
      case 'PAID':
      case 'CONFIRMED':
        return AppColors.warning;
      case 'PAYMENT_FAILED':
      case 'FAILED':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }

  String _formatDate(String raw) {
    final dt = DateTime.tryParse(raw)?.toLocal();
    if (dt == null) return raw;
    final day = dt.day.toString().padLeft(2, '0');
    final month = dt.month.toString().padLeft(2, '0');
    final hour = dt.hour.toString().padLeft(2, '0');
    final minute = dt.minute.toString().padLeft(2, '0');
    return '$day/$month/${dt.year}, $hour:$minute';
  }

  String? _restaurantImage(String restaurantId) =>
      _restaurantImages[restaurantId];

  @override
  Widget build(BuildContext context) {
    final filtered = _filteredItems;
    final totalPages = (_total / 20).ceil().clamp(1, 999);
    final compactAndroid = isCompactAndroid(context);
    return Scaffold(
      appBar: AppBar(
        leading: Navigator.canPop(context) ? const BackButton() : null,
        title: const Text('Your Orders'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
        ],
      ),
      body: _loading
          ? const LoadingView()
          : _error != null
          ? ErrorView(message: _error!, onRetry: _load)
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.lg,
                    AppSpacing.lg,
                    AppSpacing.lg,
                    AppSpacing.sm,
                  ),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 920),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Track your orders and revisit your past purchases.',
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(color: AppColors.textSecondary),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        Wrap(
                          spacing: AppSpacing.sm,
                          runSpacing: AppSpacing.sm,
                          children: [
                            _FilterChip(
                              label: 'All',
                              selected: _filter == 'all',
                              onSelected: () => setState(() => _filter = 'all'),
                            ),
                            _FilterChip(
                              label: 'In progress',
                              selected: _filter == 'in_progress',
                              onSelected: () =>
                                  setState(() => _filter = 'in_progress'),
                            ),
                            _FilterChip(
                              label: 'Completed',
                              selected: _filter == 'completed',
                              onSelected: () =>
                                  setState(() => _filter = 'completed'),
                            ),
                            _FilterChip(
                              label: 'Payment failed',
                              selected: _filter == 'failed',
                              onSelected: () =>
                                  setState(() => _filter = 'failed'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  child: RefreshIndicator(
                    onRefresh: _load,
                    child: filtered.isEmpty
                        ? ListView(
                            children: [
                              const SizedBox(height: AppSpacing.xxl),
                              EmptyView(
                                title: _items.isEmpty
                                    ? 'No orders yet'
                                    : 'No matching orders',
                                subtitle: _items.isEmpty
                                    ? 'Your orders will appear here after checkout.'
                                    : 'Try another status filter.',
                                icon: Icons.receipt_long_outlined,
                              ),
                              if (_items.isEmpty) ...[
                                const SizedBox(height: AppSpacing.lg),
                                Center(
                                  child: SecondaryButton(
                                    label: 'Browse restaurants',
                                    icon: Icons.restaurant,
                                    onPressed: () => Navigator.pushNamed(
                                      context,
                                      '/restaurants',
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          )
                        : ListView.separated(
                            padding: const EdgeInsets.all(AppSpacing.lg),
                            itemCount: filtered.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: AppSpacing.md),
                            itemBuilder: (_, i) {
                              final o = filtered[i];
                              final imageUrl = _restaurantImage(o.restaurantId);
                              return Center(
                                child: ConstrainedBox(
                                  constraints: const BoxConstraints(
                                    maxWidth: 920,
                                  ),
                                  child: AppCard(
                                    padding: const EdgeInsets.all(
                                      AppSpacing.md,
                                    ),
                                    child: InkWell(
                                      borderRadius: BorderRadius.circular(
                                        AppRadii.lg,
                                      ),
                                      onTap: () => Navigator.pushNamed(
                                        context,
                                        '/order',
                                        arguments: o.id,
                                      ),
                                      child: compactAndroid
                                          ? Column(
                                              crossAxisAlignment:
                                                  CrossAxisAlignment.stretch,
                                              children: [
                                                Row(
                                                  crossAxisAlignment:
                                                      CrossAxisAlignment.start,
                                                  children: [
                                                    _RestaurantThumb(
                                                      imageUrl: imageUrl,
                                                    ),
                                                    const SizedBox(
                                                      width: AppSpacing.md,
                                                    ),
                                                    Expanded(
                                                      child: Column(
                                                        crossAxisAlignment:
                                                            CrossAxisAlignment
                                                                .start,
                                                        children: [
                                                          Text(
                                                            o.restaurantName ??
                                                                'Restaurant',
                                                            style:
                                                                Theme.of(
                                                                      context,
                                                                    )
                                                                    .textTheme
                                                                    .titleMedium,
                                                            softWrap: true,
                                                          ),
                                                          const SizedBox(
                                                            height:
                                                                AppSpacing.xs,
                                                          ),
                                                          Text(
                                                            'Order ${o.id.toString().substring(0, 8)}',
                                                            style:
                                                                Theme.of(
                                                                      context,
                                                                    )
                                                                    .textTheme
                                                                    .bodySmall,
                                                          ),
                                                          const SizedBox(
                                                            height: 2,
                                                          ),
                                                          Text(
                                                            _formatDate(
                                                              o.createdAt
                                                                  .toString(),
                                                            ),
                                                            style:
                                                                Theme.of(
                                                                      context,
                                                                    )
                                                                    .textTheme
                                                                    .bodySmall,
                                                          ),
                                                        ],
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                                const SizedBox(
                                                  height: AppSpacing.md,
                                                ),
                                                Wrap(
                                                  alignment: WrapAlignment
                                                      .spaceBetween,
                                                  crossAxisAlignment:
                                                      WrapCrossAlignment.center,
                                                  runSpacing: AppSpacing.sm,
                                                  children: [
                                                    _StatusBadge(
                                                      label: _statusLabel(
                                                        o.status,
                                                      ),
                                                      color: _statusColor(
                                                        o.status,
                                                      ),
                                                    ),
                                                    PriceText(
                                                      minor: o.totalAmountMinor,
                                                      currency: o.currency,
                                                      bold: true,
                                                    ),
                                                    SecondaryButton(
                                                      label: 'View',
                                                      onPressed: () =>
                                                          Navigator.pushNamed(
                                                            context,
                                                            '/order',
                                                            arguments: o.id,
                                                          ),
                                                    ),
                                                  ],
                                                ),
                                              ],
                                            )
                                          : Row(
                                              crossAxisAlignment:
                                                  CrossAxisAlignment.start,
                                              children: [
                                                _RestaurantThumb(
                                                  imageUrl: imageUrl,
                                                ),
                                                const SizedBox(
                                                  width: AppSpacing.md,
                                                ),
                                                Expanded(
                                                  child: Column(
                                                    crossAxisAlignment:
                                                        CrossAxisAlignment
                                                            .start,
                                                    children: [
                                                      Row(
                                                        children: [
                                                          Expanded(
                                                            child: Text(
                                                              o.restaurantName ??
                                                                  'Restaurant',
                                                              style:
                                                                  Theme.of(
                                                                        context,
                                                                      )
                                                                      .textTheme
                                                                      .titleMedium,
                                                              maxLines: 1,
                                                              overflow:
                                                                  TextOverflow
                                                                      .ellipsis,
                                                            ),
                                                          ),
                                                          const SizedBox(
                                                            width:
                                                                AppSpacing.sm,
                                                          ),
                                                          _StatusBadge(
                                                            label: _statusLabel(
                                                              o.status,
                                                            ),
                                                            color: _statusColor(
                                                              o.status,
                                                            ),
                                                          ),
                                                        ],
                                                      ),
                                                      const SizedBox(
                                                        height: AppSpacing.xs,
                                                      ),
                                                      Text(
                                                        'Order ${o.id.toString().substring(0, 8)}',
                                                        style: Theme.of(
                                                          context,
                                                        ).textTheme.bodySmall,
                                                      ),
                                                      const SizedBox(height: 2),
                                                      Text(
                                                        _formatDate(
                                                          o.createdAt
                                                              .toString(),
                                                        ),
                                                        style: Theme.of(
                                                          context,
                                                        ).textTheme.bodySmall,
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                                const SizedBox(
                                                  width: AppSpacing.md,
                                                ),
                                                Column(
                                                  crossAxisAlignment:
                                                      CrossAxisAlignment.end,
                                                  children: [
                                                    PriceText(
                                                      minor: o.totalAmountMinor,
                                                      currency: o.currency,
                                                      bold: true,
                                                    ),
                                                    const SizedBox(
                                                      height: AppSpacing.sm,
                                                    ),
                                                    SecondaryButton(
                                                      label: 'View',
                                                      onPressed: () =>
                                                          Navigator.pushNamed(
                                                            context,
                                                            '/order',
                                                            arguments: o.id,
                                                          ),
                                                    ),
                                                  ],
                                                ),
                                              ],
                                            ),
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 920),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        IconButton(
                          onPressed: _page > 1 && (!compactAndroid || !_loading)
                              ? () {
                                  _page--;
                                  _load();
                                }
                              : null,
                          icon: const Icon(Icons.chevron_left),
                          tooltip: 'Previous page',
                        ),
                        Text('Page $_page of $totalPages'),
                        IconButton(
                          onPressed:
                              (_page * 20 < _total) &&
                                  (!compactAndroid || !_loading)
                              ? () {
                                  _page++;
                                  _load();
                                }
                              : null,
                          icon: const Icon(Icons.chevron_right),
                          tooltip: 'Next page',
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onSelected;
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onSelected,
  });
  @override
  Widget build(BuildContext context) {
    return FilterChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onSelected(),
      showCheckmark: false,
      selectedColor: AppColors.accentSoft,
      labelStyle: TextStyle(
        color: selected ? AppColors.accent : AppColors.textPrimary,
        fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
      ),
      side: BorderSide(color: selected ? AppColors.accent : AppColors.border),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String label;
  final Color color;
  const _StatusBadge({required this.label, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _RestaurantThumb extends StatelessWidget {
  final String? imageUrl;
  const _RestaurantThumb({required this.imageUrl});
  @override
  Widget build(BuildContext context) {
    if (imageUrl == null || imageUrl!.isEmpty) {
      return Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          color: AppColors.surfaceAlt,
          borderRadius: BorderRadius.circular(AppRadii.md),
        ),
        child: const Icon(Icons.restaurant, color: AppColors.textSecondary),
      );
    }
    String resolved = imageUrl!;
    if (!resolved.startsWith('http'))
      resolved = '${AppConfig.apiBaseUrl}$resolved';
    return ClipRRect(
      borderRadius: BorderRadius.circular(AppRadii.md),
      child: Image.network(
        resolved,
        width: 52,
        height: 52,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => Container(
          width: 52,
          height: 52,
          color: AppColors.surfaceAlt,
          child: const Icon(Icons.restaurant, color: AppColors.textSecondary),
        ),
      ),
    );
  }
}
