import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'theme/app_theme.dart';
import 'api/api_client.dart';
import 'state/auth.dart';
import 'state/cart.dart';
import 'screens/auth_landing_screen.dart';
import 'screens/login_screen.dart';
import 'screens/signup_screen.dart';
import 'screens/restaurant_list_screen.dart';
import 'screens/menu_screen.dart';
import 'screens/cart_screen.dart';
import 'screens/checkout_result_screen.dart';
import 'screens/order_detail_screen.dart';
import 'screens/order_history_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/admin_shell.dart';

void main() {
  runApp(const QuickBiteApp());
}

class QuickBiteApp extends StatelessWidget {
  const QuickBiteApp({super.key});

  @override
  Widget build(BuildContext context) {
    final api = ApiClient();
    return MultiProvider(
      providers: [
        Provider<ApiClient>.value(value: api),
        ChangeNotifierProvider(create: (_) => AuthState(api)),
        ChangeNotifierProvider(create: (_) => CartState(api: api)),
      ],
      child: MaterialApp(
        title: 'QuickBite',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        initialRoute: '/',
        routes: {
          '/': (_) => const AuthLandingScreen(),
          '/login': (_) => const LoginScreen(),
          '/admin-login': (_) => const LoginScreen(adminMode: true),
          '/signup': (_) => const SignupScreen(),
          '/restaurants': (_) => const RestaurantListScreen(),
          '/menu': (_) => const MenuScreen(),
          '/cart': (_) => const CartScreen(),
          '/order': (_) => const OrderDetailScreen(),
          '/history': (_) => const OrderHistoryScreen(),
          '/notifications': (_) => const NotificationsScreen(),
          '/admin': (_) => const AdminShell(),
          '/checkout-result': (_) => const CheckoutResultScreen(),
        },
      ),
    );
  }
}
