import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:frontend/main.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('login screen renders', (WidgetTester tester) async {
    await tester.pumpWidget(const QuickBiteApp());
    await tester.pump();
    expect(find.text('QuickBite'), findsOneWidget);
  });
}
