import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/auth.dart';
import 'admin_home_screen.dart';
import 'admin_orders_screen.dart';
import 'admin_restaurants_screen.dart';
import 'admin_menu_screen.dart';

class AdminShell extends StatefulWidget {
  const AdminShell({super.key});
  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> {
  int _index = 0;
  final List<int> _history = <int>[];

  void _selectTab(int i) {
    if (i == _index) return;
    _history.add(_index);
    setState(() => _index = i);
  }

  void _goBack() {
    if (_history.isNotEmpty) {
      setState(() => _index = _history.removeLast());
    } else {
      setState(() => _index = 0);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    if (!auth.isAuthenticated || auth.user?.role != 'admin') {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Navigator.of(context).pushReplacementNamed('/login');
      });
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final isWide = MediaQuery.of(context).size.width >= 900;
    final pages = [
      AdminHomeScreen(onSelectTab: _selectTab),
      AdminOrdersScreen(onBack: _goBack),
      AdminRestaurantsScreen(onBack: _goBack),
      AdminMenuScreen(onBack: _goBack),
    ];
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) _goBack();
      },
      child: Scaffold(
      body: Row(children: [
        if (isWide)
          NavigationRail(
            selectedIndex: _index,
            onDestinationSelected: _selectTab,
            labelType: NavigationRailLabelType.all,
            destinations: const [
              NavigationRailDestination(icon: Icon(Icons.home_outlined), label: Text('Home')),
              NavigationRailDestination(icon: Icon(Icons.analytics_outlined), label: Text('Analytics')),
              NavigationRailDestination(icon: Icon(Icons.storefront_outlined), label: Text('Restaurants')),
              NavigationRailDestination(icon: Icon(Icons.restaurant_menu_outlined), label: Text('Menu')),
            ],
          ),
        Expanded(child: pages[_index]),
      ]),
      bottomNavigationBar: isWide
          ? null
          : NavigationBar(
              selectedIndex: _index,
            onDestinationSelected: _selectTab,
              destinations: const [
                NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
                NavigationDestination(icon: Icon(Icons.analytics_outlined), label: 'Analytics'),
                NavigationDestination(icon: Icon(Icons.storefront_outlined), label: 'Restaurants'),
                NavigationDestination(icon: Icon(Icons.restaurant_menu_outlined), label: 'Menu'),
              ],
            ),
      ),
    );
  }
}
