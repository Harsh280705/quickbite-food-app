import 'package:flutter/material.dart';
import '../models.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class CheckoutResultScreen extends StatelessWidget {
  const CheckoutResultScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final arg = ModalRoute.of(context)?.settings.arguments;
    final accepted = arg is CheckoutAccepted ? arg : null;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: AppCard(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.check_circle, color: AppColors.success, size: 64),
                const SizedBox(height: AppSpacing.md),
                Text('Order accepted', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: AppSpacing.sm),
                Text('Your order is being processed asynchronously.', style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
                const SizedBox(height: AppSpacing.lg),
                _row('Order ID', accepted?.orderId ?? '-'),
                _row('Status', accepted?.status ?? '-'),
                _row('Total', '${accepted?.currency ?? "INR"} ${((accepted?.totalAmountMinor ?? 0) / 100).toStringAsFixed(2)}'),
                const SizedBox(height: AppSpacing.xl),
                PrimaryButton(label: 'Track order', onPressed: () => Navigator.pushReplacementNamed(context, '/order', arguments: accepted?.orderId)),
                const SizedBox(height: AppSpacing.sm),
                SecondaryButton(label: 'Browse restaurants', onPressed: () => Navigator.pushReplacementNamed(context, '/restaurants')),
              ]),
            ),
          ),
        ),
      ),
    );
  }

  Widget _row(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(k, style: const TextStyle(color: AppColors.textSecondary)), Text(v, style: const TextStyle(fontWeight: FontWeight.w600))]),
      );
}
