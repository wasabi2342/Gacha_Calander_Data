import 'package:flutter/material.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'month_view.dart';
import 'theme.dart';

/// 날짜 칸을 눌렀을 때 그날의 일정 목록
void showDaySheet(
  BuildContext context, {
  required DateTime day,
  required List<ScheduleEvent> events,
  required Map<String, Game> games,
  required void Function(ScheduleEvent) onTapEvent,
}) {
  final items = events.where((e) => games[e.gameId] != null && occursOn(e, day)).toList()
    ..sort((a, b) {
      if (a.isBanner != b.isBanner) return a.isBanner ? 1 : -1;
      return a.startAt.compareTo(b.startAt);
    });

  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    backgroundColor: context.pal.surface,
    builder: (sheetContext) {
      final p = sheetContext.pal;
      return SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: MediaQuery.of(sheetContext).size.height * 0.7),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            children: [
              Row(children: [
                Text(fmtDate(day), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
                const Spacer(),
                Text(dDay(day, kstNow()), style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: p.muted)),
              ]),
              const SizedBox(height: 12),
              if (items.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 24),
                  child: Center(child: Text('이 날은 일정이 없어요', style: TextStyle(color: p.muted))),
                ),
              for (final e in items)
                _DayItem(
                  event: e,
                  game: games[e.gameId]!,
                  day: day,
                  onTap: () {
                    Navigator.of(sheetContext).pop();
                    onTapEvent(e);
                  },
                ),
            ],
          ),
        ),
      );
    },
  );
}

class _DayItem extends StatelessWidget {
  final ScheduleEvent event;
  final Game game;
  final DateTime day;
  final VoidCallback onTap;

  const _DayItem({required this.event, required this.game, required this.day, required this.onTap});

  String get _headline {
    final e = event;
    if (!e.isBanner) {
      if (!e.hasVersionNumber) return e.title;
      return e.title.contains('업데이트') ? e.title : '${e.title} 업데이트';
    }
    final r = dayRange(e);
    if (r.first == day) return '${e.title} 시작';
    if (r.last == day) return '${e.title} 종료${e.endConfirmed ? '' : ' (추정)'}';
    return '${e.title} 진행 중';
  }

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final chars = event.characters.map((c) => c.isNew ? c.name : '${c.name}(복각)').join(', ');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Material(
        color: p.cell,
        borderRadius: BorderRadius.circular(10),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: IntrinsicHeight(
            child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Container(width: 5, color: game.color),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Text(game.name,
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: tone(game.color, p))),
                      const Spacer(),
                      StatusTag(status: event.status, color: game.color),
                    ]),
                    const SizedBox(height: 3),
                    Text(_headline, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                    if (chars.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(chars, style: TextStyle(fontSize: 13, color: p.muted)),
                    ],
                  ]),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
