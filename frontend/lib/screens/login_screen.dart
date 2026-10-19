import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../state/auth.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class LoginScreen extends StatefulWidget {
  final bool adminMode;
  const LoginScreen({super.key, this.adminMode = false});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _obscure = true;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
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
                colors: [Colors.black.withValues(alpha: 0.35), Colors.black.withValues(alpha: 0.62)],
              ),
            ),
          ),
          Center(
            child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: AppSpacing.xxl),
                Text('QuickBite', style: Theme.of(context).textTheme.headlineLarge?.copyWith(color: Colors.white), textAlign: TextAlign.center),
                const SizedBox(height: AppSpacing.xs),
                Text('Order food, track delivery, stay updated.', style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.white70), textAlign: TextAlign.center),
                const SizedBox(height: AppSpacing.xxl),
                AppCard(
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(widget.adminMode ? 'Administrator sign in' : 'Sign in', style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: AppSpacing.lg),
                        TextFormField(
                          controller: _email,
                          decoration: const InputDecoration(labelText: 'Email', prefixIcon: Icon(Icons.email_outlined)),
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          validator: (v) => (v == null || !v.contains('@')) ? 'Enter a valid email' : null,
                        ),
                        const SizedBox(height: AppSpacing.md),
                        TextFormField(
                          controller: _password,
                          obscureText: _obscure,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(
                              icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                              onPressed: () => setState(() => _obscure = !_obscure),
                            ),
                          ),
                          textInputAction: TextInputAction.done,
                          onFieldSubmitted: (_) => _submit(auth),
                          validator: (v) => (v == null || v.isEmpty) ? 'Password required' : null,
                        ),
                        if (auth.error != null) ...[
                          const SizedBox(height: AppSpacing.md),
                          Text(auth.error!, style: const TextStyle(color: AppColors.error)),
                        ],
                        const SizedBox(height: AppSpacing.xl),
                        PrimaryButton(
                          label: 'Sign in',
                          loading: auth.loading,
                          onPressed: () => _submit(auth),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.lg),
                TextButton(
                  onPressed: () => Navigator.pushReplacementNamed(context, '/restaurants'),
                  child: const Text('Browse restaurants as guest'),
                ),
                TextButton(
                  onPressed: () => Navigator.pushNamed(context, '/signup'),
                  child: const Text('Create account / Sign up'),
                ),
                Text('Demo: demo@quickbite.example / DemoPass123!', style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
              ],
            ),
          ),
          ),
          ),
        ],
      ),
    );
  }

  void _submit(AuthState auth) {
    if (auth.loading) return;
    if (!_formKey.currentState!.validate()) return;
    auth.login(_email.text.trim(), _password.text).then((ok) {
      if (!ok || !mounted) return;
      final role = auth.user?.role;
      if (widget.adminMode && role != 'admin') {
        auth.logout();
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Administrator role is required')));
        return;
      }
      Navigator.pushReplacementNamed(context, role == 'admin' ? '/admin' : '/restaurants');
    });
  }
}
