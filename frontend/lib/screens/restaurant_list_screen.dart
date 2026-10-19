import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/api_client.dart';
import '../config.dart';
import '../models.dart';
import '../state/auth.dart';
import '../state/cart.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

enum BrowseMode { pagination, infinite }

SliverGridDelegate restaurantGridDelegate([double? availableWidth]) =>
    availableWidth != null && availableWidth < 600
    ? const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 1,
        crossAxisSpacing: AppSpacing.lg,
        mainAxisSpacing: AppSpacing.lg,
        childAspectRatio: 1.22,
      )
    : const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 360,
        crossAxisSpacing: AppSpacing.lg,
        mainAxisSpacing: AppSpacing.lg,
        childAspectRatio: 1.22,
      );

class RestaurantListScreen extends StatefulWidget {
  const RestaurantListScreen({super.key});
  @override
  State<RestaurantListScreen> createState() => _RestaurantListScreenState();
}

class _RestaurantListScreenState extends State<RestaurantListScreen> {
  static const int _pageSize = 12;

  final _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  Timer? _searchDebounce;

  BrowseMode _mode = BrowseMode.pagination;
  String _search = '';
  String? _cuisine;
  List<Restaurant> _items = [];
  List<String> _cuisineOptions = [];
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
    _restoreMode().then((_) {
      _loadCuisines();
      _fetch(reset: true);
    });
  }

  Future<void> _restoreMode() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('restaurant_browse_mode');
    if (saved == 'infinite') _mode = BrowseMode.infinite;
  }

  Future<void> _loadCuisines() async {
    try {
      final api = context.read<ApiClient>();
      final res = await api.get(
        '/restaurants',
        query: {'page': 1, 'page_size': 100},
      );
      final list = (res['items'] as List)
          .map((e) => Restaurant.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      if (!mounted) return;
      setState(() {
        _cuisineOptions = (list.map((r) => r.cuisine).toSet().toList()..sort());
      });
    } catch (_) {}
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
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
    if (_mode != BrowseMode.infinite || _loading || _loadingMore || !_hasMore) {
      return;
    }
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 240) {
      _fetch(reset: false, append: true);
    }
  }

  Future<void> _fetch({
    required bool reset,
    bool append = false,
    int? requestedPage,
  }) async {
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
      final page = append ? _page + 1 : requestedPage ?? 1;
      final query = <String, dynamic>{'page': page, 'page_size': _pageSize};
      if (_search.isNotEmpty) query['search'] = _search;
      if (_cuisine != null) query['cuisine'] = _cuisine;
      final res = await api.get('/restaurants', query: query);
      if (token != _requestToken || !mounted) return;
      final list = (res['items'] as List)
          .map((e) => Restaurant.fromJson(Map<String, dynamic>.from(e)))
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
    await prefs.setString('restaurant_browse_mode', mode.name);
    if (mounted) _fetch(reset: true);
  }

  int get _totalPages =>
      _total <= 0 ? 1 : ((_total + _pageSize - 1) ~/ _pageSize);

  void _goToPage(int page) {
    if (_loading || page < 1 || page > _totalPages || page == _page) return;
    setState(() {
      _page = page;
      _items = [];
      _loading = true;
      _error = null;
    });
    _fetch(reset: true, requestedPage: page);
  }

  List<String> get _cuisines => _cuisineOptions;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final cart = context.watch<CartState>();
    final compactAndroid = isCompactAndroid(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('QuickBite'),
        actions: compactAndroid
            ? [
                IconButton(
                  tooltip: 'Cart',
                  icon: Badge(
                    label: Text('${cart.itemCount}'),
                    child: const Icon(Icons.shopping_bag_outlined),
                  ),
                  onPressed: () => Navigator.pushNamed(context, '/cart'),
                ),
                PopupMenuButton<String>(
                  tooltip: 'More options',
                  onSelected: (value) => _selectCompactAction(value, auth),
                  itemBuilder: (_) => [
                    if (auth.isAuthenticated) ...[
                      const PopupMenuItem(
                        value: 'history',
                        child: Text('Order history'),
                      ),
                      const PopupMenuItem(
                        value: 'notifications',
                        child: Text('Notifications'),
                      ),
                      if (auth.user?.role == 'admin')
                        const PopupMenuItem(
                          value: 'admin',
                          child: Text('Admin'),
                        ),
                      const PopupMenuItem(
                        value: 'logout',
                        child: Text('Sign out'),
                      ),
                    ] else ...[
                      const PopupMenuItem(
                        value: 'login',
                        child: Text('Sign in'),
                      ),
                      const PopupMenuItem(
                        value: 'signup',
                        child: Text('Sign up'),
                      ),
                    ],
                  ],
                ),
              ]
            : [
                Padding(
                  padding: const EdgeInsets.only(right: AppSpacing.sm),
                  child: SegmentedButton<BrowseMode>(
                    showSelectedIcon: false,
                    segments: const [
                      ButtonSegment(
                        value: BrowseMode.pagination,
                        label: Text('Pagination'),
                        icon: Icon(Icons.view_list, size: 16),
                      ),
                      ButtonSegment(
                        value: BrowseMode.infinite,
                        label: Text('Infinite scroll'),
                        icon: Icon(Icons.all_inclusive, size: 16),
                      ),
                    ],
                    selected: {_mode},
                    onSelectionChanged: (selection) =>
                        _setMode(selection.first),
                  ),
                ),
                IconButton(
                  tooltip: 'Cart',
                  icon: Badge(
                    label: Text('${cart.itemCount}'),
                    child: const Icon(Icons.shopping_bag_outlined),
                  ),
                  onPressed: () => Navigator.pushNamed(context, '/cart'),
                ),
                if (auth.isAuthenticated) ...[
                  IconButton(
                    tooltip: 'Order history',
                    icon: const Icon(Icons.receipt_long_outlined),
                    onPressed: () => Navigator.pushNamed(context, '/history'),
                  ),
                  IconButton(
                    tooltip: 'Notifications',
                    icon: const Icon(Icons.notifications_outlined),
                    onPressed: () =>
                        Navigator.pushNamed(context, '/notifications'),
                  ),
                  if (auth.user?.role == 'admin')
                    IconButton(
                      tooltip: 'Admin',
                      icon: const Icon(Icons.admin_panel_settings_outlined),
                      onPressed: () => Navigator.pushNamed(context, '/admin'),
                    ),
                  PopupMenuButton<String>(
                    onSelected: (v) {
                      if (v == 'logout') {
                        auth.logout();
                        Navigator.pushReplacementNamed(context, '/login');
                      }
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'logout', child: Text('Sign out')),
                    ],
                  ),
                ] else ...[
                  TextButton(
                    onPressed: () => Navigator.pushNamed(context, '/login'),
                    child: const Text('Sign in'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pushNamed(context, '/signup'),
                    child: const Text('Sign up'),
                  ),
                ],
              ],
      ),
      body: _loading
          ? const LoadingView()
          : _error != null
          ? ErrorView(
              message: _error!,
              onRetry: () => _fetch(reset: true, requestedPage: _page),
            )
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.lg,
                    AppSpacing.lg,
                    AppSpacing.lg,
                    AppSpacing.sm,
                  ),
                  child: TextField(
                    controller: _searchController,
                    decoration: const InputDecoration(
                      labelText: 'Search restaurants or cuisines',
                      prefixIcon: Icon(Icons.search),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.sm),
                SizedBox(
                  height: 44,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.lg,
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(right: AppSpacing.sm),
                        child: FilterChip(
                          label: const Text('All'),
                          selected: _cuisine == null,
                          onSelected: (_) {
                            _cuisine = null;
                            _resetAndFetch();
                          },
                        ),
                      ),
                      ..._cuisines.map(
                        (c) => Padding(
                          padding: const EdgeInsets.only(right: AppSpacing.sm),
                          child: FilterChip(
                            label: Text(c),
                            selected: _cuisine == c,
                            onSelected: (_) {
                              _cuisine = _cuisine == c ? null : c;
                              _resetAndFetch();
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                if (compactAndroid)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.lg,
                      AppSpacing.sm,
                      AppSpacing.lg,
                      0,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
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
                                icon: Icon(Icons.view_list, size: 16),
                              ),
                              ButtonSegment(
                                value: BrowseMode.infinite,
                                label: Text('Infinite scroll'),
                                icon: Icon(Icons.all_inclusive, size: 16),
                              ),
                            ],
                            selected: {_mode},
                            onSelectionChanged: (selection) =>
                                _setMode(selection.first),
                          ),
                        ),
                      ],
                    ),
                  ),
                Expanded(
                  child: _mode == BrowseMode.pagination
                      ? _buildPagination(context)
                      : _buildInfinite(context),
                ),
              ],
            ),
    );
  }

  void _selectCompactAction(String value, AuthState auth) {
    switch (value) {
      case 'history':
        Navigator.pushNamed(context, '/history');
        return;
      case 'notifications':
        Navigator.pushNamed(context, '/notifications');
        return;
      case 'admin':
        Navigator.pushNamed(context, '/admin');
        return;
      case 'login':
        Navigator.pushNamed(context, '/login');
        return;
      case 'signup':
        Navigator.pushNamed(context, '/signup');
        return;
      case 'logout':
        auth.logout();
        Navigator.pushReplacementNamed(context, '/login');
        return;
    }
  }

  Widget _buildPagination(BuildContext context) {
    if (_items.isEmpty) {
      return const EmptyView(
        title: 'No restaurants found',
        subtitle: 'Try a different search or category.',
      );
    }
    return Column(
      children: [
        Expanded(
          child: GridView.builder(
            padding: const EdgeInsets.all(AppSpacing.lg),
            gridDelegate: restaurantGridDelegate(
              isCompactAndroid(context)
                  ? MediaQuery.sizeOf(context).width
                  : null,
            ),
            itemCount: _items.length,
            itemBuilder: (_, i) => _RestaurantCard(restaurant: _items[i]),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                tooltip: 'Previous page',
                onPressed: _page > 1 && !_loading
                    ? () => _goToPage(_page - 1)
                    : null,
                icon: const Icon(Icons.chevron_left),
              ),
              Text('Page $_page of $_totalPages'),
              IconButton(
                tooltip: 'Next page',
                onPressed: _page < _totalPages && !_loading
                    ? () => _goToPage(_page + 1)
                    : null,
                icon: const Icon(Icons.chevron_right),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInfinite(BuildContext context) {
    if (_items.isEmpty && !_loadingMore) {
      return const EmptyView(
        title: 'No restaurants found',
        subtitle: 'Try a different search or category.',
      );
    }
    return CustomScrollView(
      controller: _scrollController,
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          sliver: SliverGrid(
            gridDelegate: restaurantGridDelegate(
              isCompactAndroid(context)
                  ? MediaQuery.sizeOf(context).width
                  : null,
            ),
            delegate: SliverChildBuilderDelegate(
              (context, index) => _RestaurantCard(
                key: ValueKey(_items[index].id),
                restaurant: _items[index],
              ),
              childCount: _items.length,
            ),
          ),
        ),
        if (_loadingMore ||
            _moreError != null ||
            (!_hasMore && _items.isNotEmpty))
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                0,
                AppSpacing.lg,
                AppSpacing.lg,
              ),
              child: SizedBox(
                height: 48,
                child: Center(
                  child: _loadingMore
                      ? const SizedBox.square(
                          dimension: 24,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : _moreError != null
                      ? TextButton(
                          onPressed: () => _fetch(reset: false, append: true),
                          child: const Text('Retry loading restaurants'),
                        )
                      : const Text('End of results'),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _RestaurantCard extends StatelessWidget {
  final Restaurant restaurant;
  const _RestaurantCard({super.key, required this.restaurant});
  @override
  Widget build(BuildContext context) {
    final rating = (restaurant.rating / 100).toStringAsFixed(1);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () =>
            Navigator.pushNamed(context, '/menu', arguments: restaurant),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AspectRatio(
              aspectRatio: 1.88,
              child: Container(
                color: AppColors.surfaceAlt,
                child: _RestaurantImage(url: restaurant.imageUrl),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    restaurant.name,
                    style: Theme.of(context).textTheme.titleMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    restaurant.cuisine,
                    style: Theme.of(context).textTheme.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(
                        Icons.star,
                        size: 14,
                        color: AppColors.warning,
                      ),
                      const SizedBox(width: 2),
                      Text(
                        rating,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const Spacer(),
                      if (!restaurant.isActive)
                        const Text(
                          'Closed',
                          style: TextStyle(
                            color: AppColors.error,
                            fontSize: 12,
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RestaurantImage extends StatelessWidget {
  final String? url;
  const _RestaurantImage({required this.url});

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
        child: Icon(Icons.restaurant, size: 48, color: AppColors.textSecondary),
      );
    }
    return Image.network(
      resolved,
      fit: BoxFit.cover,
      width: double.infinity,
      loadingBuilder: (context, child, progress) {
        if (progress == null) return child;
        return const Center(child: CircularProgressIndicator(strokeWidth: 2));
      },
      errorBuilder: (context, error, stack) {
        return const Center(
          child: Icon(
            Icons.restaurant,
            size: 48,
            color: AppColors.textSecondary,
          ),
        );
      },
    );
  }
}
