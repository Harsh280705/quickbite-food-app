import 'package:flutter/material.dart' hide Notification;
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../state/auth.dart';
import 'order_polling_controller.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class OrderDetailScreen extends StatefulWidget {
  const OrderDetailScreen({super.key});
  @override
  State<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends State<OrderDetailScreen>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  String? orderId;
  OrderDetail? order;
  List<HistoryEntry> history = [];
  List<Notification> notifications = [];
  bool loading = true;
  String? error;
  OrderPollingController? _poller;
  late final AnimationController _entrance;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _entrance = AnimationController(vsync: this, duration: const Duration(milliseconds: 320));
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final arg = ModalRoute.of(context)?.settings.arguments;
    if (arg is String && orderId == null) {
      orderId = arg;
      _startPolling();
      _startEntrance();
    } else if (arg is Map && orderId == null) {
      orderId = arg['id']?.toString();
      _startPolling();
      _startEntrance();
    }
  }

  void _startEntrance() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (MediaQuery.of(context).disableAnimations) {
        _entrance.value = 1;
      } else {
        _entrance.forward();
      }
    });
  }

  void _startPolling() {
    if (orderId == null) return;
    _poller ??= OrderPollingController(
      fetch: () => _load(silent: order != null),
      isTerminal: () => _isTerminal(order?.status) ||
          !context.read<AuthState>().isAuthenticated,
    );
    _poller!.start();
  }

  bool _isTerminal(String? status) =>
      status == 'DRIVER_ASSIGNED' || status == 'PAYMENT_FAILED' || status == 'FAILED';

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _poller?.resume();
    } else {
      _poller?.pause();
    }
  }

  Future<bool> _load({bool silent = false}) async {
    if (orderId == null || !mounted) return false;
    if (!context.read<AuthState>().isAuthenticated) {
      if (mounted) {
        setState(() {
          error = 'Your session expired. Please sign in to continue tracking this order.';
          loading = false;
        });
      }
      return false;
    }
    if (!silent) setState(() { loading = true; error = null; });
    try {
      final api = context.read<ApiClient>();
      final res = await api.get('/orders/$orderId');
      final h = await api.get('/orders/$orderId/history', query: {'page': 1, 'page_size': 50});
      final n = await api.get('/orders/$orderId/notifications', query: {'page': 1, 'page_size': 50});
      if (!mounted) return false;
      setState(() {
        order = OrderDetail.fromJson(Map<String, dynamic>.from(res));
        history = (h['items'] as List).map((e) => HistoryEntry.fromJson(Map<String, dynamic>.from(e))).toList();
        notifications = (n['items'] as List).map((e) => Notification.fromJson(Map<String, dynamic>.from(e))).toList();
        loading = false;
      });
      return true;
    } catch (e) {
      if (mounted) setState(() { error = e.toString(); loading = false; });
      return false;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _poller?.dispose();
    _entrance.dispose();
    super.dispose();
  }

  String _formatDate(String raw) {
    final dt = DateTime.tryParse(raw)?.toLocal();
    if (dt == null) return raw;
    final month = dt.month.toString().padLeft(2, '0');
    final day = dt.day.toString().padLeft(2, '0');
    final hour = dt.hour.toString().padLeft(2, '0');
    final minute = dt.minute.toString().padLeft(2, '0');
    return '$day/$month/${dt.year} $hour:$minute';
  }

  IconData _stageIcon(String status) {
    switch (status) {
      case 'PENDING':
        return Icons.receipt_long_outlined;
      case 'PAID':
        return Icons.payments_outlined;
      case 'CONFIRMED':
        return Icons.restaurant_outlined;
      case 'DRIVER_ASSIGNED':
        return Icons.delivery_dining_outlined;
      default:
        return Icons.info_outline;
    }
  }

  String _stageTitle(String status) {
    switch (status) {
      case 'PENDING':
        return 'Order received';
      case 'PAID':
        return 'Payment successful';
      case 'CONFIRMED':
        return 'Restaurant confirmed';
      case 'DRIVER_ASSIGNED':
        return 'Driver assigned';
      default:
        return status;
    }
  }

  String _stageDescription(String status) {
    switch (status) {
      case 'PENDING':
        return 'Your order has been accepted for processing.';
      case 'PAID':
        return 'Simulated payment completed successfully.';
      case 'CONFIRMED':
        return 'The restaurant accepted the order.';
      case 'DRIVER_ASSIGNED':
        return 'A simulated driver has been assigned.';
      default:
        return 'Order status updated.';
    }
  }

  int _rank(String status) {
    const ranks = {'PENDING': 0, 'PAID': 1, 'CONFIRMED': 2, 'DRIVER_ASSIGNED': 3};
    return ranks[status] ?? -1;
  }

  IconData _notificationIcon(String eventType) {
    if (eventType.contains('payment')) return Icons.payments_outlined;
    if (eventType.contains('driver')) return Icons.delivery_dining_outlined;
    if (eventType.contains('confirmed')) return Icons.restaurant_outlined;
    return Icons.notifications_outlined;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Order tracking'), actions: [
        IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: () => _load()),
      ]),
      body: loading
          ? const LoadingView()
          : error != null
              ? !context.watch<AuthState>().isAuthenticated
                  ? Center(
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                        Padding(padding: const EdgeInsets.all(AppSpacing.lg), child: Text(error!, textAlign: TextAlign.center)),
                        PrimaryButton(label: 'Sign in', icon: Icons.login, onPressed: () async {
                            await Navigator.pushNamed(context, '/login');
                            if (mounted && context.read<AuthState>().isAuthenticated) {
                              setState(() => error = null);
                              _poller?.resume();
                            }
                          }),
                      ]),
                    )
                  : ErrorView(message: error!, onRetry: () => _load())
              : order == null
                  ? const EmptyView(title: 'Order not found')
                  : FadeTransition(
                      opacity: CurvedAnimation(parent: _entrance, curve: Curves.easeOut),
                      child: SlideTransition(
                        position: Tween<Offset>(begin: const Offset(0, 0.03), end: Offset.zero).animate(CurvedAnimation(parent: _entrance, curve: Curves.easeOut)),
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(AppSpacing.lg),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            _SimulationBanner(),
                            const SizedBox(height: AppSpacing.lg),
                            _SummaryCard(order: order!, formatDate: _formatDate),
                            const SizedBox(height: AppSpacing.lg),
                            _TimelineCard(order: order!, history: history, rank: _rank, stageIcon: _stageIcon, stageTitle: _stageTitle, stageDescription: _stageDescription, formatDate: _formatDate),
                            const SizedBox(height: AppSpacing.lg),
                            _ItemsCard(order: order!),
                            const SizedBox(height: AppSpacing.lg),
                            if (order!.driverName != null || order!.status != 'DRIVER_ASSIGNED')
                              _DriverCard(order: order!),
                            if (order!.driverName != null || order!.status != 'DRIVER_ASSIGNED') const SizedBox(height: AppSpacing.lg),
                            _NotificationsCard(notifications: notifications, formatDate: _formatDate, iconFor: _notificationIcon),
                            const SizedBox(height: AppSpacing.lg),
                          ]),
                        ),
                      ),
                    ),
    );
  }
}

