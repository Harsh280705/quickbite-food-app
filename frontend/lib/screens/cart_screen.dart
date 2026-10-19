import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/api_client.dart';
import '../config.dart';
import '../models.dart';
import '../state/auth.dart';
import '../state/cart.dart';
import '../theme/app_theme.dart';
import '../widgets/common.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key});
  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  final _formKey = GlobalKey<FormState>();
  final _addressCtrl = TextEditingController();
  String? _addressError;

  @override
  void initState() {
    super.initState();
    _addressCtrl.text = context.read<CartState>().deliveryAddress;
    _addressCtrl.addListener(() {
      if (_addressError != null) setState(() => _addressError = null);
    });
  }

  @override
  void dispose() {
    _addressCtrl.dispose();
    super.dispose();
  }

  bool _isRetryable(Object error) {
    if (error is ApiException) {
      return error.statusCode >= 500 ||
          error.statusCode == 408 ||
          error.statusCode == 429;
    }
    return true;
  }

  Future<void> _checkout() async {
    final cart = context.read<CartState>();
    final api = context.read<ApiClient>();
    final auth = context.read<AuthState>();
    if (api.accessToken == null && auth.api.accessToken != null) {
      api.setAccessToken(auth.api.accessToken);
    }
    final hasPending =
        cart.pendingIdempotencyKey != null && cart.pendingRequest != null;
    if ((!hasPending && cart.isEmpty) ||
        (!hasPending && cart.restaurantId == null))
      return;
    if (api.accessToken == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please sign in to place your order')),
      );
      Navigator.pushNamed(context, '/login');
      return;
    }
    if (!hasPending) {
      cart.deliveryAddress = _addressCtrl.text.trim();
      if (cart.deliveryAddress.length < 10) {
        setState(() => _addressError = 'Enter a complete delivery address');
        return;
      }
      await cart.preparePendingCheckout(cart.buildRequest());
    }
    cart.checkoutInProgress = true;
    cart.checkoutError = null;
    cart.checkoutRetryable = false;
    cart.notify();

    try {
      final res = await api.post(
        '/orders',
        body: cart.pendingRequest,
        idempotencyKey: cart.pendingIdempotencyKey,
      );
      final accepted = CheckoutAccepted.fromJson(
        Map<String, dynamic>.from(res),
      );
      cart.checkoutInProgress = false;
      await cart.clearResolvedCheckout();
      if (mounted)
        Navigator.pushNamed(context, '/checkout-result', arguments: accepted);
    } catch (e) {
      cart.checkoutInProgress = false;
      cart.checkoutError = e.toString();
      cart.checkoutRetryable = _isRetryable(e);
      // A validation rejection proves that the server did not accept this
      // request. Network failures, timeouts, 5xx responses and idempotency
      // conflicts remain pending so the exact request/key can be retried.
      if (e is ApiException && (e.statusCode == 400 || e.statusCode == 422)) {
        await cart.clearPendingCheckout();
      }
      cart.notify();
      if (mounted) {
        setState(() {});
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Checkout failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<CartState>();
    final compactAndroid = isCompactAndroid(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Your cart')),
      body: cart.isEmpty
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (cart.pendingRequest != null) ...[
                    const Icon(Icons.sync, size: 48),
                    const SizedBox(height: AppSpacing.md),
                    const Text('A checkout is waiting for confirmation.'),
                    const SizedBox(height: AppSpacing.md),
                    PrimaryButton(
                      label: 'Retry saved checkout',
                      loading: cart.checkoutInProgress,
                      onPressed: cart.checkoutInProgress ? null : _checkout,
                    ),
                  ] else
                    const EmptyView(
                      title: 'Your cart is empty',
                      subtitle: 'Add items from a restaurant menu.',
                      icon: Icons.shopping_bag_outlined,
                    ),
                  const SizedBox(height: AppSpacing.lg),
                  if (cart.pendingRequest == null)
                    PrimaryButton(
                      label: 'Discover restaurants',
                      icon: Icons.restaurant,
                      onPressed: () => Navigator.pushReplacementNamed(
                        context,
                        '/restaurants',
                      ),
                    ),
                ],
              ),
            )
          : LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 900;
                final cartList = ListView.separated(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  itemCount: cart.lines.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: AppSpacing.md),
                  itemBuilder: (_, i) {
                    final line = cart.lines[i];
                    return AppCard(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      child: compactAndroid
                          ? Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    _CartImage(url: line.item.imageUrl),
                                    const SizedBox(width: AppSpacing.md),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            line.item.name,
                                            style: Theme.of(
                                              context,
                                            ).textTheme.titleMedium,
                                            softWrap: true,
                                          ),
                                          const SizedBox(height: 2),
                                          PriceText(
                                            minor: line.item.priceMinor,
                                            currency: line.item.currency,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                                const Divider(height: AppSpacing.xl),
                                Row(
                                  children: [
                                    IconButton(
                                      tooltip: 'Decrease',
                                      icon: const Icon(
                                        Icons.remove_circle_outline,
                                      ),
                                      onPressed:
                                          cart.pendingIdempotencyKey != null
                                          ? null
                                          : () => cart.updateQty(
                                              line.item.id,
                                              line.quantity - 1,
                                            ),
                                    ),
                                    Text(
                                      '${line.quantity}',
                                      style: Theme.of(
                                        context,
                                      ).textTheme.titleMedium,
                                    ),
                                    IconButton(
                                      tooltip: 'Increase',
                                      icon: const Icon(
                                        Icons.add_circle_outline,
                                      ),
                                      onPressed:
                                          cart.pendingIdempotencyKey != null
                                          ? null
                                          : () => cart.updateQty(
                                              line.item.id,
                                              line.quantity + 1,
                                            ),
                                    ),
                                    const Spacer(),
                                    PriceText(
                                      minor: line.lineTotal,
                                      currency: line.item.currency,
                                      bold: true,
                                    ),
                                    IconButton(
                                      tooltip: 'Remove',
                                      icon: const Icon(Icons.delete_outline),
                                      color: AppColors.error,
                                      onPressed:
                                          cart.pendingIdempotencyKey != null
                                          ? null
                                          : () => cart.remove(line.item.id),
                                    ),
                                  ],
                                ),
                              ],
                            )
                          : Row(
                              children: [
                                _CartImage(url: line.item.imageUrl),
                                const SizedBox(width: AppSpacing.md),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        line.item.name,
                                        style: Theme.of(
                                          context,
                                        ).textTheme.titleMedium,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      const SizedBox(height: 2),
                                      PriceText(
                                        minor: line.item.priceMinor,
                                        currency: line.item.currency,
                                      ),
                                    ],
                                  ),
                                ),
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    IconButton(
                                      tooltip: 'Decrease',
                                      icon: const Icon(
                                        Icons.remove_circle_outline,
                                      ),
                                      onPressed:
                                          cart.pendingIdempotencyKey != null
                                          ? null
                                          : () => cart.updateQty(
                                              line.item.id,
                                              line.quantity - 1,
                                            ),
                                    ),
                                    Text(
                                      '${line.quantity}',
                                      style: Theme.of(
                                        context,
                                      ).textTheme.titleMedium,
                                    ),
                                    IconButton(
                                      tooltip: 'Increase',
                                      icon: const Icon(
                                        Icons.add_circle_outline,
                                      ),
                                      onPressed:
                                          cart.pendingIdempotencyKey != null
                                          ? null
                                          : () => cart.updateQty(
                                              line.item.id,
                                              line.quantity + 1,
                                            ),
                                    ),
                                    IconButton(
                                      tooltip: 'Remove',
                                      icon: const Icon(Icons.delete_outline),
                                      color: AppColors.error,
                                      onPressed:
                                          cart.pendingIdempotencyKey != null
                                          ? null
                                          : () => cart.remove(line.item.id),
                                    ),
                                  ],
                                ),
                                const SizedBox(width: AppSpacing.sm),
                                PriceText(
                                  minor: line.lineTotal,
                                  currency: line.item.currency,
                                  bold: true,
                                ),
                              ],
                            ),
                    );
                  },
                );
                final summary = AppCard(
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Order summary',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: AppSpacing.md),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Subtotal'),
                            PriceText(
                              minor: cart.subtotal,
                              currency: cart.lines.first.item.currency,
                              bold: true,
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.md),
                        Text(
                          'Delivery address',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        TextFormField(
                          controller: _addressCtrl,
                          enabled: cart.pendingIdempotencyKey == null,
                          minLines: 2,
                          maxLines: 3,
                          decoration: InputDecoration(
                            hintText: 'House/flat, street, area, city',
                            errorText: _addressError,
                          ),
                          validator: (v) => (v == null || v.trim().length < 10)
                              ? 'Enter a complete delivery address'
                              : null,
                        ),
                        if (cart.checkoutError != null) ...[
                          const SizedBox(height: AppSpacing.sm),
                          Text(
                            cart.checkoutError!,
                            style: const TextStyle(
                              color: AppColors.error,
                              fontSize: 12,
                            ),
                          ),
                        ],
                        const SizedBox(height: AppSpacing.lg),
                        if (cart.pendingIdempotencyKey != null) ...[
                          const SizedBox(height: AppSpacing.sm),
                          const Text(
                            'A checkout request is awaiting confirmation. Retry sends the saved request with the same key.',
                          ),
                        ],
                        PrimaryButton(
                          label: cart.pendingIdempotencyKey == null
                              ? 'Place order'
                              : 'Resolve pending checkout',
                          loading: cart.checkoutInProgress,
                          onPressed: cart.checkoutInProgress ? null : _checkout,
                        ),
                        if (cart.pendingIdempotencyKey != null &&
                            cart.checkoutRetryable) ...[
                          const SizedBox(height: AppSpacing.sm),
                          SecondaryButton(
                            label: 'Retry checkout',
                            icon: Icons.refresh,
                            onPressed: cart.checkoutInProgress
                                ? null
                                : _checkout,
                          ),
                        ],
                      ],
                    ),
                  ),
                );
                if (wide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 2, child: cartList),
                      const SizedBox(width: AppSpacing.lg),
                      SizedBox(
                        width: 380,
                        child: Padding(
                          padding: const EdgeInsets.only(top: AppSpacing.lg),
                          child: summary,
                        ),
                      ),
                    ],
                  );
                }
                if (compactAndroid) {
                  return Column(
                    children: [
                      Expanded(child: cartList),
                      ConstrainedBox(
                        constraints: BoxConstraints(
                          maxHeight: constraints.maxHeight * 0.55,
                        ),
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(AppSpacing.md),
                          child: summary,
                        ),
                      ),
                    ],
                  );
                }
                return Column(
                  children: [
                    Expanded(child: cartList),
                    Padding(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      child: summary,
                    ),
                  ],
                );
              },
            ),
    );
  }
}

class _CartImage extends StatelessWidget {
  final String? url;
  const _CartImage({required this.url});
  @override
  Widget build(BuildContext context) {
    if (url == null || url!.isEmpty) {
      return Container(
        width: 56,
        height: 56,
        decoration: BoxDecoration(
          color: AppColors.surfaceAlt,
          borderRadius: BorderRadius.circular(AppRadii.md),
        ),
        child: const Icon(Icons.fastfood, color: AppColors.textSecondary),
      );
    }
    String resolved = url!;
    if (!resolved.startsWith('http'))
      resolved = '${AppConfig.apiBaseUrl}$resolved';
    return ClipRRect(
      borderRadius: BorderRadius.circular(AppRadii.md),
      child: Image.network(
        resolved,
        width: 56,
        height: 56,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => Container(
          width: 56,
          height: 56,
          color: AppColors.surfaceAlt,
          child: const Icon(Icons.fastfood, color: AppColors.textSecondary),
        ),
      ),
    );
  }
}
