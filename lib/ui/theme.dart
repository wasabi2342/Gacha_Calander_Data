import 'package:flutter/material.dart';

import '../models/schedule.dart';

/// 라이트/다크 공통 색 토큰. 기본 캘린더 앱처럼 배경은 무채색으로 두고,
/// 색은 게임 아이덴티티 컬러와 일요일(빨강)·토요일(파랑)에만 쓴다.
@immutable
class Pal extends ThemeExtension<Pal> {
  final bool dark;
  final Color bg; // 화면 배경
  final Color cell; // 이번 달 날짜 칸
  final Color cellOut; // 지난달/다음달 날짜 칸
  final Color ink; // 기본 글자
  final Color muted; // 보조 글자
  final Color line; // 구분선
  final Color sunday;
  final Color saturday;
  final Color todayBadge; // 오늘 날짜 배지
  final Color todayBorder; // 오늘 칸 테두리
  final Color surface; // 시트, 카드
  final Color pill; // 하단 알약 버튼
  final Color selected; // 선택한 날짜 칸
  final Color panel; // 달력 아래 "선택한 날" 영역 바탕
  final Color urgentBg; // 마감 임박 배지
  final Color urgentFg;
  final Color chip; // 일반 배지, 진행 막대 바탕

  const Pal({
    required this.dark,
    required this.bg,
    required this.cell,
    required this.cellOut,
    required this.ink,
    required this.muted,
    required this.line,
    required this.sunday,
    required this.saturday,
    required this.todayBadge,
    required this.todayBorder,
    required this.surface,
    required this.pill,
    required this.selected,
    required this.panel,
    required this.urgentBg,
    required this.urgentFg,
    required this.chip,
  });

  static const light = Pal(
    dark: false,
    bg: Color(0xFFFFFFFF),
    cell: Color(0xFFF7F7F9),
    cellOut: Color(0xFFFBFBFC),
    ink: Color(0xFF111111),
    muted: Color(0xFF8A8F98),
    line: Color(0xFFE6E8EC),
    sunday: Color(0xFFE5483B),
    saturday: Color(0xFF2E6BD6),
    todayBadge: Color(0xFFF2424B),
    todayBorder: Color(0xFF6B6F76),
    surface: Color(0xFFFFFFFF),
    pill: Color(0xFFFFFFFF),
    selected: Color(0xFFE9EBEF),
    panel: Color(0xFFF3F4F6),
    urgentBg: Color(0xFFFDE7EA),
    urgentFg: Color(0xFFB4233C),
    chip: Color(0xFFE9EBEF),
  );

  static const darkPal = Pal(
    dark: true,
    bg: Color(0xFF000000),
    cell: Color(0xFF151515),
    cellOut: Color(0xFF0B0B0B),
    ink: Color(0xFFF2F2F2),
    muted: Color(0xFF8E8E93),
    line: Color(0xFF2A2A2A),
    sunday: Color(0xFFFF6B5E),
    saturday: Color(0xFF5B8DEF),
    todayBadge: Color(0xFFF2424B),
    todayBorder: Color(0xFF8E8E93),
    surface: Color(0xFF1C1C1E),
    pill: Color(0xFF3A3A3C),
    selected: Color(0xFF2C2C2E),
    panel: Color(0xFF111113),
    urgentBg: Color(0xFF3A1D23),
    urgentFg: Color(0xFFFF9AA8),
    chip: Color(0xFF2C2C2E),
  );

  @override
  Pal copyWith() => this;

  @override
  Pal lerp(ThemeExtension<Pal>? other, double t) => (other is Pal && t >= 0.5) ? other : this;
}

extension PalContext on BuildContext {
  Pal get pal => Theme.of(this).extension<Pal>()!;
}

ThemeData buildTheme(Brightness brightness) {
  final p = brightness == Brightness.dark ? Pal.darkPal : Pal.light;
  final base = ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: ColorScheme.fromSeed(
      seedColor: p.todayBadge,
      brightness: brightness,
      surface: p.bg,
    ),
    scaffoldBackgroundColor: p.bg,
  );
  return base.copyWith(
    extensions: [p],
    textTheme: base.textTheme.apply(bodyColor: p.ink, displayColor: p.ink),
    appBarTheme: AppBarTheme(
      backgroundColor: p.bg,
      foregroundColor: p.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: true,
    ),
    drawerTheme: DrawerThemeData(backgroundColor: p.bg),
    bottomSheetTheme: BottomSheetThemeData(backgroundColor: p.surface, modalBackgroundColor: p.surface),
    dividerTheme: DividerThemeData(color: p.line, space: 1, thickness: 1),
  );
}

/// 게임 컬러를 글자색으로 쓸 때: 라이트는 어둡게, 다크는 밝게
Color tone(Color c, Pal p) {
  final hsl = HSLColor.fromColor(c);
  final l = p.dark ? (hsl.lightness * 1.25 + 0.12) : (hsl.lightness * 0.62);
  return hsl.withLightness(l.clamp(0.0, 0.92)).toColor();
}

/// 달력 막대 배경. 기본 캘린더처럼 라이트는 파스텔, 다크는 짙은 색
Color barFill(Color game, Pal p, {bool tentative = false}) {
  if (tentative) return Color.alphaBlend(game.withValues(alpha: p.dark ? 0.16 : 0.10), p.cell);
  return Color.alphaBlend(game.withValues(alpha: p.dark ? 0.62 : 0.36), p.dark ? Colors.black : Colors.white);
}

Color barText(Color game, Pal p, {bool tentative = false}) {
  if (tentative) return tone(game, p);
  return p.dark ? Colors.white : const Color(0xFF111111);
}

String? statusLabel(EventStatus s) => switch (s) {
      EventStatus.official => null,
      EventStatus.estimated => '추정',
      EventStatus.leak => '유출',
    };

String statusDescription(EventStatus s) => switch (s) {
      EventStatus.official => '공식 발표된 일정이에요.',
      EventStatus.estimated => '공식 발표 전 추정 일정이에요. 바뀔 수 있어요.',
      EventStatus.leak => '유출 정보 기반이에요. 실제와 다를 수 있어요.',
    };

class StatusTag extends StatelessWidget {
  final EventStatus status;
  final Color color;

  const StatusTag({super.key, required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    final label = statusLabel(status);
    if (label == null) return const SizedBox.shrink();
    final p = context.pal;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.7)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: tone(color, p))),
    );
  }
}
