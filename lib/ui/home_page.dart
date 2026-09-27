import 'dart:async';

import 'package:flutter/material.dart';

import '../config.dart';
import '../data/kst.dart';
import '../data/schedule_repository.dart';
import '../models/schedule.dart';
import 'agenda_view.dart';
import 'day_panel.dart';
import 'event_sheet.dart';
import 'month_view.dart';
import 'theme.dart';
import 'timeline_view.dart';
import 'upcoming_list.dart';

enum CalendarMode { month, list, timeline }

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with WidgetsBindingObserver {
  final _repo = ScheduleRepository();
  ScheduleData? _data;
  Map<String, String> _holidays = const {};
  Set<String> _hidden = {};
  CalendarMode _mode = CalendarMode.month;
  bool _refreshing = false;

  /// 처음 불러오기에 실패했을 때 이유 (저장된 일정도 없을 때만 화면에 보임)
  String? _loadError;

  late DateTime _today = dateOnly(kstNow());
  late DateTime _selected = _today;

  late final int _todayPage = monthIndexOf(_today);
  late final PageController _pages = PageController(initialPage: _todayPage);
  late int _page = _todayPage;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _init();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pages.dispose();
    super.dispose();
  }

  /// 앱으로 돌아오면: 날짜가 바뀌었으면 오늘을 갱신하고, 새 일정을 조용히 받아 온다
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) return;
    final t = dateOnly(kstNow());
    if (t != _today) setState(() => _today = t);
    _refresh(silent: true);
  }

  Future<void> _init() async {
    final hidden = await _repo.loadHidden();
    final modeName = await _repo.loadMode();
    final holidays = await _repo.loadHolidays();
    final cached = await _repo.loadCached();
    if (!mounted) return;
    setState(() {
      _hidden = hidden;
      _mode = CalendarMode.values.firstWhere((m) => m.name == modeName, orElse: () => CalendarMode.month);
      _holidays = holidays;
      // 저장된 일정이 비어 있으면 없는 것으로 본다
      if (cached != null && cached.events.isNotEmpty) _data = cached;
    });
    await _refresh(silent: _data != null);
  }

  /// 네트워크에서 새로 받기.
  /// - 받았는데 수집된 일정이 0개면 → 예시 일정
  /// - 못 받았으면 → 저장된 일정 유지, 그것도 없으면 오류 화면 (예시로 가리지 않는다)
  Future<void> _refresh({bool silent = false}) async {
    if (_refreshing) return;
    _refreshing = true;
    try {
      var fresh = await _repo.fetch();
      if (fresh.events.isEmpty) fresh = await _repo.loadSample();
      if (mounted) {
        setState(() {
          _data = fresh;
          _loadError = null;
        });
      }
    } catch (e) {
      if (!mounted) return;
      if (!isDataUrlConfigured) {
        // 데이터 주소를 아직 안 넣었을 때만 예시로 보여준다
        final sample = await _repo.loadSample();
        if (mounted) setState(() => _data = sample);
      } else if (_data == null) {
        setState(() => _loadError = _describeError(e));
      } else if (!silent) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('새 일정을 받지 못했어요. 저장된 일정을 보여줄게요.')),
        );
      }
    } finally {
      _refreshing = false;
    }
  }

  void _toggle(String id) {
    setState(() => _hidden.contains(id) ? _hidden.remove(id) : _hidden.add(id));
    _repo.saveHidden(_hidden);
  }

  void _setMode(CalendarMode m) {
    setState(() => _mode = m);
    _repo.saveMode(m.name);
  }

  void _goToday() {
    final t = dateOnly(kstNow());
    setState(() {
      _today = t;
      _selected = t;
    });
    if (_mode != CalendarMode.month) _setMode(CalendarMode.month);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_pages.hasClients) {
        _pages.animateToPage(monthIndexOf(t), duration: const Duration(milliseconds: 300), curve: Curves.easeOutCubic);
      }
    });
  }

  void _selectDay(DateTime day) {
    setState(() => _selected = day);
    final i = monthIndexOf(day);
    if (i != _page && _pages.hasClients) {
      _pages.animateToPage(i, duration: const Duration(milliseconds: 300), curve: Curves.easeOutCubic);
    }
  }

  void _onPageChanged(int i) {
    setState(() {
      _page = i;
      // 넘긴 달에 선택한 날이 없으면: 이번 달이면 오늘, 아니면 1일
      final m = monthOfIndex(i);
      if (_selected.year != m.year || _selected.month != m.month) {
        _selected = (_today.year == m.year && _today.month == m.month) ? _today : m;
      }
    });
  }

  String get _title {
    switch (_mode) {
      case CalendarMode.timeline:
        return '타임라인';
      case CalendarMode.list:
        return '일정';
      case CalendarMode.month:
        final m = monthOfIndex(_page);
        return m.year == _today.year ? '${m.month}월' : '${m.year}년 ${m.month}월';
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    final gamesById = {for (final g in data?.games ?? const <Game>[]) g.id: g};
    final visibleGames = (data?.games ?? const <Game>[]).where((g) => !_hidden.contains(g.id)).toList();
    final visibleIds = visibleGames.map((g) => g.id).toSet();
    final visibleGamesById = {for (final g in visibleGames) g.id: g};
    final events = (data?.events ?? const <ScheduleEvent>[]).where((e) => visibleIds.contains(e.gameId)).toList();

    void openEvent(ScheduleEvent e) {
      final g = gamesById[e.gameId];
      if (g != null) showEventSheet(context, e, g);
    }

    Widget body;
    if (data == null) {
      body = _loadError == null ? const Center(child: CircularProgressIndicator()) : _errorView(_loadError!);
    } else {
      final Widget content = switch (_mode) {
        CalendarMode.month => _monthBody(events, visibleGamesById, openEvent),
        CalendarMode.list => AgendaView(
            events: events,
            games: visibleGamesById,
            now: kstNow(),
            onTapEvent: openEvent,
            onRefresh: _refresh,
          ),
        CalendarMode.timeline => Stack(children: [
            Positioned.fill(
              child: Padding(
                padding: const EdgeInsets.only(bottom: 76),
                child: TimelineView(games: visibleGames, events: events, onTap: openEvent),
              ),
            ),
            Positioned(
              left: 0,
              right: 0,
              bottom: 16,
              child: Center(
                child: _NextPill(
                  events: events,
                  games: visibleGamesById,
                  onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
                    builder: (_) => Scaffold(
                      appBar: AppBar(
                        title: const Text('다가오는 일정', style: TextStyle(fontWeight: FontWeight.w800)),
                      ),
                      body: UpcomingList(gamesById: visibleGamesById, events: events, onTap: openEvent),
                    ),
                  )),
                ),
              ),
            ),
          ]),
      };
      body = Column(children: [
        if (data.source != DataSource.network) _SampleNotice(source: data.source, configured: isDataUrlConfigured),
        Expanded(child: content),
      ]);
    }

    return Scaffold(
      drawer: data == null
          ? null
          : _AppDrawer(
              data: data,
              hidden: _hidden,
              onToggle: _toggle,
              mode: _mode,
              onMode: _setMode,
              today: _today,
            ),
      appBar: AppBar(
        toolbarHeight: 64,
        title: Text(_title, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), tooltip: '새로고침', onPressed: () => _refresh()),
          _TodayButton(day: _today.day, onTap: _goToday),
          const SizedBox(width: 10),
        ],
      ),
      body: body,
    );
  }

  String _describeError(Object e) {
    if (e is TimeoutException) return '서버 응답이 너무 늦어요 (10초 초과).';
    final msg = e.toString();
    if (msg.contains('HTTP 404')) return '데이터 파일을 찾지 못했어요 (404). lib/config.dart의 주소를 확인해 주세요.';
    return '일정을 불러오지 못했어요. 인터넷 연결을 확인해 주세요.\n($msg)';
  }

  Widget _errorView(String message) {
    final p = context.pal;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.cloud_off_outlined, size: 48, color: p.muted),
          const SizedBox(height: 16),
          Text(message, textAlign: TextAlign.center, style: TextStyle(fontSize: 14, color: p.muted, height: 1.5)),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () {
              setState(() => _loadError = null);
              _refresh();
            },
            icon: const Icon(Icons.refresh),
            label: const Text('다시 시도'),
          ),
        ]),
      ),
    );
  }

  /// 달력 + 선택한 날. 폰은 위아래, 넓은 화면(태블릿·웹·데스크톱)은 좌우로 놓는다
  Widget _monthBody(
    List<ScheduleEvent> events,
    Map<String, Game> games,
    void Function(ScheduleEvent) openEvent,
  ) {
    final p = context.pal;
    final now = kstNow();

    Widget pager() => PageView.builder(
          controller: _pages,
          itemCount: monthPageCount,
          onPageChanged: _onPageChanged,
          itemBuilder: (context, i) => MonthGrid(
            month: monthOfIndex(i),
            events: events,
            games: games,
            selected: _selected,
            holidays: _holidays,
            onTapEvent: openEvent,
            onTapDay: _selectDay,
          ),
        );

    List<Widget> panel() => dayPanelChildren(
          context,
          day: _selected,
          now: now,
          events: events,
          games: games,
          holidays: _holidays,
          onTapEvent: openEvent,
        );

    return LayoutBuilder(builder: (context, c) {
      final bottomInset = MediaQuery.paddingOf(context).bottom;

      if (c.maxWidth >= 900) {
        return Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(child: Padding(padding: const EdgeInsets.only(bottom: 8), child: pager())),
          Container(
            width: 380,
            decoration: BoxDecoration(color: p.panel, border: Border(left: BorderSide(color: p.line))),
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.fromLTRB(18, 16, 18, 24 + bottomInset),
                children: panel(),
              ),
            ),
          ),
        ]);
      }

      // 폰: 달력이 화면의 약 60%, 나머지는 선택한 날 (삼성 캘린더처럼)
      final gridH = c.maxHeight < 500 ? c.maxHeight * 0.6 : (c.maxHeight * 0.6).clamp(300.0, 620.0).toDouble();
      return Column(children: [
        SizedBox(height: gridH, child: pager()),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: p.panel,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            ),
            clipBehavior: Clip.antiAlias,
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.fromLTRB(16, 10, 16, 24 + bottomInset),
                children: [
                  Center(
                    child: Container(
                      width: 36,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(color: p.line, borderRadius: BorderRadius.circular(2)),
                    ),
                  ),
                  ...panel(),
                ],
              ),
            ),
          ),
        ),
      ]);
    });
  }
}

