import 'package:flutter/material.dart' hide Notification;
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<Notification> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final api = context.read<ApiClient>();
      final res = await api.get('/notifications', query: {'page': 1, 'page_size': 50});
      final list = (res['items'] as List).map((e) => Notification.fromJson(Map<String, dynamic>.from(e))).toList();
      setState(() { _items = list; _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: _loading
          ? const LoadingView()
          : _error != null
              ? ErrorView(message: _error!, onRetry: _load)
              : _items.isEmpty
                  ? const EmptyView(title: 'No notifications', subtitle: 'Order updates will appear here.')
                  : ListView.separated(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      itemCount: _items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                      itemBuilder: (_, i) {
                        final n = _items[i];
                        return AppCard(
                          padding: const EdgeInsets.all(AppSpacing.md),
                          child: Row(children: [
                            Container(
                              width: 40, height: 40,
                              decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(AppRadii.md)),
                              child: const Icon(Icons.notifications_outlined, color: AppColors.accent),
                            ),
                            const SizedBox(width: AppSpacing.md),
                            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(n.title, style: Theme.of(context).textTheme.titleMedium),
                              Text(n.body, style: Theme.of(context).textTheme.bodySmall),
                              Text(n.createdAt.substring(0, 16).replaceFirst('T', ' '), style: Theme.of(context).textTheme.bodySmall),
                            ])),
                            StatusChip(status: n.status),
                          ]),
                        );
                      },
                    ),
    );
  }
}
