import 'package:flutter/material.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'theme.dart';

/// 날짜별로 묶은 "다가오는 일정" 목록. 곧 끝나는 픽업도 함께 보여준다.
class UpcomingList extends StatelessWidget {
  final Map<String, Game> gamesById;
  final List<ScheduleEvent> events;
  final void Function(ScheduleEvent) onTap;

  static const horizonDays = 60;
  static const endingSoonDays = 10;

  const UpcomingList({super.key, required this.gamesById, required this.events, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final children = upcomingChildren(context, gamesById: gamesById, events: events, onTap: onTap);
    if (children.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text('앞으로 $horizonDays일 안에 잡힌 일정이 없어요.\n메뉴에서 게임을 더 골라 보세요.',
              textAlign: TextAlign.center, style: TextStyle(color: context.pal.muted)),
        ),
      );
    }
    return ListView(padding: const EdgeInsets.only(bottom: 24), children: children);
  }
}

/// 날짜별로 묶은 "다가오는 일정" 항목들 (목록 보기에서도 같이 씀). 없으면 빈 목록.
List<Widget> upcomingChildren(
  BuildContext context, {
  required Map<String, Game> gamesById,
  required List<ScheduleEvent> events,
  required void Function(ScheduleEvent) onTap,
  EdgeInsets tilePadding = const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
  EdgeInsets headerPadding = const EdgeInsets.fromLTRB(16, 20, 16, 8),
}) {
  final now = kstNow();
  final items = <_Item>[];
  for (final e in events) {
    if (gamesById[e.gameId] == null) continue;
    if (e.startAt.isAfter(now) && e.startAt.isBefore(now.add(const Duration(days: UpcomingList.horizonDays)))) {
      items.add(_Item(e.startAt, e, isEnd: false));
    }
    final end = e.endAt;
    if (e.isBanner && end != null && end.isAfter(now) &&
        end.isBefore(now.add(const Duration(days: UpcomingList.endingSoonDays)))) {
      items.add(_Item(end, e, isEnd: true));
    }
  }
  items.sort((a, b) => a.date.compareTo(b.date));

  final children = <Widget>[];
  DateTime? currentDay;
  for (final item in items) {
    final day = dateOnly(item.date);
    if (day != currentDay) {
      currentDay = day;
      children.add(_DayHeader(day: day, now: now, padding: headerPadding));
    }
    children.add(_UpcomingTile(
      item: item,
      game: gamesById[item.event.gameId]!,
      padding: tilePadding,
      onTap: () => onTap(item.event),
    ));
  }
  return children;
}

class _Item {
  final DateTime date;
  final ScheduleEvent event;
  final bool isEnd;

  _Item(this.date, this.event, {required this.isEnd});
}

class _DayHeader extends StatelessWidget {
  final DateTime day;
  final DateTime now;
  final EdgeInsets padding;

  const _DayHeader({required this.day, required this.now, required this.padding});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Row(children: [
        Text(fmtDate(day), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
        const Spacer(),
        Text(dDay(day, now), style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: context.pal.muted)),
      ]),
    );
  }
}

class _UpcomingTile extends StatelessWidget {
  final _Item item;
  final Game game;
  final EdgeInsets padding;
  final VoidCallback onTap;

  const _UpcomingTile({required this.item, required this.game, required this.padding, required this.onTap});

  String get _headline {
    final e = item.event;
    if (!e.isBanner) return e.title.contains('업데이트') ? e.title : '${e.title} 업데이트';
    if (item.isEnd) return '${e.title} 종료${e.endConfirmed ? '' : ' (추정)'}';
    return '${e.title} 시작';
  }

  String? get _characters {
    final chars = item.event.characters;
    if (chars.isEmpty) return null;
    return chars.map((c) => c.isNew ? c.name : '${c.name}(복각)').join(', ');
  }

  String? get _time {
    final e = item.event;
    if (item.isEnd) return e.endConfirmed ? '${two(item.date.hour)}:${two(item.date.minute)}까지' : null;
    return e.timeKnown ? '${two(e.startAt.hour)}:${two(e.startAt.minute)}부터' : null;
  }

  @override
  Widget build(BuildContext context) {
    final chars = _characters;
    final time = _time;
    return Padding(
      padding: padding,
      child: Material(
        color: context.pal.cell,
        borderRadius: BorderRadius.circular(10),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: IntrinsicHeight(
            child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Container(width: 5, color: item.isEnd ? game.color.withValues(alpha: 0.35) : game.color),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Text(game.name,
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: tone(game.color, context.pal))),
                      if (time != null) ...[
                        const SizedBox(width: 8),
                        Text(time, style: TextStyle(fontSize: 12, color: context.pal.muted)),
                      ],
                      const Spacer(),
                      StatusTag(status: item.event.status, color: game.color),
                    ]),
                    const SizedBox(height: 4),
                    Text(_headline, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                    if (chars != null) ...[
                      const SizedBox(height: 2),
                      Text(chars, style: TextStyle(fontSize: 13.5, color: context.pal.muted)),
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