/// 기본 캘린더 오른쪽 위의 "오늘 날짜" 버튼
class _TodayButton extends StatelessWidget {
  final int day;
  final VoidCallback onTap;

  const _TodayButton({required this.day, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return Tooltip(
      message: '오늘',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: 34,
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            border: Border.all(color: p.ink, width: 2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text('$day', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: p.ink)),
        ),
      ),
    );
  }
}

/// 하단 알약 버튼: 가장 가까운 다음 일정을 보여주고, 누르면 "다가오는 일정" 목록 (타임라인 보기에서 사용)
class _NextPill extends StatelessWidget {
  final List<ScheduleEvent> events;
  final Map<String, Game> games;
  final VoidCallback onTap;

  const _NextPill({required this.events, required this.games, required this.onTap});

  String _label() {
    final now = kstNow();
    final upcoming = events.where((e) => e.startAt.isAfter(now) && games[e.gameId] != null).toList()
      ..sort((a, b) => a.startAt.compareTo(b.startAt));
    if (upcoming.isEmpty) return '다가오는 일정 보기';
    final e = upcoming.first;
    final what = e.isBanner
        ? (e.characters.where((c) => c.isNew).map((c) => c.name).firstOrNull ?? e.title)
        : (e.hasVersionNumber ? '${e.version} 업데이트' : e.title);
    return '${e.startAt.month}/${e.startAt.day} ${games[e.gameId]!.name} $what';
  }

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 420),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 40),
        child: Material(
          color: p.pill,
          elevation: p.dark ? 0 : 6,
          shadowColor: Colors.black26,
          shape: const StadiumBorder(),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 15),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.event_note_outlined, size: 20, color: p.muted),
                const SizedBox(width: 10),
                Flexible(
                  child: Text(_label(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 15, color: p.muted, fontWeight: FontWeight.w500)),
                ),
                const SizedBox(width: 10),
                Icon(Icons.chevron_right, color: p.ink),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

