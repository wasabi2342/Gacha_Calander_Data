import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'theme.dart';

/// 월 페이지 인덱스 (2020년 1월 = 0)
const _baseYear = 2020;
const monthPageCount = 12 * 20;

int monthIndexOf(DateTime d) => (d.year - _baseYear) * 12 + d.month - 1;

DateTime monthOfIndex(int i) => DateTime.utc(_baseYear + i ~/ 12, i % 12 + 1, 1);

/// 일정이 달력에서 차지하는 날짜 범위 (양 끝 포함)
({DateTime first, DateTime last}) dayRange(ScheduleEvent e) {
  final first = dateOnly(e.startAt);
  if (!e.isBanner) return (first: first, last: first);
  final end = e.displayEnd;
  var last = dateOnly(end);
  // 새벽(06시 전)에 끝나는 픽업은 사실상 전날까지라서 전날로 표시
  if (end.hour < 6 && last.isAfter(first)) last = last.subtract(const Duration(days: 1));
  if (last.isBefore(first)) last = first;
  return (first: first, last: last);
}

bool occursOn(ScheduleEvent e, DateTime day) {
  final r = dayRange(e);
  return !day.isBefore(r.first) && !day.isAfter(r.last);
}

/// 기본 캘린더 앱 스타일의 한 달 격자
class MonthGrid extends StatelessWidget {
  final DateTime month; // 그 달 1일 (UTC 벽시계)
  final List<ScheduleEvent> events;
  final Map<String, Game> games;
  final void Function(ScheduleEvent) onTapEvent;
  final void Function(DateTime day) onTapDay;

  /// 선택한 날 (달력 아래 패널에 보여주는 날). null이면 표시 안 함
  final DateTime? selected;

  /// 'YYYY-MM-DD' → 공휴일 이름
  final Map<String, String> holidays;

  static const _weekdays = ['일', '월', '화', '수', '목', '금', '토'];

  const MonthGrid({
    super.key,
    required this.month,
    required this.events,
    required this.games,
    required this.onTapEvent,
    required this.onTapDay,
    this.selected,
    this.holidays = const {},
  });

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final today = dateOnly(kstNow());
    final offset = month.weekday % 7; // 일요일 시작
    final gridStart = month.subtract(Duration(days: offset));
    final daysInMonth = DateTime.utc(month.year, month.month + 1, 0).day;
    final rows = ((offset + daysInMonth) / 7).ceil();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: Column(children: [
        SizedBox(
          height: 32,
          child: Row(children: [
            for (var i = 0; i < 7; i++)
              Expanded(
                child: Center(
                  child: Text(
                    _weekdays[i],
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: i == 0 ? p.sunday : (i == 6 ? p.saturday : p.muted),
                    ),
                  ),
                ),
              ),
          ]),
        ),
        Expanded(
          child: LayoutBuilder(builder: (context, c) {
            final rowH = c.maxHeight / rows;
            return Column(children: [
              for (var r = 0; r < rows; r++)
                SizedBox(
                  height: rowH,
                  child: _WeekRow(
                    weekStart: gridStart.add(Duration(days: r * 7)),
                    month: month,
                    today: today,
                    events: events,
                    games: games,
                    onTapEvent: onTapEvent,
                    onTapDay: onTapDay,
                    selected: selected == null ? null : dateOnly(selected!),
                    holidays: holidays,
                  ),
                ),
            ]);
          }),
        ),
      ]),
    );
  }
}

/// 한 주에 걸친 일정 조각
class _Seg {
  final ScheduleEvent event;
  final int startCol;
  final int endCol;
  final bool contLeft; // 지난주에서 이어짐
  final bool contRight; // 다음 주로 이어짐
  int lane = 0;

  _Seg(this.event, this.startCol, this.endCol, {required this.contLeft, required this.contRight});
}

class _WeekRow extends StatelessWidget {
  final DateTime weekStart;
  final DateTime month;
  final DateTime today;
  final List<ScheduleEvent> events;
  final Map<String, Game> games;
  final void Function(ScheduleEvent) onTapEvent;
  final void Function(DateTime day) onTapDay;
  final DateTime? selected;
  final Map<String, String> holidays;

