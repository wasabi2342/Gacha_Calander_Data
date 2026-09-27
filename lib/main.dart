import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import 'ui/home_page.dart';
import 'ui/theme.dart';

void main() {
  runApp(const GachaCalendarApp());
}

class GachaCalendarApp extends StatelessWidget {
  const GachaCalendarApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '픽업 달력',
      debugShowCheckedModeBanner: false,
      // 기기의 라이트/다크 설정을 따른다
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: ThemeMode.system,
      // 데스크톱에서도 마우스로 끌어서 달력을 넘길 수 있게
      scrollBehavior: const MaterialScrollBehavior().copyWith(dragDevices: {
        PointerDeviceKind.touch,
        PointerDeviceKind.mouse,
        PointerDeviceKind.trackpad,
        PointerDeviceKind.stylus,
      }),
      home: const HomePage(),
    );
  }
}
