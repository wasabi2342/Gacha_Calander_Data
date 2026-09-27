/// 게임 일정은 전부 한국 시간 기준이라, 기기 시간대와 상관없이
/// "KST 벽시계 값을 가진 UTC DateTime"으로 통일해서 다룬다.
DateTime toKst(DateTime d) => d.toUtc().add(const Duration(hours: 9));

DateTime kstNow() => toKst(DateTime.now());

DateTime dateOnly(DateTime d) => DateTime.utc(d.year, d.month, d.day);

const _weekdays = ['월', '화', '수', '목', '금', '토', '일'];

String weekdayKo(DateTime d) => _weekdays[d.weekday - 1];

String two(int n) => n.toString().padLeft(2, '0');

String fmtDate(DateTime d) => '${d.month}월 ${d.day}일 (${weekdayKo(d)})';

String fmtDateTime(DateTime d, {bool withTime = true}) =>
    withTime ? '${fmtDate(d)} ${two(d.hour)}:${two(d.minute)}' : fmtDate(d);

/// 오늘 기준 D-day 문자열
String dDay(DateTime target, DateTime now) {
  final diff = dateOnly(target).difference(dateOnly(now)).inDays;
  if (diff == 0) return '오늘';
  return diff > 0 ? 'D-$diff' : 'D+${-diff}';
}

/// 두 날짜 사이 일수 (날짜만 비교, b가 뒤면 양수)
int daysBetween(DateTime a, DateTime b) => dateOnly(b).difference(dateOnly(a)).inDays;

/// 공휴일 표 등에 쓰는 'YYYY-MM-DD'
String dateKey(DateTime d) => '${d.year}-${two(d.month)}-${two(d.day)}';

/// '9.26' 처럼 짧은 날짜
String fmtShort(DateTime d) => '${d.month}.${d.day}';
