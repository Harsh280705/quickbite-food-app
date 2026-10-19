import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../config.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class AdminMenuScreen extends StatefulWidget {
  final VoidCallback? onBack;
  const AdminMenuScreen({super.key, this.onBack});
  @override
  State<AdminMenuScreen> createState() => _AdminMenuScreenState();
}

class _AdminMenuScreenState extends State<AdminMenuScreen> {
  List<Restaurant> _restaurants = [];
  List<MenuItem> _items = [];
  Restaurant? _selected;
  bool _loading = true;
  String? _error;
  final _search = TextEditingController();

  @override
  void initState() {
    super.initState();
    _search.addListener(() => setState(() {}));
    _loadRestaurants();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _loadRestaurants() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiClient>();
      final res = await api.get(
        '/admin/restaurants',
        query: {'page': 1, 'page_size': 100},
      );
      final list = (res['items'] as List)
          .map((e) => Restaurant.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      setState(() {
        _restaurants = list;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _selectRestaurant(Restaurant r) async {
    setState(() {
      _selected = r;
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiClient>();
      final res = await api.get(
        '/admin/menu-items',
        query: {'restaurant_id': r.id, 'page': 1, 'page_size': 100},
      );
      final list = (res['items'] as List)
          .map((e) => MenuItem.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      setState(() {
        _items = list;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _saveItem({MenuItem? existing}) async {
    final r = _selected;
    if (r == null) return;
    final name = TextEditingController(text: existing?.name ?? '');
    final desc = TextEditingController(text: existing?.description ?? '');
    final price = TextEditingController(
      text: existing != null
          ? (existing.priceMinor / 100).toStringAsFixed(2)
          : '',
    );
    final image = TextEditingController(text: existing?.imageUrl ?? '');
    bool available = existing?.isAvailable ?? true;
    bool discontinued = existing?.isDiscontinued ?? false;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSt) => AlertDialog(
          title: Text(existing == null ? 'New menu item' : 'Edit menu item'),
          content: SizedBox(
            width: isCompactAndroid(ctx)
                ? MediaQuery.sizeOf(ctx).width - 112
                : 460,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Restaurant: ${r.name}',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  TextField(
                    controller: name,
                    decoration: const InputDecoration(labelText: 'Name'),
                  ),
                  TextField(
                    controller: desc,
                    decoration: const InputDecoration(labelText: 'Description'),
                  ),
                  TextField(
                    controller: price,
                    decoration: const InputDecoration(labelText: 'Price (INR)'),
                    keyboardType: TextInputType.number,
                  ),
                  TextField(
                    controller: image,
                    decoration: const InputDecoration(labelText: 'Image URL'),
                  ),
                  SwitchListTile(
                    title: const Text('Available'),
                    value: available,
                    onChanged: (v) => setSt(() => available = v),
                  ),
                  SwitchListTile(
                    title: const Text('Discontinued'),
                    value: discontinued,
                    onChanged: (v) => setSt(() => discontinued = v),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    if (ok != true) return;
    final priceMinor = ((double.tryParse(price.text.trim()) ?? 0) * 100)
        .round();
    try {
      final api = context.read<ApiClient>();
      final body = {
        'restaurant_id': r.id,
        'name': name.text.trim(),
        'description': desc.text.trim(),
        'price_minor': priceMinor,
        'is_available': available,
        'is_discontinued': discontinued,
        'image_url': image.text.trim().isEmpty ? null : image.text.trim(),
      };
      if (existing == null) {
        await api.post('/admin/menu-items', body: body);
      } else {
        await api.patch('/admin/menu-items/${existing.id}', body: body);
      }
      if (mounted)
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Menu item saved')));
      await _selectRestaurant(r);
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _quick(MenuItem m, {bool? available, bool? discontinued}) async {
    try {
      final api = context.read<ApiClient>();
      final body = <String, dynamic>{};
      if (available != null) body['is_available'] = available;
      if (discontinued != null) body['is_discontinued'] = discontinued;
      await api.patch('/admin/menu-items/${m.id}', body: body);
      await _selectRestaurant(_selected!);
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_selected == null) {
      final q = _search.text.trim().toLowerCase();
      final filtered = _restaurants
          .where(
            (r) =>
                q.isEmpty ||
                r.name.toLowerCase().contains(q) ||
                r.cuisine.toLowerCase().contains(q),
          )
          .toList();
      return Scaffold(
        appBar: AppBar(
          leading: widget.onBack == null
              ? null
              : BackButton(onPressed: widget.onBack),
          title: const Text('Menu Management'),
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _loadRestaurants,
            ),
          ],
        ),
        body: _loading
            ? const LoadingView()
            : _error != null
            ? ErrorView(message: _error!, onRetry: _loadRestaurants)
            : Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    child: TextField(
                      controller: _search,
                      decoration: const InputDecoration(
                        labelText: 'Search restaurants',
                        prefixIcon: Icon(Icons.search),
                      ),
                    ),
                  ),
                  Expanded(
                    child: filtered.isEmpty
                        ? const EmptyView(title: 'No restaurants')
                        : ListView.separated(
                            padding: const EdgeInsets.all(AppSpacing.lg),
                            itemCount: filtered.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: AppSpacing.sm),
                            itemBuilder: (_, i) {
                              final r = filtered[i];
                              return AppCard(
                                child: ListTile(
                                  leading: CircleAvatar(
                                    radius: 20,
                                    backgroundColor: AppColors.accentSoft,
                                    child: Stack(
                                      alignment: Alignment.center,
                                      children: [
                                        Text(
                                          r.name.substring(0, 1),
                                          style: TextStyle(
                                            color: Theme.of(context).colorScheme.onPrimaryContainer,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                        if (r.imageUrl != null && r.imageUrl!.isNotEmpty)
                                          ClipOval(
                                            child: Image.network(
                                              r.imageUrl!.startsWith('http')
                                                  ? r.imageUrl!
                                                  : '${AppConfig.apiBaseUrl}${r.imageUrl}',
                                              width: 40,
                                              height: 40,
                                              fit: BoxFit.cover,
                                              errorBuilder: (context, error, stackTrace) =>
                                                  const SizedBox.shrink(),
                                            ),
                                          ),
                                      ],
                                    ),
                                  ),
                                  title: Text(r.name),
                                  subtitle: Text(
                                    '${r.cuisine} • ${r.isActive ? 'Active' : 'Inactive'} • ${r.acceptsOrders ? 'Accepting orders' : 'Paused'}',
                                  ),
                                  trailing: const Icon(Icons.chevron_right),
                                  onTap: () => _selectRestaurant(r),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),
      );
    }

    final q = _search.text.trim().toLowerCase();
    final filtered = _items
        .where((m) => q.isEmpty || m.name.toLowerCase().contains(q))
        .toList();
    return Scaffold(
      appBar: AppBar(
        leading: BackButton(
          onPressed: () => setState(() {
            _selected = null;
            _items = [];
          }),
        ),
        title: Text('Menu: ${_selected!.name}'),
        actions: [
          IconButton(icon: const Icon(Icons.add), onPressed: () => _saveItem()),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _selectRestaurant(_selected!),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    '${_selected!.cuisine} • ${_selected!.isActive ? 'Active' : 'Inactive'}',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
                Text(
                  '${_items.length} items',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: TextField(
              controller: _search,
              decoration: const InputDecoration(
                labelText: 'Search dishes',
                prefixIcon: Icon(Icons.search),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Expanded(
            child: _loading
                ? const LoadingView()
                : _error != null
                ? ErrorView(
                    message: _error!,
                    onRetry: () => _selectRestaurant(_selected!),
                  )
                : filtered.isEmpty
                ? const EmptyView(title: 'No menu items')
                : ListView.separated(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    itemCount: filtered.length,
                    separatorBuilder: (_, __) =>
                        const SizedBox(height: AppSpacing.sm),
                    itemBuilder: (_, i) {
                      final m = filtered[i];
                      return AppCard(
                        child: ListTile(
                           leading: CircleAvatar(
                             radius: 20,
                             backgroundColor: AppColors.accentSoft,
                             child: Stack(
                               alignment: Alignment.center,
                               children: [
                                 Text(
                                   m.name.substring(0, 1),
                                   style: TextStyle(
                                     color: Theme.of(context).colorScheme.onPrimaryContainer,
                                     fontWeight: FontWeight.w600,
                                   ),
                                 ),
                                 if (m.imageUrl != null && m.imageUrl!.isNotEmpty)
                                   ClipOval(
                                     child: Image.network(
                                       m.imageUrl!.startsWith('http')
                                           ? m.imageUrl!
                                           : '${AppConfig.apiBaseUrl}${m.imageUrl}',
                                       width: 40,
                                       height: 40,
                                       fit: BoxFit.cover,
                                       errorBuilder: (context, error, stackTrace) =>
                                           const SizedBox.shrink(),
                                     ),
                                   ),
                               ],
                             ),
                           ),
                          title: Text(m.name),
                          subtitle: Text(
                            '${m.currency} ${(m.priceMinor / 100).toStringAsFixed(2)} • ${m.isDiscontinued ? 'Discontinued' : (m.isAvailable ? 'Available' : 'Out of stock')}',
                          ),
                          trailing: PopupMenuButton<String>(
                            onSelected: (v) {
                              if (v == 'edit') _saveItem(existing: m);
                              if (v == 'oos') _quick(m, available: false);
                              if (v == 'avail') _quick(m, available: true);
                              if (v == 'disc') _quick(m, discontinued: true);
                              if (v == 'react') _quick(m, discontinued: false);
                            },
                            itemBuilder: (_) => const [
                              PopupMenuItem(value: 'edit', child: Text('Edit')),
                              PopupMenuItem(
                                value: 'oos',
                                child: Text('Mark out of stock'),
                              ),
                              PopupMenuItem(
                                value: 'avail',
                                child: Text('Restore availability'),
                              ),
                              PopupMenuItem(
                                value: 'disc',
                                child: Text('Discontinue'),
                              ),
                              PopupMenuItem(
                                value: 'react',
                                child: Text('Reactivate'),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
