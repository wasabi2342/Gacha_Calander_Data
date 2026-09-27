import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/kst.dart';
import '../models/schedule.dart';
import 'theme.dart';

void showEventSheet(BuildContext context, ScheduleEvent e, Game game) {
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    backgroundColor: context.pal.surface,
    builder: (_) => _EventSheet(event: e, game: game),
  );
}

class _EventSheet extends StatelessWidget {
  final ScheduleEvent event;
  final Game game;

  const _EventSheet({required this.event, required this.game});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final e = event;
    final end = e.endAt;
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(width: 10, height: 10, decoration: BoxDecoration(color: game.color, shape: BoxShape.circle)),
            const SizedBox(width: 8),
            Text(game.name, style: TextStyle(fontWeight: FontWeight.w700, color: tone(game.color, p))),
          ]),
          const SizedBox(height: 8),
          Text(e.title, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text(statusDescription(e.status), style: TextStyle(color: p.muted)),
          const SizedBox(height: 18),
          _InfoRow(label: '시작', value: '${fmtDateTime(e.startAt, withTime: e.timeKnown)}${e.timeKnown ? '' : ', 시각 미정'}'),
          if (e.isBanner)
            _InfoRow(
              label: '종료',
              value: end == null
                  ? '아직 발표 전'
                  : '${fmtDateTime(end, withTime: e.endConfirmed)}${e.endConfirmed ? '' : ' (추정)'}',
            ),
          if (e.characters.isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text('픽업 캐릭터', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final c in e.characters) _CharacterChip(character: c, color: game.color),
            ]),
          ],
          if (e.note != null) ...[
            const SizedBox(height: 16),
            Text(e.note!, style: TextStyle(color: p.muted)),
          ],
          if (e.sourceUrl != null) ...[
            const SizedBox(height: 16),
            Text('출처', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: p.muted)),
            SelectableText(e.sourceUrl!, style: TextStyle(fontSize: 12, color: p.muted)),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () => _openSource(context, e.sourceUrl!),
              icon: const Icon(Icons.open_in_new, size: 18),
              label: const Text('원문 열기'),
            ),
          ],
        ]),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 44, child: Text(label, style: TextStyle(color: context.pal.muted))),
        Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w600))),
      ]),
    );
  }
}

class _CharacterChip extends StatelessWidget {
  final PickupCharacter character;
  final Color color;

  const _CharacterChip({required this.character, required this.color});

  @override
  Widget build(BuildContext context) {
    final p = context.pal;
    final c = character;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: c.isNew ? color.withValues(alpha: p.dark ? 0.28 : 0.14) : p.cell,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text.rich(TextSpan(children: [
        TextSpan(text: c.name, style: const TextStyle(fontWeight: FontWeight.w700)),
        TextSpan(
          text: '  ${c.isNew ? '신규' : '복각'}${c.rarity != null ? ' ${c.rarity}성' : ''}',
          style: TextStyle(fontSize: 12, color: c.isNew ? tone(color, p) : p.muted),
        ),
      ])),
    );
  }
}

Future<void> _openSource(BuildContext context, String url) async {
  final uri = Uri.tryParse(url);
  var ok = false;
  if (uri != null) {
    try {
      ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {}
  }
  if (!ok && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('원문을 열 수 없어요')));
  }
}
