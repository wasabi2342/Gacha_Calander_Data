import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:gacha_calender/data/kst.dart';
import 'package:gacha_calender/main.dart';
import 'package:gacha_calender/models/schedule.dart';
import 'package:gacha_calender/ui/month_view.dart';
import 'package:gacha_calender/ui/pickup_widgets.dart';

ScheduleEvent banner({required String start, String? end, bool endConfirmed = true}) => ScheduleEvent.fromJson({
      'id': 't',
      'gameId': 'genshin',
      'type': 'BANNER',
      'version': '7.0',
      'phase': 1,
      'title': '7.0 전반 픽업',
      'characters': [
        {'name': '복각캐', 'rarity': 5, 'isNew': false},
        {'name': '신규캐', 'rarity': 5, 'isNew': true},
      ],
      'startAt': start,
      'timeKnown': true,
      'endAt': end,
      'endConfirmed': endConfirmed,
      'status': 'OFFICIAL',
    });

/// KST 벽시계 값 (앱 내부 표현과 같음)
DateTime kst(int m, int d, [int h = 12]) => DateTime.utc(2026, m, d, h);

void main() {
  testWidgets('앱이 뜨고 이번 달 제목이 보인다', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const GachaCalendarApp());
    await tester.pump();

    final now = DateTime.now().toUtc().add(const Duration(hours: 9));
    expect(find.text('${now.month}월'), findsOneWidget);

    // 테스트에선 네트워크가 막혀 있다. 저장된 일정도 없으니 예시로 가리지 않고 '다시 시도' 화면이 나와야 한다.
    await tester.pump(const Duration(seconds: 12));
    await tester.pump(const Duration(seconds: 12));
    expect(find.text('다시 시도'), findsOneWidget);
    expect(find.textContaining('진행 중인 픽업'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('저장된 일정이 있으면 네트워크가 안 돼도 그걸 보여준다', (WidgetTester tester) async {
    final raw = (await tester.runAsync(() => rootBundle.loadString('assets/seed_events.json')))!;
    SharedPreferences.setMockInitialValues({'events_cache_v1': raw});
    await tester.pumpWidget(const GachaCalendarApp());
    await tester.pump(const Duration(seconds: 12));
    await tester.pump(const Duration(seconds: 12));
    expect(find.textContaining('마지막으로 받은 일정'), findsOneWidget);
    expect(find.text('다시 시도'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  group('픽업 남은 기간', () {
    final e = banner(start: '2026-09-09T11:00:00+09:00', end: '2026-09-29T17:59:00+09:00');

    test('D-day와 진행 비율', () {
      final pr = PickupProgress.of(e, kst(9, 26));
      expect(pr.daysLeft, 3);
      expect(pr.badge, 'D-3');
      expect(pr.urgent, isTrue);
      expect(pr.ratio, closeTo(18 / 21, 1e-9)); // 9.9~9.29 = 21일 중 18일째
    });

    test('마지막 날은 D-DAY, 다음 날은 종료', () {
      expect(PickupProgress.of(e, kst(9, 29, 9)).badge, 'D-DAY');
      expect(PickupProgress.of(e, kst(9, 30)).ended, isTrue);
    });

    test('마지막 날 낮에도 진행 중으로 본다 (날짜만 비교)', () {
      expect(occursOn(e, dateOnly(kst(9, 29, 15))), isTrue);
    });

    test('새벽 6시 전에 끝나는 픽업은 전날까지로 계산', () {
      final early = banner(start: '2026-09-09T11:00:00+09:00', end: '2026-09-30T03:59:00+09:00');
      expect(PickupProgress.of(early, kst(9, 29)).badge, 'D-DAY');
    });

    test('종료일 미정이면 D-day 대신 진행 중', () {
      final open = banner(start: '2026-09-20T00:00:00+09:00', end: null, endConfirmed: false);
      final pr = PickupProgress.of(open, kst(9, 26));
      expect(pr.endUnknown, isTrue);
      expect(pr.badge, '진행 중');
      expect(pr.urgent, isFalse);
    });

    test('신규 캐릭터가 먼저, 복각은 표시', () {
      expect(characterLine(e), '신규캐, 복각캐(복각)');
    });
  });

  test('날짜 도우미', () {
    expect(daysBetween(kst(9, 26, 23), kst(9, 27, 1)), 1);
    expect(dateKey(kst(9, 5)), '2026-09-05');
    expect(fmtShort(kst(10, 3)), '10.3');
  });
}
