import 'package:flutter/material.dart';

import '../data/kst.dart';

enum EventType { versionUpdate, banner }

enum EventStatus { official, estimated, leak }

class Game {
  final String id;
  final String name;
  final Color color;

  const Game({required this.id, required this.name, required this.color});

  factory Game.fromJson(Map<String, dynamic> j) => Game(
        id: j['id'] as String,
        name: j['name'] as String,
        color: _parseHex(j['color'] as String? ?? '#888888'),
      );

  static Color _parseHex(String hex) {
    final h = hex.replaceFirst('#', '');
    return Color(int.parse(h.length == 6 ? 'FF$h' : h, radix: 16));
  }
}

class PickupCharacter {
  final String name;
  final int? rarity;
  final bool isNew;

  const PickupCharacter({required this.name, this.rarity, required this.isNew});

  factory PickupCharacter.fromJson(Map<String, dynamic> j) => PickupCharacter(
        name: j['name'] as String,
        rarity: j['rarity'] as int?,
        isNew: j['isNew'] as bool? ?? false,
      );
}

class ScheduleEvent {
  final String id;
  final String gameId;
  final EventType type;
  final String version;
  final int? phase;
  final String title;
  final List<PickupCharacter> characters;

  /// 한국 시간 벽시계 기준 (kst.dart 참고)
  final DateTime startAt;
  final bool timeKnown;
  final DateTime? endAt;
  final bool endConfirmed;
  final EventStatus status;
  final String? note;
  final String? sourceUrl;

  const ScheduleEvent({
    required this.id,
    required this.gameId,
    required this.type,
    required this.version,
    required this.phase,
    required this.title,
    required this.characters,
    required this.startAt,
    required this.timeKnown,
    required this.endAt,
    required this.endConfirmed,
    required this.status,
    this.note,
    this.sourceUrl,
  });

  bool get isBanner => type == EventType.banner;

  /// 버전 번호가 없는 게임(니케, 블루 아카이브 등)은 version 자리에 시작 날짜가 들어온다
  bool get hasVersionNumber => !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(version);

  /// 종료일이 없을 때 타임라인에 그릴 임시 끝 (3주)
  DateTime get displayEnd => endAt ?? startAt.add(const Duration(days: 21));

  factory ScheduleEvent.fromJson(Map<String, dynamic> j) => ScheduleEvent(
        id: j['id'].toString(),
        gameId: j['gameId'] as String,
        type: j['type'] == 'VERSION_UPDATE' ? EventType.versionUpdate : EventType.banner,
        version: j['version'] as String,
        phase: j['phase'] as int?,
        title: j['title'] as String? ?? '',
        characters: ((j['characters'] as List?) ?? const [])
            .map((c) => PickupCharacter.fromJson(c as Map<String, dynamic>))
            .toList(),
        startAt: toKst(DateTime.parse(j['startAt'] as String)),
        timeKnown: j['timeKnown'] as bool? ?? false,
        endAt: j['endAt'] == null ? null : toKst(DateTime.parse(j['endAt'] as String)),
        endConfirmed: j['endConfirmed'] as bool? ?? false,
        status: switch (j['status']) {
          'OFFICIAL' => EventStatus.official,
          'LEAK' => EventStatus.leak,
          _ => EventStatus.estimated,
        },
        note: j['note'] as String?,
        sourceUrl: j['sourceUrl'] as String?,
      );
}