  static const gap = 3.0;
  static const dateH = 30.0;
  static const barH = 18.0;
  static const barGap = 2.0;

  const _WeekRow({
    required this.weekStart,
    required this.month,
    required this.today,
    required this.events,
    required this.games,
    required this.onTapEvent,
    required this.onTapDay,
    required this.selected,
    required this.holidays,
  });

  List<_Seg> _segments() {
    final weekEnd = weekStart.add(const Duration(days: 6));
    final segs = <_Seg>[];
    for (final e in events) {
      if (games[e.gameId] == null) continue;
      final r = dayRange(e);
      if (r.last.isBefore(weekStart) || r.first.isAfter(weekEnd)) continue;
      final s = r.first.isBefore(weekStart) ? 0 : r.first.difference(weekStart).inDays;
      final t = r.last.isAfter(weekEnd) ? 6 : r.last.difference(weekStart).inDays;
      segs.add(_Seg(e, s, t, contLeft: r.first.isBefore(weekStart), contRight: r.last.isAfter(weekEnd)));
    }
    // 버전 업데이트 먼저, 그다음 시작이 빠른 순, 긴 순
    segs.sort((a, b) {
      if (a.event.isBanner != b.event.isBanner) return a.event.isBanner ? 1 : -1;
      final byStart = a.startCol.compareTo(b.startCol);
      if (byStart != 0) return byStart;
      return (b.endCol - b.startCol).compareTo(a.endCol - a.startCol);
    });
    final laneEnds = <int>[];
    for (final s in segs) {
      var lane = laneEnds.indexWhere((end) => end < s.startCol);
      if (lane == -1) {
        lane = laneEnds.length;
        laneEnds.add(s.endCol);
      } else {
        laneEnds[lane] = s.endCol;
      }
      s.lane = lane;
    }
    return segs;
  }

  @override
  Widget build(BuildContext context) {
    final segs = _segments();
    final totalLanes = segs.isEmpty ? 0 : segs.map((s) => s.lane).reduce(math.max) + 1;

    return LayoutBuilder(builder: (context, c) {
      final cellW = c.maxWidth / 7;
      final fit = math.max(0, ((c.maxHeight - dateH - gap * 2) / (barH + barGap)).floor());
      // 다 안 들어가면 마지막 줄은 "+N" 자리로 비워둔다
      final visible = totalLanes <= fit ? totalLanes : math.max(0, fit - 1);
      final hidden = List<int>.filled(7, 0);
      for (final s in segs) {
        if (s.lane >= visible) {
          for (var d = s.startCol; d <= s.endCol; d++) {
            hidden[d]++;
          }
        }
      }

      return Stack(children: [
        Row(children: [
          for (var d = 0; d < 7; d++)
            _DayCell(
              day: weekStart.add(Duration(days: d)),
              inMonth: weekStart.add(Duration(days: d)).month == month.month,
              isToday: weekStart.add(Duration(days: d)) == today,
              isSelected: weekStart.add(Duration(days: d)) == selected,
              holiday: holidays[dateKey(weekStart.add(Duration(days: d)))],
              showHolidayName: cellW >= 120, // 좁으면 이름 없이 빨간 날로만
              hidden: hidden[d],
              onTap: () => onTapDay(weekStart.add(Duration(days: d))),
            ),
        ]),
        for (final s in segs)
          if (s.lane < visible)
            Positioned(
              left: s.contLeft ? s.startCol * cellW : s.startCol * cellW + gap + 1,
              width: (s.contRight ? (s.endCol + 1) * cellW : (s.endCol + 1) * cellW - gap - 1) -
                  (s.contLeft ? s.startCol * cellW : s.startCol * cellW + gap + 1),
              top: gap + dateH + s.lane * (barH + barGap),
              height: barH,
              child: Opacity(
                opacity: _outsideMonth(s) ? 0.45 : 1,
                child: _Bar(seg: s, game: games[s.event.gameId]!, onTap: () => onTapEvent(s.event)),
              ),
            ),
      ]);
    });
  }

  bool _outsideMonth(_Seg s) {
    for (var d = s.startCol; d <= s.endCol; d++) {
      if (weekStart.add(Duration(days: d)).month == month.month) return false;
    }
    return true;
  }
}