class _SampleNotice extends StatelessWidget {
  final DataSource source;
  final bool configured;

  const _SampleNotice({required this.source, required this.configured});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final text = source == DataSource.cache
        ? '인터넷에 연결되지 않아 마지막으로 받은 일정을 보여주고 있어요.'
        : (configured ? '아직 수집된 일정이 없어서 예시 일정을 보여주고 있어요.' : '예시 일정이에요. lib/config.dart에 데이터 주소를 넣어 주세요.');
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(color: p.cell, borderRadius: BorderRadius.circular(8)),
      child: Text(text, style: TextStyle(fontSize: 12.5, color: p.muted)),
    );
  }
}

/// 왼쪽 메뉴: 보기 전환, 게임 켜고 끄기, 데이터 상태
class _AppDrawer extends StatelessWidget {
  final ScheduleData data;
  final Set<String> hidden;
  final void Function(String id) onToggle;
  final CalendarMode mode;
  final void Function(CalendarMode) onMode;
  final DateTime today;

  const _AppDrawer({
    required this.data,
    required this.hidden,
    required this.onToggle,
    required this.mode,
    required this.onMode,
    required this.today,
  });

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final updated = data.updatedAt;
    final status = switch (data.source) {
      DataSource.sample => '예시 일정을 보여주는 중 (수집된 일정 없음)',
      DataSource.cache => updated == null ? '저장된 일정 (오프라인)' : '저장된 일정 · 마지막 변경 ${fmtDateTime(updated)}',
      DataSource.network => updated == null ? '' : '일정 마지막 변경: ${fmtDateTime(updated)}',
    };

