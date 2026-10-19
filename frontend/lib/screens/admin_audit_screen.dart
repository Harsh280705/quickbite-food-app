import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class AdminAuditScreen extends StatefulWidget {
  const AdminAuditScreen({super.key});
  @override
  State<AdminAuditScreen> createState() => _AdminAuditScreenState();
}

class _AdminAuditScreenState extends State<AdminAuditScreen> {
  List<Map<String, dynamic>> _items = [];
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
      final res = await api.get('/admin/audit-logs', query: {'page': 1, 'page_size': 50});
      _items = (res['items'] as List).map((e) => Map<String, dynamic>.from(e)).toList();
      setState(() { _loading = false; });
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Audit log'), actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _load)]),
      body: _loading
          ? const LoadingView()
          : _error != null
              ? ErrorView(message: _error!, onRetry: _load)
              : _items.isEmpty
                  ? const EmptyView(title: 'No audit entries')
                  : ListView.separated(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      itemCount: _items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                      itemBuilder: (_, i) {
                        final e = _items[i];
                        return AppCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${e['entity_type']} ${e['action']}', style: Theme.of(context).textTheme.titleMedium),
                          Text('Entity: ${e['entity_id']}', style: Theme.of(context).textTheme.bodySmall),
                          Text('At: ${e['created_at']}', style: Theme.of(context).textTheme.bodySmall),
                        ]));
                      },
                    ),
    );
  }
}
