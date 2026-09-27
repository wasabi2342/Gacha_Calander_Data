import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';
import '../models/schedule.dart';
import 'kst.dart';

/// 지금 보여주는 일정이 어디서 왔는지
enum DataSource { network, cache, sample }

class ScheduleData {
  final List<Game> games;
  final List<ScheduleEvent> events;
  final DataSource source;

  /// 데이터 파일이 마지막으로 바뀐 시각 (KST)
  final DateTime? updatedAt;

  const ScheduleData({
    required this.games,
    required this.events,
    required this.source,
    this.updatedAt,
  });

  /// 최신 데이터를 못 받아서 내장 샘플을 보여주는 중인지
  bool get fromSample => source == DataSource.sample;
}

/// GitHub 저장소의 events.json 한 파일만 읽는다.
/// 1) 기기에 저장해 둔 마지막 데이터를 먼저 보여주고  2) 네트워크에서 새로 받아 바꾼다.
/// 둘 다 없을 때만 앱에 들어 있는 샘플을 쓴다.
class ScheduleRepository {
  static const _cacheKey = 'events_cache_v1';
  static const _holidaysKey = 'holidays_cache_v1';
  static const _hiddenKey = 'hidden_games';
  static const _modeKey = 'calendar_mode';

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  /// 저장된 마지막 데이터 (없거나 깨졌으면 null)
  Future<ScheduleData?> loadCached() async {
    if (!isDataUrlConfigured) return null;
    try {
      final raw = (await _prefs).getString(_cacheKey);
      return raw == null ? null : _parse(raw, source: DataSource.cache);
    } catch (_) {
      return null;
    }
  }

  /// 네트워크에서 최신 데이터. 실패하면 예외를 던진다.
  Future<ScheduleData> fetch() async {
    if (!isDataUrlConfigured) throw StateError('데이터 주소가 설정되지 않았어요');
    final res = await http.get(Uri.parse(dataUrl)).timeout(const Duration(seconds: 10));
    if (res.statusCode != 200) throw http.ClientException('HTTP ${res.statusCode}', Uri.parse(dataUrl));
    final body = utf8.decode(res.bodyBytes);
    final data = _parse(body, source: DataSource.network); // 파싱에 성공한 것만 저장
    try {
      await (await _prefs).setString(_cacheKey, body);
    } catch (_) {}
    return data;
  }

  Future<ScheduleData> loadSample() async =>
      _parse(await rootBundle.loadString('assets/seed_events.json'), source: DataSource.sample);

  /// 예전 방식 그대로: 네트워크 → 실패하면 캐시 → 그래도 없으면 샘플
  Future<ScheduleData> load() async {
    try {
      return await fetch();
    } catch (_) {
      return await loadCached() ?? await loadSample();
    }
  }

  ScheduleData _parse(String raw, {required DataSource source}) {
    final j = jsonDecode(raw) as Map<String, dynamic>;
    final updated = j['updatedAt'] as String?;
    final events = <ScheduleEvent>[];
    for (final e in (j['events'] as List? ?? const [])) {
      // 한 건이 이상해도 나머지는 보여준다
      try {
        events.add(ScheduleEvent.fromJson(e as Map<String, dynamic>));
      } catch (_) {}
    }
    return ScheduleData(
      games: (j['games'] as List).map((g) => Game.fromJson(g as Map<String, dynamic>)).toList(),
      events: events,
      source: source,
      updatedAt: updated == null ? null : toKst(DateTime.parse(updated)),
    );
  }

  // ---------------- 공휴일 ----------------

  /// 'YYYY-MM-DD' → 이름. 앱에 든 기본값 + 데이터 저장소에 holidays.json이 있으면 그것도 합친다.
  Future<Map<String, String>> loadHolidays() async {
    Map<String, String> parse(String raw) {
      final m = jsonDecode(raw) as Map<String, dynamic>;
      return {
        for (final e in m.entries)
          if (!e.key.startsWith('_') && e.value is String) e.key: e.value as String,
      };
    }

    final result = <String, String>{};
    try {
      result.addAll(parse(await rootBundle.loadString('assets/holidays.json')));
    } catch (_) {}
    final prefs = await _prefs;
    final cached = prefs.getString(_holidaysKey);
    if (cached != null) {
      try {
        result.addAll(parse(cached));
      } catch (_) {}
    }
    if (isDataUrlConfigured) {
      // 다음 실행 때 쓰도록 조용히 받아 둔다 (없으면 그냥 넘어감)
      unawaited(() async {
        try {
          final res = await http.get(Uri.parse(holidaysUrl)).timeout(const Duration(seconds: 8));
          if (res.statusCode == 200) {
            final body = utf8.decode(res.bodyBytes);
            parse(body);
            await prefs.setString(_holidaysKey, body);
          }
        } catch (_) {}
      }());
    }
    return result;
  }

  // ---------------- 화면 설정 ----------------

  Future<Set<String>> loadHidden() async => ((await _prefs).getStringList(_hiddenKey) ?? const <String>[]).toSet();

  Future<void> saveHidden(Set<String> ids) async => (await _prefs).setStringList(_hiddenKey, ids.toList());

  Future<String?> loadMode() async => (await _prefs).getString(_modeKey);

  Future<void> saveMode(String name) async => (await _prefs).setString(_modeKey, name);
}
