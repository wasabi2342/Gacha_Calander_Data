import 'package:flutter/material.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'month_view.dart';
import 'pickup_widgets.dart';
import 'theme.dart';

/// 달력 아래(넓은 화면에선 오른쪽)에 붙는 "선택한 날" 내용.
/// 그날 업데이트 → 진행 중인 픽업(종료 임박 순) → 곧 시작하는 일정
List<Widget> dayPanelChildren(
  BuildContext context, {
  required DateTime day,
  required DateTime now,
  required List<ScheduleEvent> events,
  required Map<String, Game> games,
  required Map<String, String> holidays,
  required void Function(ScheduleEvent) onTapEvent,
}) {
  final p = context.pal;
  final d = dateOnly(day);
  final holiday = holidays[dateKey(d)];
  final mine = events.where((e) => games[e.gameId] != null).toList();

  final updates = mine.where((e) => !e.isBanner && dateOnly(e.startAt) == d).toList()
    ..sort((a, b) => a.startAt.compareTo(b.startAt));
  final pickups = mine.where((e) => e.isBanner && occursOn(e, d)).toList()
    ..sort((a, b) => dayRange(a).last.compareTo(dayRange(b).last));
  final soon = mine.where((e) {
    final n = daysBetween(d, e.startAt);
    return n > 0 && n <= 21;
  }).toList()
    ..sort((a, b) => a.startAt.compareTo(b.startAt));

  final rel = dDay(d, now);
  return [
    Row(children: [
      Flexible(
        child: Text(fmtDate(d),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
      ),
      if (holiday != null) ...[
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(color: p.urgentBg, borderRadius: BorderRadius.circular(10)),
          child: Text(holiday, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: p.urgentFg)),
        ),
      ],
      const Spacer(),
      if (rel != '오늘') Text(rel, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: p.muted)),
    ]),
    if (updates.isNotEmpty) ...[
      const SectionLabel('이날 업데이트'),
      for (final e in updates)
        EventRow(
          event: e,
          game: games[e.gameId]!,
          trailing: e.timeKnown ? '${two(e.startAt.hour)}:${two(e.startAt.minute)}' : '시각 미정',
          onTap: () => onTapEvent(e),
        ),
    ],
    SectionLabel('진행 중인 픽업 · ${pickups.length}'),
    if (pickups.isEmpty) const EmptyNote('이날 진행 중인 픽업이 없어요.'),
    for (final e in pickups)
      PickupCard(event: e, game: games[e.gameId]!, now: now, onTap: () => onTapEvent(e)),
    const SectionLabel('곧 시작'),
    if (soon.isEmpty) const EmptyNote('3주 안에 시작하는 일정이 없어요.'),
    for (final e in soon.take(6))
      EventRow(event: e, game: games[e.gameId]!, trailing: startsText(e, now), onTap: () => onTapEvent(e)),
  ];
}
