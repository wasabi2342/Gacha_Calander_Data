import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'theme.dart';

/// 게임별 가로 줄 + 날짜 가로축. 픽업 기간은 막대, 버전 업데이트는 마름모로 표시.
/// - 날짜 헤더는 위에 고정, 게임 이름은 왼쪽에 고정
/// - 추정/유출 일정: 옅은 막대 + 테두리
/// - 종료일이 확정되지 않은 픽업: 막대 끝이 흐려짐
/// - 막대 시작이 화면 왼쪽 밖이면 글자가 화면 안쪽에 붙어서 따라옴
class TimelineView extends StatefulWidget {
  final List<Game> games;
  final List<ScheduleEvent> events;
  final void Function(ScheduleEvent) onTap;

  const TimelineView({super.key, required this.games, required this.events, required this.onTap});

  @override
  State<TimelineView> createState() => _TimelineViewState();
}

class _TimelineViewState extends State<TimelineView> {
  static const dayW = 30.0;
  static const labelW = 112.0;
  static const headerH = 50.0;
  static const laneH = 34.0;
  static const versionH = 22.0;
  static const rowPad = 8.0;
  static const daysBefore = 14;
  static const totalDays = 100;

  /// 막대 글자가 따라올 때 오른쪽 끝에 최소한 남겨둘 공간
  static const minLabelRoom = 90.0;