class _DayCell extends StatelessWidget {
  final DateTime day;
  final bool inMonth;
  final bool isToday;
  final bool isSelected;
  final String? holiday;
  final bool showHolidayName;
  final int hidden;
  final VoidCallback onTap;

  const _DayCell({
    required this.day,
    required this.inMonth,
    required this.isToday,
    required this.isSelected,
    required this.holiday,
    required this.showHolidayName,
    required this.hidden,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final red = day.weekday == DateTime.sunday || holiday != null;
    var color = red ? p.sunday : (day.weekday == DateTime.saturday ? p.saturday : p.ink);
    if (!inMonth) color = color.withValues(alpha: 0.3);
    final label = '${day.month}월 ${day.day}일${holiday != null ? ', $holiday' : ''}${isToday ? ', 오늘' : ''}';

    return Expanded(
      child: Semantics(
        button: true,
        selected: isSelected,
        label: label,
        child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Container(
          margin: const EdgeInsets.all(_WeekRow.gap),
          decoration: BoxDecoration(
            color: isSelected ? p.selected : (inMonth ? p.cell : p.cellOut),
            borderRadius: BorderRadius.circular(6),
            border: isToday ? Border.all(color: p.todayBorder, width: 1.5) : null,
          ),
          child: Stack(children: [
            Align(
              alignment: Alignment.topCenter,
              child: Padding(
                padding: const EdgeInsets.only(top: 4),
                child: isToday
                    ? Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(color: p.todayBadge, borderRadius: BorderRadius.circular(6)),
                        child: Text('${day.day}',
                            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: Colors.white)),
                      )
                    : Text('${day.day}', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: color)),
              ),
            ),
            if (holiday != null && showHolidayName && inMonth)
              Positioned(
                top: 7,
                right: 5,
                child: Text(holiday!, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: p.sunday)),
              ),
            if (hidden > 0)
              Positioned(
                left: 0,
                right: 0,
                bottom: 2,
                child: Center(
                  child: Text('+$hidden',
                      style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: p.muted)),
                ),
              ),
          ]),
        ),
      ),
      ),
    );
  }
}

class _Bar extends StatelessWidget {
  final _Seg seg;
  final Game game;
  final VoidCallback onTap;

  const _Bar({required this.seg, required this.game, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final e = seg.event;
    final tentative = e.status != EventStatus.official;
    final radius = BorderRadius.horizontal(
      left: Radius.circular(seg.contLeft ? 0 : 4),
      right: Radius.circular(seg.contRight ? 0 : 4),
    );

    if (!e.isBanner) {
      // 버전 업데이트: 배경 없이 게임 색 글자
      return GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 3),
          alignment: Alignment.centerLeft,
          decoration: BoxDecoration(
            borderRadius: radius,
            border: Border.all(color: game.color.withValues(alpha: tentative ? 0.4 : 0.8), width: 1),
          ),
          child: Text(
            '◆ ${e.hasVersionNumber ? e.version : '업데이트'}',
            maxLines: 1,
            overflow: TextOverflow.clip,
            softWrap: false,
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: tone(game.color, p), height: 1.2),
          ),
        ),
      );
    }

    final fill = barFill(game.color, p, tentative: tentative);
    final fade = !e.endConfirmed && !seg.contRight;
    final label = statusLabel(e.status);
    final newFirst = [...e.characters.where((c) => c.isNew), ...e.characters.where((c) => !c.isNew)];
    final text = newFirst.isEmpty ? e.title : newFirst.map((c) => c.name).join(', ');

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        alignment: Alignment.centerLeft,
        decoration: BoxDecoration(
          borderRadius: radius,
          border: tentative ? Border.all(color: game.color.withValues(alpha: 0.6), width: 1) : null,
          gradient: LinearGradient(
            colors: fade ? [fill, fill, fill.withValues(alpha: 0)] : [fill, fill],
            stops: fade ? const [0, 0.7, 1] : const [0, 1],
          ),
        ),
        child: Text(
          label == null ? text : '$label $text',
          maxLines: 1,
          overflow: TextOverflow.clip,
          softWrap: false,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: barText(game.color, p, tentative: tentative),
            height: 1.2,
          ),
        ),
      ),
    );
  }
}