class _SimulationBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(AppRadii.md), border: Border.all(color: AppColors.border)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('Learning Demo · Simulated Order Processing', style: Theme.of(context).textTheme.titleSmall?.copyWith(color: AppColors.accent))),
        ]),
        const SizedBox(height: AppSpacing.xs),
        Text('Payment, restaurant confirmation, driver assignment, and notifications are simulated.', style: Theme.of(context).textTheme.bodySmall),
      ]),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final OrderDetail order;
  final String Function(String) formatDate;
  const _SummaryCard({required this.order, required this.formatDate});
  @override
  Widget build(BuildContext context) {
    return AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Expanded(child: Text('Order ${order.id.substring(0, 8)}', style: Theme.of(context).textTheme.headlineSmall)),
        StatusChip(status: order.status),
      ]),
      const SizedBox(height: AppSpacing.sm),
      Text(order.restaurantName ?? 'Restaurant', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: AppSpacing.xs),
      Text('Created ${formatDate(order.createdAt)}', style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: AppSpacing.md),
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text('Total', style: Theme.of(context).textTheme.titleMedium),
        PriceText(minor: order.totalAmountMinor, currency: order.currency, bold: true),
      ]),
      if (order.failureMessage != null) ...[
        const SizedBox(height: AppSpacing.sm),
        Text(order.failureMessage!, style: const TextStyle(color: AppColors.error)),
      ],
    ]));
  }
}

