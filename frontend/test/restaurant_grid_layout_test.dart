import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/screens/restaurant_list_screen.dart';

Widget _grid(int count, {double? screenWidth}) {
  return MaterialApp(
    home: Scaffold(
      body: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: restaurantGridDelegate(screenWidth),
        itemCount: count,
        itemBuilder: (context, index) => Container(
          key: ValueKey('restaurant-$index'),
          alignment: Alignment.center,
          child: Text('Restaurant $index'),
        ),
      ),
    ),
  );
}

void _setViewport(WidgetTester tester, Size size) {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = size;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets(
    'desktop grid shows four compact, stable columns as items append',
    (tester) async {
      _setViewport(tester, const Size(1536, 864));
      await tester.pumpWidget(_grid(5));

      final first = find.byKey(const ValueKey('restaurant-0'));
      final firstPosition = tester.getTopLeft(first);
      final firstSize = tester.getSize(first);
      final rowY = [
        for (var index = 0; index < 4; index++)
          tester.getTopLeft(find.byKey(ValueKey('restaurant-$index'))).dy,
      ];
      expect(rowY, everyElement(firstPosition.dy));

      final fifth = find.byKey(const ValueKey('restaurant-4'));
      expect(tester.getTopLeft(fifth).dy, greaterThan(firstPosition.dy));
      expect(tester.getSize(fifth), firstSize);

      await tester.pumpWidget(_grid(12));
      expect(tester.getTopLeft(first), firstPosition);
      expect(tester.getSize(first), firstSize);
    },
  );

  testWidgets('tablet grid adapts to two columns', (tester) async {
    _setViewport(tester, const Size(768, 900));
    await tester.pumpWidget(_grid(4));

    final firstY = tester
        .getTopLeft(find.byKey(const ValueKey('restaurant-0')))
        .dy;
    final secondY = tester
        .getTopLeft(find.byKey(const ValueKey('restaurant-1')))
        .dy;
    final thirdY = tester
        .getTopLeft(find.byKey(const ValueKey('restaurant-2')))
        .dy;
    expect(secondY, firstY);
    expect(thirdY, greaterThan(firstY));
  });

  testWidgets('phone grid keeps one readable column on wide phones too', (
    tester,
  ) async {
    _setViewport(tester, const Size(412, 915));
    await tester.pumpWidget(_grid(3, screenWidth: 412));

    final first = find.byKey(const ValueKey('restaurant-0'));
    final second = find.byKey(const ValueKey('restaurant-1'));
    expect(
      tester.getTopLeft(second).dy,
      greaterThan(tester.getTopLeft(first).dy),
    );
    expect(tester.getTopLeft(second).dx, tester.getTopLeft(first).dx);
  });
}
