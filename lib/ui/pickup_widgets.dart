import 'package:flutter/material.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'month_view.dart';
import 'theme.dart';

/// 픽업이 오늘 기준 얼마나 남았는지 계산한 값
class PickupProgress {
  final int daysLeft; // 0 = 오늘 종료, 음수 = 이미 끝남
  final double ratio; // 0~1 지나간 비율
  final bool endUnknown; // 종료일 발표 전
  final bool endEstimated; // 종료일이 추정

  const PickupProgress._(this.daysLeft, this.ratio, this.endUnknown, this.endEstimated);

  factory PickupProgress.of(ScheduleEvent e, DateTime now) {
    final r = dayRange(e);
    final today = dateOnly(now);
    final total = daysBetween(r.first, r.last) + 1;
    final done = (daysBetween(r.first, today) + 1).clamp(0, total);
    return PickupProgress._(
      daysBetween(today, r.last),
      total <= 0 ? 0 : done / total,
      e.endAt == null,
      !e.endConfirmed,
    );
  }

  bool get ended => daysLeft < 0;

  /// 3일 이내 종료 (종료일을 알 때만)
  bool get urgent => !endUnknown && !ended && daysLeft <= 3;

  String get badge {
    if (endUnknown) return '진행 중';
    if (ended) return '종료';
    return daysLeft == 0 ? 'D-DAY' : 'D-$daysLeft';
  }
}

/// 픽업 캐릭터 이름: 신규 먼저, 복각은 (복각) 표시
String characterLine(ScheduleEvent e) => [
      ...e.characters.where((c) => c.isNew).map((c) => c.name),
      ...e.characters.where((c) => !c.isNew).map((c) => '${c.name}(복각)'),
    ].join(', ');

/// 진행 중인 픽업 카드: 게임 · 제목 · 캐릭터 · 남은 기간 막대 · D-day
class PickupCard extends StatelessWidget {
  final ScheduleEvent event;
  final Game game;
  final DateTime now;
  final VoidCallback onTap;

  /// true면 흰 카드(회색 패널 위), false면 회색 카드(흰 화면 위)
  final bool onPanel;

  const PickupCard({
    super.key,
    required this.event,
    required this.game,
    required this.now,
    required this.onTap,
    this.onPanel = true,
  });

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final e = event;
    final pr = PickupProgress.of(e, now);
    final chars = characterLine(e);
    final r = dayRange(e);

    final String leftText;
    if (pr.endUnknown) {
      leftText = '종료일 미정';
    } else if (pr.ended) {
      leftText = '${fmtShort(r.last)} 종료됨';
    } else if (pr.daysLeft == 0) {
      final end = e.endAt!;
      leftText = e.endConfirmed ? '오늘 ${two(end.hour)}:${two(end.minute)} 종료' : '오늘 종료 (추정)';
    } else {
      leftText = '종료까지 ${pr.daysLeft}일${pr.endEstimated ? ' (추정)' : ''}';
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: onPanel ? p.surface : p.cell,
        borderRadius: BorderRadius.circular(16),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                GameTile(game: game),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Flexible(
                        child: Text(game.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: tone(game.color, p))),
                      ),
                      const SizedBox(width: 6),
                      StatusTag(status: e.status, color: game.color),
                    ]),
                    Text(e.title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                    if (chars.isNotEmpty)
                      Text(chars,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 12.5, color: p.muted)),
                  ]),
                ),
                const SizedBox(width: 8),
                DBadge(text: pr.badge, urgent: pr.urgent),
              ]),
              const SizedBox(height: 10),
              Row(children: [
                Text('${fmtShort(r.first)} – ${pr.endUnknown ? '미정' : fmtShort(r.last)}',
                    style: TextStyle(fontSize: 12, color: p.muted)),
                const SizedBox(width: 10),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: LinearProgressIndicator(
                      value: pr.endUnknown ? null : pr.ratio,
                      minHeight: 5,
                      color: game.color,
                      backgroundColor: p.chip,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Text(leftText, style: TextStyle(fontSize: 12, color: p.muted)),
              ]),
            ]),
          ),
        ),
      ),
    );
  }
}

/// 한 줄짜리 일정 (업데이트, 곧 시작)
class EventRow extends StatelessWidget {
  final ScheduleEvent event;
  final Game game;
  final String trailing;
  final VoidCallback onTap;

  const EventRow({super.key, required this.event, required this.game, required this.trailing, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final e = event;
    final what = e.isBanner
        ? e.title
        : (e.hasVersionNumber && !e.title.contains('업데이트') ? '${e.title} 업데이트' : e.title);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 44),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Row(children: [
            Container(width: 8, height: 8, decoration: BoxDecoration(color: game.color, shape: BoxShape.circle)),
            const SizedBox(width: 10),
            Text(game.name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: tone(game.color, p))),
            const SizedBox(width: 8),
            Expanded(
              child: Text(what, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5)),
            ),
            const SizedBox(width: 6),
            StatusTag(status: e.status, color: game.color),
            const SizedBox(width: 6),
            Text(trailing, style: TextStyle(fontSize: 12, color: p.muted)),
          ]),
        ),
      ),
    );
  }
}

/// 게임 첫 글자 타일
class GameTile extends StatelessWidget {
  final Game game;
  final double size;

  const GameTile({super.key, required this.game, this.size = 38});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final letter = game.name.isEmpty ? '?' : game.name.characters.first;
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: game.color.withValues(alpha: p.dark ? 0.28 : 0.16),
        borderRadius: BorderRadius.circular(size * 0.3),
      ),
      child: Text(letter,
          style: TextStyle(fontSize: size * 0.4, fontWeight: FontWeight.w800, color: tone(game.color, p))),
    );
  }
}

class DBadge extends StatelessWidget {
  final String text;
  final bool urgent;

  const DBadge({super.key, required this.text, this.urgent = false});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(color: urgent ? p.urgentBg : p.chip, borderRadius: BorderRadius.circular(12)),
      child: Text(text,
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: urgent ? p.urgentFg : p.muted)),
    );
  }
}

class SectionLabel extends StatelessWidget {
  final String text;
  final bool urgent;

  const SectionLabel(this.text, {super.key, this.urgent = false});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 14, 2, 8),
      child: Text(text,
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: urgent ? p.urgentFg : p.muted)),
    );
  }
}

class EmptyNote extends StatelessWidget {
  final String text;

  const EmptyNote(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
        child: Text(text, style: TextStyle(fontSize: 13, color: context.pal.muted)),
      );
}

/// "9.30 19:00 · 4일 후"
String startsText(ScheduleEvent e, DateTime now) {
  final n = daysBetween(now, e.startAt);
  final rel = n == 0 ? '오늘' : (n > 0 ? '$n일 후' : '${-n}일 전');
  final time = e.timeKnown ? ' ${two(e.startAt.hour)}:${two(e.startAt.minute)}' : '';
  return '${fmtShort(e.startAt)}$time · $rel';
}
