import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/main.dart';

void main() {
  testWidgets('App renders login', (WidgetTester tester) async {
    await tester.pumpWidget(const QuickBiteApp());
    await tester.pump();
    expect(find.text('QuickBite'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Continue as demo user'), findsOneWidget);
    expect(find.text('Login as admin'), findsOneWidget);
  });
}