class _TimelineCard extends StatelessWidget {
  final OrderDetail order;
  final List<HistoryEntry> history;
  final int Function(String) rank;
  final IconData Function(String) stageIcon;
  final String Function(String) stageTitle;
  final String Function(String) stageDescription;
  final String Function(String) formatDate;
  const _TimelineCard({required this.order, required this.history, required this.rank, required this.stageIcon, required this.stageTitle, required this.stageDescription, required this.formatDate});
  @override
  Widget build(BuildContext context) {
    const stages = ['PENDING', 'PAID', 'CONFIRMED', 'DRIVER_ASSIGNED'];
    final currentRank = rank(order.status);
    final failure = order.status == 'PAYMENT_FAILED' || order.status == 'FAILED';
    return AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Order progress', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: AppSpacing.md),
      ...List.generate(stages.length, (index) {
        final stage = stages[index];
        final stageRank = index;
        final completed = !failure && (history.any((h) => h.toStatus == stage) || currentRank > stageRank);
        final current = !failure && order.status == stage;
        final color = completed || current ? AppColors.success : AppColors.textSecondary;
        return Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.md),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Column(children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(color: color.withValues(alpha: current ? 0.18 : 0.10), shape: BoxShape.circle, border: Border.all(color: color)),
                child: Icon(stageIcon(stage), size: 18, color: color),
              ),
              if (index < stages.length - 1)
                Container(width: 2, height: 34, color: completed ? AppColors.success : AppColors.border),
            ]),
            const SizedBox(width: AppSpacing.md),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                child: Text(stageTitle(stage), key: ValueKey('$stage-$current'), style: Theme.of(context).textTheme.titleSmall?.copyWith(color: current ? AppColors.accent : null)),
              ),
              const SizedBox(height: 2),
              Text(stageDescription(stage), style: Theme.of(context).textTheme.bodySmall),
              if (history.any((h) => h.toStatus == stage))
                Text(formatDate(history.firstWhere((h) => h.toStatus == stage).createdAt), style: Theme.of(context).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600)),
            ])),
          ]),
        );
      }),
      if (failure) ...[
        const SizedBox(height: AppSpacing.sm),
        Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(color: AppColors.error.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(AppRadii.md), border: Border.all(color: AppColors.error)),
          child: Row(children: [
            const Icon(Icons.error_outline, color: AppColors.error),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: Text(order.failureMessage ?? 'Processing failed.', style: const TextStyle(color: AppColors.error))),
          ]),
        ),
      ],
      if (history.isNotEmpty) ...[
        const SizedBox(height: AppSpacing.md),
        Text('Processing events', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: AppSpacing.sm),
        ...history.map((h) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Row(children: [
                const Icon(Icons.circle, size: 8, color: AppColors.accent),
                const SizedBox(width: AppSpacing.sm),
                Expanded(child: Text('${h.toStatus} (v${h.version}) â€” ${h.note}')),
                Text(formatDate(h.createdAt), style: Theme.of(context).textTheme.bodySmall),
              ]),
            )),
      ],
    ]));
  }
}

class _ItemsCard extends StatelessWidget {
  final OrderDetail order;
  const _ItemsCard({required this.order});
  @override
  Widget build(BuildContext context) {
    return AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Order items', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: AppSpacing.md),
      ...order.items.map((i) => Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: Row(children: [
              Container(width: 36, height: 36, decoration: BoxDecoration(color: AppColors.surfaceAlt, borderRadius: BorderRadius.circular(AppRadii.md)), child: const Icon(Icons.fastfood, size: 18, color: AppColors.textSecondary)),
              const SizedBox(width: AppSpacing.md),
              Expanded(child: Text(i.itemName, style: Theme.of(context).textTheme.titleSmall)),
              Text('${i.quantity} × ${(i.unitPriceMinor / 100).toStringAsFixed(2)}', style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(width: AppSpacing.md),
              PriceText(minor: i.lineTotalMinor, currency: order.currency, bold: true),
            ]),
          )),
      const Divider(),
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text('Total', style: Theme.of(context).textTheme.titleMedium),
        PriceText(minor: order.totalAmountMinor, currency: order.currency, bold: true),
      ]),
    ]));
  }
}

class _DriverCard extends StatelessWidget {
  final OrderDetail order;
  const _DriverCard({required this.order});
  @override
  Widget build(BuildContext context) {
    final assigned = order.driverName != null;
    return AppCard(child: Row(children: [
      Container(width: 48, height: 48, decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(AppRadii.md)), child: const Icon(Icons.delivery_dining, color: AppColors.accent)),
      const SizedBox(width: AppSpacing.md),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Simulated driver assignment', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: AppSpacing.xs),
        if (assigned) ...[
          Text(order.driverName!, style: Theme.of(context).textTheme.titleSmall),
          if (order.driverVehicle != null) Text(order.driverVehicle!, style: Theme.of(context).textTheme.bodySmall),
          Text('Assigned driver information is simulated.', style: Theme.of(context).textTheme.bodySmall),
        ] else
          Text('Waiting for simulated driver assignment', style: Theme.of(context).textTheme.bodySmall),
      ])),
    ]));
  }
}

class _NotificationsCard extends StatelessWidget {
  final List<Notification> notifications;
  final String Function(String) formatDate;
  final IconData Function(String) iconFor;
  const _NotificationsCard({required this.notifications, required this.formatDate, required this.iconFor});
  @override
  Widget build(BuildContext context) {
    return AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Persisted notifications', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: AppSpacing.md),
      if (notifications.isEmpty)
        const EmptyView(title: 'No notifications yet', subtitle: 'Order updates will appear here.', icon: Icons.notifications_none)
      else
        ...notifications.map((n) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: Container(
                padding: const EdgeInsets.all(AppSpacing.md),
                decoration: BoxDecoration(color: AppColors.surfaceAlt, borderRadius: BorderRadius.circular(AppRadii.md)),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Icon(iconFor(n.eventType), color: AppColors.accent),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Expanded(child: Text(n.title, style: Theme.of(context).textTheme.titleSmall)),
                      Text(formatDate(n.createdAt), style: Theme.of(context).textTheme.bodySmall),
                    ]),
                    const SizedBox(height: 2),
                    Text(n.body, style: Theme.of(context).textTheme.bodySmall),
                  ])),
                ]),
              ),
            )),
    ]));
  }
}
