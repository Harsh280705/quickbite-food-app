import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../config.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class AdminRestaurantsScreen extends StatefulWidget {
  final VoidCallback? onBack;
  const AdminRestaurantsScreen({super.key, this.onBack});
  @override
  State<AdminRestaurantsScreen> createState() => _AdminRestaurantsScreenState();
}

class _AdminRestaurantsScreenState extends State<AdminRestaurantsScreen> {
  List<Restaurant> _items = [];
  bool _loading = true;
  String? _error;
  final _search = TextEditingController();

  @override
  void initState() {
    super.initState();
    _search.addListener(() => setState(() {}));
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
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

  Future<void> _edit(Restaurant r) async {
    final name = TextEditingController(text: r.name);
    final desc = TextEditingController(text: r.description);
    final cuisine = TextEditingController(text: r.cuisine);
    final rating = TextEditingController(text: r.rating.toString());
    final image = TextEditingController(text: r.imageUrl ?? '');
    bool active = r.isActive;
    bool accepts = r.acceptsOrders;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSt) => AlertDialog(
          title: const Text('Edit restaurant'),
          content: SizedBox(
            width: isCompactAndroid(ctx)
                ? MediaQuery.sizeOf(ctx).width - 112
                : 420,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: name,
                    decoration: const InputDecoration(labelText: 'Name'),
                  ),
                  TextField(
                    controller: desc,
                    decoration: const InputDecoration(labelText: 'Description'),
                  ),
                  TextField(
                    controller: cuisine,
                    decoration: const InputDecoration(labelText: 'Cuisine'),
                  ),
                  TextField(
                    controller: rating,
                    decoration: const InputDecoration(
                      labelText: 'Rating (x100)',
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  TextField(
                    controller: image,
                    decoration: const InputDecoration(labelText: 'Image URL'),
                  ),
                  SwitchListTile(
                    title: const Text('Active'),
                    value: active,
                    onChanged: (v) => setSt(() => active = v),
                  ),
                  SwitchListTile(
                    title: const Text('Accepting orders'),
                    value: accepts,
                    onChanged: (v) => setSt(() => accepts = v),
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
    try {
      final api = context.read<ApiClient>();
      await api.patch(
        '/admin/restaurants/${r.id}',
        body: {
          'name': name.text.trim(),
          'description': desc.text.trim(),
          'cuisine': cuisine.text.trim(),
          'rating': int.tryParse(rating.text.trim()) ?? r.rating,
          'is_active': active,
          'accepts_orders': accepts,
          'image_url': image.text.trim().isEmpty ? null : image.text.trim(),
        },
      );
      if (mounted)
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Restaurant updated')));
      await _load();
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    final q = _search.text.trim().toLowerCase();
    final filtered = _items
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
        title: const Text('Restaurants'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const LoadingView()
          : _error != null
          ? ErrorView(message: _error!, onRetry: _load)
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
                                trailing: IconButton(
                                  icon: const Icon(Icons.edit),
                                  onPressed: () => _edit(r),
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
