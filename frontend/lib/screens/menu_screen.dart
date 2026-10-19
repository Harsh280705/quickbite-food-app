import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/api_client.dart';
import '../config.dart';
import '../models.dart';
import '../state/cart.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

enum BrowseMode { pagination, infinite }

class MenuScreen extends StatefulWidget {
  const MenuScreen({super.key});
  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  static const int _pageSize = 12;

  Restaurant? restaurant;
  final _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  Timer? _searchDebounce;

  BrowseMode _mode = BrowseMode.pagination;
  String _search = '';
  List<MenuItem> _items = [];
  int _page = 1;
  int _total = 0;
  bool _hasMore = true;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;
  String? _moreError;
  int _requestToken = 0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _searchController.addListener(_scheduleSearch);
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final arg = ModalRoute.of(context)?.settings.arguments;
    if (arg is Restaurant && restaurant == null) {
      restaurant = arg;
      _restoreMode().then((_) => _fetch(reset: true));
    }
  }

  Future<void> _restoreMode() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('menu_browse_mode');
    if (saved == 'infinite') _mode = BrowseMode.infinite;
  }

  void _scheduleSearch() {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 300), () {
      final next = _searchController.text.trim();
      if (next == _search) return;
      _search = next;
      _resetAndFetch();
    });
  }

  void _resetAndFetch() {
    if (restaurant == null) return;
    setState(() {
      _page = 1;
      _items = [];
      _total = 0;
      _hasMore = true;
      _loadingMore = false;
      _moreError = null;
      _error = null;
      _loading = true;
    });
    _fetch(reset: true);
  }

  void _onScroll() {
    if (_mode != BrowseMode.infinite ||
        _loading ||
        _loadingMore ||
        !_hasMore ||
        restaurant == null)
      return;
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 240) {
      _fetch(reset: false, append: true);
    }
  }

  Future<void> _fetch({required bool reset, bool append = false}) async {
    if (restaurant == null) return;
    if (_loading && !reset) return;
    if (_loadingMore) return;
    if (append && (!_hasMore || _mode != BrowseMode.infinite)) return;

    final token = ++_requestToken;
    if (append) {
      setState(() {
        _loadingMore = true;
        _moreError = null;
      });
    } else {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final api = context.read<ApiClient>();
      final page = append ? _page + 1 : 1;
      final query = <String, dynamic>{
        'page': page,
        'page_size': _pageSize,
        'only_available': true,
      };
      if (_search.isNotEmpty) query['search'] = _search;
      final res = await api.get(
        '/restaurants/${restaurant!.id}/menu',
        query: query,
      );
      if (token != _requestToken || !mounted) return;
      final list = (res['items'] as List)
          .map((e) => MenuItem.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      final total = (res['total'] as num?)?.toInt() ?? 0;
      final hasMore = res['has_more'] == true || (page * _pageSize < total);
      setState(() {
        if (append) {
          final existing = _items.map((e) => e.id).toSet();
          _items.addAll(list.where((e) => !existing.contains(e.id)));
        } else {
          _items = list;
        }
        _page = page;
        _total = total;
        _hasMore = hasMore;
        _loading = false;
        _loadingMore = false;
        _error = null;
        _moreError = null;
      });
    } catch (e) {
      if (token != _requestToken || !mounted) return;
      setState(() {
        _loading = false;
        _loadingMore = false;
        if (append) {
          _moreError = e.toString();
        } else {
          _error = e.toString();
        }
      });
    }
  }

  Future<void> _setMode(BrowseMode mode) async {
    if (_mode == mode) return;
    setState(() {
      _mode = mode;
      _page = 1;
      _items = [];
      _total = 0;
      _hasMore = true;
      _loadingMore = false;
      _moreError = null;
      _error = null;
      _loading = true;
    });
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('menu_browse_mode', mode.name);
    if (mounted) _fetch(reset: true);
  }

  int get _totalPages =>
      _total <= 0 ? 1 : ((_total + _pageSize - 1) ~/ _pageSize);

  Future<void> _addToCart(MenuItem m) async {
    final cart = context.read<CartState>();
    if (cart.restaurantId != null &&
        cart.restaurantId != restaurant!.id &&
        cart.lines.isNotEmpty) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Start a new cart?'),
          content: Text(
            'Your cart has items from ${cart.restaurantName}. Adding this item will clear the current cart.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Clear and add'),
            ),
          ],
        ),
      );
      if (ok != true) return;
      cart.clear();
    }
    cart.setRestaurant(restaurant!.id, restaurant!.name);
    cart.addItem(m);
    if (mounted)
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('${m.name} added to cart')));
  }

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<CartState>();
    final compactAndroid = isCompactAndroid(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(restaurant?.name ?? 'Menu'),
        actions: [
          IconButton(
            tooltip: 'Cart',
            icon: Badge(
              label: Text('${cart.itemCount}'),
              child: const Icon(Icons.shopping_bag_outlined),
            ),
            onPressed: () => Navigator.pushNamed(context, '/cart'),
          ),
        ],
      ),
      body: restaurant == null
          ? const LoadingView()
          : _loading
          ? const LoadingView()
          : _error != null
          ? ErrorView(message: _error!, onRetry: () => _fetch(reset: true))
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        restaurant!.description,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        restaurant!.cuisine,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: AppSpacing.md),
                      TextField(
                        controller: _searchController,
                        decoration: const InputDecoration(
                          labelText: 'Search this menu',
                          prefixIcon: Icon(Icons.search),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      if (compactAndroid) ...[
                        Text(
                          'Browse mode',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        SizedBox(
                          width: double.infinity,
                          child: SegmentedButton<BrowseMode>(
                            showSelectedIcon: false,
                            segments: const [
                              ButtonSegment(
                                value: BrowseMode.pagination,
                                label: Text('Pagination'),
                                icon: Icon(Icons.view_list),
                              ),
                              ButtonSegment(
                                value: BrowseMode.infinite,
                                label: Text('Infinite scroll'),
                                icon: Icon(Icons.all_inclusive),
                              ),
                            ],
                            selected: {_mode},
                            onSelectionChanged: (selection) =>
                                _setMode(selection.first),
                          ),
                        ),
                      ] else
                        Row(
                          children: [
                            Text(
                              'Browse mode',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            SegmentedButton<BrowseMode>(
                              segments: const [
                                ButtonSegment(
                                  value: BrowseMode.pagination,
                                  label: Text('Pagination'),
                                  icon: Icon(Icons.view_list),
                                ),
                                ButtonSegment(
                                  value: BrowseMode.infinite,
                                  label: Text('Infinite scroll'),
                                  icon: Icon(Icons.all_inclusive),
                                ),
                              ],
                              selected: {_mode},
                              onSelectionChanged: (selection) =>
                                  _setMode(selection.first),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
                Expanded(
                  child: _mode == BrowseMode.pagination
                      ? _buildPagination()
                      : _buildInfinite(),
                ),
              ],
            ),
    );
  }

  Widget _buildPagination() {
    if (_items.isEmpty) {
      return const EmptyView(
        title: 'No menu items',
        subtitle: 'Try a different search.',
      );
    }
    return Column(
      children: [
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.all(AppSpacing.lg),
            itemCount: _items.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.md),
            itemBuilder: (_, i) {
              final m = _items[i];
              return AppCard(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Row(
                  children: [
                    Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        color: AppColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(AppRadii.md),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: _MenuImage(url: m.imageUrl),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            m.name,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          if (m.description.isNotEmpty)
                            Text(
                              m.description,
                              style: Theme.of(context).textTheme.bodySmall,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              PriceText(
                                minor: m.priceMinor,
                                currency: m.currency,
                                bold: true,
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              if (!m.isOrderable)
                                Text(
                                  m.isDiscontinued
                                      ? 'Discontinued'
                                      : 'Out of stock',
                                  style: const TextStyle(
                                    color: AppColors.error,
                                    fontSize: 12,
                                  ),
                                ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.add_circle_outline),
                      color: m.isOrderable
                          ? AppColors.accent
                          : AppColors.textSecondary,
                      onPressed: m.isOrderable ? () => _addToCart(m) : null,
                    ),
                  ],
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                onPressed: _page > 1 && !_loading
                    ? () {
                        setState(() {
                          _page -= 1;
                          _items = [];
                          _loading = true;
                        });
                        _fetch(reset: true);
                      }
                    : null,
                icon: const Icon(Icons.chevron_left),
              ),
              Text('Page $_page of $_totalPages'),
              IconButton(
                onPressed: _page < _totalPages && !_loading
                    ? () {
                        setState(() {
                          _page += 1;
                          _items = [];
                          _loading = true;
                        });
                        _fetch(reset: true);
                      }
                    : null,
                icon: const Icon(Icons.chevron_right),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInfinite() {
    if (_items.isEmpty && !_loadingMore) {
      return const EmptyView(
        title: 'No menu items',
        subtitle: 'Try a different search.',
      );
    }
    return ListView.separated(
      controller: _scrollController,
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: _items.length + 1,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.md),
      itemBuilder: (_, i) {
        if (i == _items.length) {
          if (_loadingMore) {
            return const Padding(
              padding: EdgeInsets.all(AppSpacing.lg),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          if (_moreError != null) {
            return Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Center(
                child: TextButton(
                  onPressed: () => _fetch(reset: false, append: true),
                  child: const Text('Retry'),
                ),
              ),
            );
          }
          if (!_hasMore && _items.isNotEmpty) {
            return const Padding(
              padding: EdgeInsets.all(AppSpacing.lg),
              child: Center(child: Text('End of results')),
            );
          }
          return const SizedBox.shrink();
        }
        final m = _items[i];
        return AppCard(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: AppColors.surfaceAlt,
                  borderRadius: BorderRadius.circular(AppRadii.md),
                ),
                clipBehavior: Clip.antiAlias,
                child: _MenuImage(url: m.imageUrl),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      m.name,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (m.description.isNotEmpty)
                      Text(
                        m.description,
                        style: Theme.of(context).textTheme.bodySmall,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        PriceText(
                          minor: m.priceMinor,
                          currency: m.currency,
                          bold: true,
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        if (!m.isOrderable)
                          Text(
                            m.isDiscontinued ? 'Discontinued' : 'Out of stock',
                            style: const TextStyle(
                              color: AppColors.error,
                              fontSize: 12,
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.add_circle_outline),
                color: m.isOrderable
                    ? AppColors.accent
                    : AppColors.textSecondary,
                onPressed: m.isOrderable ? () => _addToCart(m) : null,
              ),
            ],
          ),
        );
      },
    );
  }
}

class _MenuImage extends StatelessWidget {
  final String? url;
  const _MenuImage({required this.url});

  String? get _resolved {
    if (url == null || url!.isEmpty) return null;
    if (url!.startsWith('http')) return url;
    return '${AppConfig.apiBaseUrl}$url';
  }

  @override
  Widget build(BuildContext context) {
    final resolved = _resolved;
    if (resolved == null) {
      return const Center(
        child: Icon(Icons.fastfood, color: AppColors.textSecondary),
      );
    }
    return Image.network(
      resolved,
      fit: BoxFit.cover,
      width: 72,
      height: 72,
      loadingBuilder: (context, child, progress) {
        if (progress == null) return child;
        return const Center(
          child: SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        );
      },
      errorBuilder: (context, error, stack) {
        return const Center(
          child: Icon(Icons.fastfood, color: AppColors.textSecondary),
        );
      },
    );
  }
}