  late final DateTime _rangeStart = dateOnly(kstNow()).subtract(const Duration(days: daysBefore));
  late final ScrollController _h = ScrollController(initialScrollOffset: (daysBefore - 2) * dayW);
  final ScrollController _vBody = ScrollController();
  final ScrollController _vLabels = ScrollController();
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    // 본문과 게임 이름 열의 세로 스크롤을 서로 맞춘다
    _vBody.addListener(() => _sync(_vBody, _vLabels));
    _vLabels.addListener(() => _sync(_vLabels, _vBody));
  }

  @override
  void dispose() {
    _h.dispose();
    _vBody.dispose();
    _vLabels.dispose();
    super.dispose();
  }

  void _sync(ScrollController from, ScrollController to) {
    if (_syncing || !from.hasClients || !to.hasClients) return;
    _syncing = true;
    final target = from.offset.clamp(to.position.minScrollExtent, to.position.maxScrollExtent).toDouble();
    if (to.offset != target) to.jumpTo(target);
    _syncing = false;
  }

  double get _scrollX => _h.hasClients ? _h.offset : _h.initialScrollOffset;

  double _dx(DateTime t) => t.difference(_rangeStart).inMinutes / 1440 * dayW;

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    if (widget.games.isEmpty) {
      return const Center(child: Text('위에서 볼 게임을 하나 이상 골라 주세요.'));
    }

    final rows = <_Row>[];
    var y = 0.0;
    for (final g in widget.games) {
      final row = _Row.layout(g, widget.events.where((e) => e.gameId == g.id).toList(), y);
      rows.add(row);
      y += row.height;
    }
    final bodyH = y + 16;
    final now = kstNow();
    final headerBorder = BoxDecoration(border: Border(bottom: BorderSide(color: p.line)));

    return LayoutBuilder(builder: (context, constraints) {
      final height = constraints.maxHeight;
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 왼쪽: 게임 이름 (세로로만 움직임)
          SizedBox(
            width: labelW,
            height: height,
            child: Column(children: [
              Container(height: headerH, decoration: headerBorder),
              Expanded(
                child: SingleChildScrollView(
                  controller: _vLabels,
                  child: SizedBox(
                    height: bodyH,
                    child: Stack(children: [
                      for (final r in rows)
                        Positioned(
                          top: r.top,
                          left: 0,
                          right: 0,
                          height: r.height,
                          child: _GameLabel(game: r.game),
                        ),
                    ]),
                  ),
                ),
              ),
            ]),
          ),
          // 오른쪽: 날짜 헤더(가로로만) + 본문(가로·세로)
          Expanded(
            child: SingleChildScrollView(
              controller: _h,
              scrollDirection: Axis.horizontal,
              child: SizedBox(
                width: totalDays * dayW,
                height: height,
                child: Column(children: [
                  Container(
                    height: headerH,
                    decoration: headerBorder,
                    child: Stack(children: _header(now)),
                  ),
                  Expanded(
                    child: SingleChildScrollView(
                      controller: _vBody,
                      child: SizedBox(
                        height: bodyH,
                        child: Stack(children: [
                          Positioned.fill(
                            child: CustomPaint(
                              painter: _GridPainter(
                                start: _rangeStart,
                                days: totalDays,
                                dayW: dayW,
                                rowBottoms: rows.map((r) => r.top + r.height).toList(),
                                weekendColor: p.cell,
                                lineColor: p.line,
                              ),
                            ),
                          ),
                          Positioned.fill(
                            child: AnimatedBuilder(
                              animation: _h,
                              builder: (context, _) => Stack(children: [
                                for (final r in rows) ..._rowChildren(r, now),
                              ]),
                            ),
                          ),
                          Positioned(
                            left: _dx(now) - 1,
                            top: 0,
                            bottom: 0,
                            width: 2,
                            child: IgnorePointer(child: ColoredBox(color: p.ink)),
                          ),
                        ]),
                      ),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        ],
      );
    });
  }

  List<Widget> _header(DateTime now) {
    final p = context.pal;
    final today = dateOnly(now);
    final cells = <Widget>[];
    for (var i = 0; i < totalDays; i++) {
      final d = _rangeStart.add(Duration(days: i));
      final isToday = d == today;
      final showMonth = i == 0 || d.day == 1;
      cells.add(Positioned(
        left: i * dayW,
        top: 4,
        width: dayW,
        height: headerH - 4,
        child: Column(
          children: [
            SizedBox(
              height: 14,
              child: showMonth
                  ? OverflowBox(
                      maxWidth: 60,
                      alignment: Alignment.centerLeft,
                      child: Text('${d.month}월', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
                    )
                  : null,
            ),
            const SizedBox(height: 3),
            Container(
              width: 22,
              height: 22,
              alignment: Alignment.center,
              decoration: isToday ? BoxDecoration(color: p.todayBadge, shape: BoxShape.circle) : null,
              child: Text(
                '${d.day}',
                style: TextStyle(
                  fontSize: 11.5,
                  fontWeight: isToday ? FontWeight.w700 : FontWeight.w500,
                  color: isToday ? Colors.white : (d.weekday == 7 ? p.sunday : (d.weekday == 6 ? p.saturday : p.ink)),
                ),
              ),
            ),
          ],
        ),
      ));
    }
    return cells;
  }

  List<Widget> _rowChildren(_Row r, DateTime now) {
    final p = context.pal;
    final color = r.game.color;
    final children = <Widget>[];

    if (r.versions.isEmpty && r.lanes.isEmpty) {
      children.add(Positioned(
        left: math.max(_scrollX, _dx(now)) + 10,
        top: r.top + r.height / 2 - 9,
        child: Text('아직 수집된 일정이 없어요', style: TextStyle(fontSize: 12, color: p.muted)),
      ));
      return children;
    }

    for (final v in r.versions) {
      children.add(Positioned(
        left: _dx(v.startAt) - 5,
        top: r.top + rowPad,
        height: versionH,
        child: GestureDetector(
          onTap: () => widget.onTap(v),
          child: _VersionMarker(event: v, color: color),
        ),
      ));
    }

    for (var lane = 0; lane < r.lanes.length; lane++) {
      for (final b in r.lanes[lane]) {
        final x0 = math.max(_dx(b.startAt), 0.0);
        final x1 = _dx(b.displayEnd);
        if (x1 <= 0) continue;
        final width = math.max(x1 - x0, 28.0);
        final inset = (_scrollX - x0).clamp(0.0, math.max(0.0, width - minLabelRoom)).toDouble();
        children.add(Positioned(
          left: x0,
          top: r.top + rowPad + versionH + lane * laneH,
          width: width,
          height: laneH - 6,
          child: _BannerBar(event: b, color: color, textInset: inset, onTap: () => widget.onTap(b)),
        ));
      }
    }
    return children;
  }
}

/// 한 게임 줄의 배치 결과. 겹치는 픽업은 서로 다른 lane에 쌓는다.
class _Row {
  final Game game;
  final double top;
  final List<ScheduleEvent> versions;
  final List<List<ScheduleEvent>> lanes;

  _Row(this.game, this.top, this.versions, this.lanes);

  double get height =>
      _TimelineViewState.rowPad * 2 +
      _TimelineViewState.versionH +
      math.max(1, lanes.length) * _TimelineViewState.laneH;

  static _Row layout(Game game, List<ScheduleEvent> events, double top) {
    final versions = events.where((e) => !e.isBanner).toList();
    final banners = events.where((e) => e.isBanner).toList()..sort((a, b) => a.startAt.compareTo(b.startAt));

    final lanes = <List<ScheduleEvent>>[];
    final laneEnds = <DateTime>[];
    for (final b in banners) {
      var placed = false;
      for (var i = 0; i < lanes.length; i++) {
        if (!laneEnds[i].isAfter(b.startAt)) {
          lanes[i].add(b);
          laneEnds[i] = b.displayEnd;
          placed = true;
          break;
        }
      }
      if (!placed) {
        lanes.add([b]);
        laneEnds.add(b.displayEnd);
      }
    }
    return _Row(game, top, versions, lanes);
  }
}

class _GameLabel extends StatelessWidget {
  final Game game;

  const _GameLabel({required this.game});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: 14, right: 8),
      decoration: BoxDecoration(border: Border(bottom: BorderSide(color: context.pal.line))),
      child: Row(children: [
        Container(width: 4, height: 18, color: game.color),
        const SizedBox(width: 8),
        // 한글은 글자 단위로 줄바꿈되니, 한 줄로 두고 길면 살짝 줄인다
        Expanded(
          child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              game.name,
              maxLines: 1,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
          ),
        ),
      ]),
    );
  }
}

