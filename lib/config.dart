/// 앱이 읽는 일정 데이터 주소 (gacha-calendar-data 저장소의 events.json).
/// <계정> 을 본인 GitHub 아이디로 바꾸세요.
/// 실행할 때 --dart-define=DATA_URL=... 로 덮어쓸 수도 있어요.
const dataUrl = String.fromEnvironment(
  'DATA_URL',
  defaultValue: 'https://raw.githubusercontent.com/wasabi2342/Gacha_Calander_Data/main/data/events.json',
);

bool get isDataUrlConfigured => !dataUrl.contains('<');

/// events.json 옆에 holidays.json을 두면 앱이 공휴일을 갱신해요 (없어도 앱에 든 기본값 사용).
String get holidaysUrl => dataUrl.replaceFirst(RegExp(r'events\.json$'), 'holidays.json');
