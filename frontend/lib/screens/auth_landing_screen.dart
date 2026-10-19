import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/auth.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class AuthLandingScreen extends StatefulWidget {
  const AuthLandingScreen({super.key});
  @override
  State<AuthLandingScreen> createState() => _AuthLandingScreenState();
}

class _AuthLandingScreenState extends State<AuthLandingScreen> {
  bool _demoLoading = false;

  Future<void> _demoLogin() async {
    setState(() => _demoLoading = true);
    final auth = context.read<AuthState>();
    final ok = await auth.login('demo@quickbite.example', 'DemoPass123!');
    if (!mounted) return;
    setState(() => _demoLoading = false);
    if (ok) {
      Navigator.pushReplacementNamed(context, '/restaurants');
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(auth.error ?? 'Demo login failed')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/images/dynamic_flying_food_feast.png', fit: BoxFit.cover),
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.black.withValues(alpha: 0.35), Colors.black.withValues(alpha: 0.58)],
              ),
            ),
          ),
          Center(
            child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.xl),
              decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.92), borderRadius: BorderRadius.circular(AppRadii.xl)),
              child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: AppSpacing.xxl),
                const Icon(Icons.restaurant_menu, size: 64, color: AppColors.accent),
                const SizedBox(height: AppSpacing.lg),
                Text('QuickBite', style: Theme.of(context).textTheme.headlineLarge, textAlign: TextAlign.center),
                const SizedBox(height: AppSpacing.xs),
                Text('Order food, track delivery, stay updated.', style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary), textAlign: TextAlign.center),
                const SizedBox(height: AppSpacing.xxl),
                PrimaryButton(label: 'Sign in', icon: Icons.login, onPressed: () => Navigator.pushNamed(context, '/login')),
                const SizedBox(height: AppSpacing.md),
                SecondaryButton(label: 'Sign up', icon: Icons.person_add_alt, onPressed: () => Navigator.pushNamed(context, '/signup')),
                const SizedBox(height: AppSpacing.md),
                SecondaryButton(label: 'Continue as demo user', icon: Icons.play_arrow, onPressed: _demoLoading ? null : _demoLogin),
                if (_demoLoading) const Padding(padding: EdgeInsets.only(top: AppSpacing.sm), child: Center(child: CircularProgressIndicator())),
                const SizedBox(height: AppSpacing.md),
                TextButton.icon(
                  onPressed: () => Navigator.pushNamed(context, '/admin-login'),
                  icon: const Icon(Icons.admin_panel_settings_outlined),
                  label: const Text('Login as admin'),
                ),
                const SizedBox(height: AppSpacing.xl),
                Text('Demo and administrator access use configured backend accounts.', style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
              ],
            ),
          ),
          ),
          ),
          ),
        ],
      ),
    );
  }
}