class _VersionMarker extends StatelessWidget {
  final ScheduleEvent event;
  final Color color;

  const _VersionMarker({required this.event, required this.color});

  @override
  Widget build(BuildContext context) {
    final tentative = event.status != EventStatus.official;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Transform.rotate(
        angle: math.pi / 4,
        child: Container(
          width: 9,
          height: 9,
          decoration: BoxDecoration(
            color: tentative ? context.pal.bg : color,
            border: Border.all(color: color, width: 1.6),
          ),
        ),
      ),
      const SizedBox(width: 6),
      Text(
        '${event.hasVersionNumber ? '${event.version} ' : ''}업데이트${tentative ? ' (${statusLabel(event.status)})' : ''}',
        style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: tone(color, context.pal)),
      ),
    ]);
  }
}

class _BannerBar extends StatelessWidget {
  final ScheduleEvent event;
  final Color color;

  /// 막대 왼쪽이 화면 밖일 때 글자를 안쪽으로 밀어 넣는 거리
  final double textInset;
  final VoidCallback onTap;

  const _BannerBar({required this.event, required this.color, required this.textInset, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final tentative = event.status != EventStatus.official;
    final fill = tentative ? color.withValues(alpha: 0.16) : color;
    final textColor = tentative ? tone(color, context.pal) : Colors.white;
    final fade = !event.endConfirmed;
    final label = statusLabel(event.status);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.only(left: 8 + textInset, right: 8),
        alignment: Alignment.centerLeft,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(6),
          border: tentative ? Border.all(color: color.withValues(alpha: 0.7), width: 1.2) : null,
          gradient: LinearGradient(
            colors: fade ? [fill, fill, fill.withValues(alpha: 0)] : [fill, fill],
            stops: fade ? const [0, 0.8, 1] : const [0, 1],
          ),
        ),
        child: Text.rich(
          TextSpan(children: [
            if (label != null) TextSpan(text: '$label  ', style: const TextStyle(fontWeight: FontWeight.w700)),
            if (event.characters.isEmpty) TextSpan(text: event.title),
            for (var i = 0; i < event.characters.length; i++)
              TextSpan(
                text: '${i > 0 ? ', ' : ''}${event.characters[i].name}',
                style: TextStyle(fontWeight: event.characters[i].isNew ? FontWeight.w700 : FontWeight.w400),
              ),
          ]),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(color: textColor, fontSize: 12.5),
        ),
      ),
    );
  }
}

class _GridPainter extends CustomPainter {
  final DateTime start;
  final int days;
  final double dayW;
  final List<double> rowBottoms;
  final Color weekendColor;
  final Color lineColor;

  _GridPainter({
    required this.start,
    required this.days,
    required this.dayW,
    required this.rowBottoms,
    required this.weekendColor,
    required this.lineColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final weekend = Paint()..color = weekendColor;
    final line = Paint()
      ..color = lineColor
      ..strokeWidth = 1;
    final monthLine = Paint()
      ..color = lineColor
      ..strokeWidth = 1.5;

    for (var i = 0; i < days; i++) {
      final d = start.add(Duration(days: i));
      final x = i * dayW;
      if (d.weekday >= 6) {
        canvas.drawRect(Rect.fromLTWH(x, 0, dayW, size.height), weekend);
      }
      if (d.day == 1) {
        canvas.drawLine(Offset(x, 0), Offset(x, size.height), monthLine);
      }
    }
    for (final y in rowBottoms) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
    }
  }

  @override
  bool shouldRepaint(covariant _GridPainter old) => true;
}
