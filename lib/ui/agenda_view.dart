import 'package:flutter/material.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'month_view.dart';
import 'pickup_widgets.dart';
import 'upcoming_list.dart';

/// 목록 보기: 마감 임박 → 진행 중 → 다가오는 일정(날짜별)
class AgendaView extends StatelessWidget {
  final List<ScheduleEvent> events;
  final Map<String, Game> games;
  final DateTime now;
  final void Function(ScheduleEvent) onTapEvent;
  final Future<void> Function() onRefresh;

  const AgendaView({
    super.key,
    required this.events,
    required this.games,
    required this.now,
    required this.onTapEvent,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final active = events.where((e) => e.isBanner && games[e.gameId] != null && occursOn(e, dateOnly(now))).toList()
      ..sort((a, b) => dayRange(a).last.compareTo(dayRange(b).last));
    final urgent = active.where((e) => PickupProgress.of(e, now).urgent).toList();
    final ongoing = active.where((e) => !PickupProgress.of(e, now).urgent).toList();
    final upcoming = upcomingChildren(
      context,
      gamesById: games,
      events: events,
      onTap: onTapEvent,
      tilePadding: const EdgeInsets.symmetric(vertical: 4),
      headerPadding: const EdgeInsets.fromLTRB(2, 16, 2, 6),
    );

    Widget card(ScheduleEvent e) =>
        PickupCard(event: e, game: games[e.gameId]!, now: now, onPanel: false, onTap: () => onTapEvent(e));

    return RefreshIndicator(
      onRefresh: onRefresh,
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: EdgeInsets.fromLTRB(16, 0, 16, 24 + MediaQuery.paddingOf(context).bottom),
            children: [
              if (urgent.isNotEmpty) ...[
                const SectionLabel('마감 임박 · 3일 이내', urgent: true),
                for (final e in urgent) card(e),
              ],
              const SectionLabel('진행 중'),
              if (ongoing.isEmpty) const EmptyNote('진행 중인 픽업이 없어요.'),
              for (final e in ongoing) card(e),
              const SectionLabel('다가오는 일정'),
              if (upcoming.isEmpty) const EmptyNote('앞으로 60일 안에 잡힌 일정이 없어요.'),
              ...upcoming,
            ],
          ),
        ),
      ),
    );
  }
}