    int activeCount(String id) =>
        data.events.where((e) => e.gameId == id && e.isBanner && occursOn(e, today)).length;

    Widget section(String text) => Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 6),
          child: Text(text, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: p.muted)),
        );

    Widget modeTile(CalendarMode m, IconData icon, String label) => ListTile(
          leading: Icon(icon, color: p.ink),
          title: Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
          trailing: mode == m ? Icon(Icons.check, color: p.todayBadge) : null,
          onTap: () {
            onMode(m);
            Navigator.of(context).pop();
          },
        );

    return Drawer(
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 16, 16, 4),
              child: Text('픽업 달력', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
            ),
            if (status.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(status, style: TextStyle(fontSize: 12.5, color: p.muted)),
              ),
            section('보기'),
            modeTile(CalendarMode.month, Icons.calendar_month_outlined, '달력'),
            modeTile(CalendarMode.list, Icons.view_agenda_outlined, '일정 목록'),
            modeTile(CalendarMode.timeline, Icons.timeline, '타임라인'),
            const Divider(height: 24),
            section('게임'),
            for (final g in data.games)
              SwitchListTile(
                dense: true,
                value: !hidden.contains(g.id),
                onChanged: (_) => onToggle(g.id),
                title: Row(children: [
                  Container(width: 10, height: 10, decoration: BoxDecoration(color: g.color, shape: BoxShape.circle)),
                  const SizedBox(width: 10),
                  Flexible(
                    child: Text(g.name,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                  ),
                  if (activeCount(g.id) > 0) ...[
                    const SizedBox(width: 8),
                    Text('진행 중 ${activeCount(g.id)}', style: TextStyle(fontSize: 11.5, color: p.muted)),
                  ],
                ]),
              ),
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 20, 16, 0),
              child: Text(
                '달력 칸을 누르면 그날 진행 중인 픽업이 아래에 나와요. 막대나 카드를 누르면 자세한 정보와 원문 기사를 볼 수 있어요.',
                style: TextStyle(fontSize: 12, height: 1.5),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
