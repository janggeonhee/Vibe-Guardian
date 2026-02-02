# Changelog

## [2.1.0] - 2026-02-02

### Added
- **세션/컨텍스트 유지 기능**: 이전 대화 내용을 기억하고 이어서 작업 가능
  - `-c` / `--continue`: 마지막 세션 이어서 작업
  - `--session <ID>`: 특정 세션 로드
  - `--sessions`: 세션 목록 확인
- **SessionManager 클래스**: 세션 생성, 로드, 저장, 목록 관리
- **ContextEntry 구조**: 역할, 내용, 타임스탬프, 명령어, 토큰 수 저장
- `.vbg_sessions/` 디렉토리에 세션 데이터 JSON 저장
- 세션 만료 기능 (24시간 후 만료)
- 컨텍스트 토큰 제한 (최대 4000 토큰)

### Changed
- VBGCore 생성자에 `continue_session`, `session_id` 파라미터 추가
- 모든 분석 명령에서 이전 컨텍스트 참조 가능
- show_usage에 세션 정보 표시 추가

### Constants Added
```python
SESSION_DIR = ".vbg_sessions"
CURRENT_SESSION_FILE = ".vbg_current_session"
MAX_CONTEXT_HISTORY = 10
MAX_CONTEXT_TOKENS = 4000
SESSION_EXPIRY_HOURS = 24
```

---

## [2.0.0] - 2026-02-02

### Added
- **병렬 실행 모드**: Claude + Gemini 동시 호출로 속도 약 40% 향상
  - `--sequential` / `--seq` / `-s` 옵션으로 순차 실행 가능
  - 설정: `execution.parallel` (기본값: true)
- **스마트 파일 선택**: 중요도 기반 파일 선택 알고리즘 (`select_important_files`)
- **토큰 추정 개선**: 영어/한글/특수문자 구분 계산 (`estimate_tokens`)
- **설정 검증**: config 로드 시 유효성 검사 (`validate_config`)
- **리포트 저장**: 모든 분석 결과 `.vbg_reports/` 디렉토리에 자동 저장
- **사용자 입력 검증**: 길이 제한 및 안전한 입력 처리
- **새 프로젝트 생성 완성**: 블루프린트 → 실제 파일 생성 흐름 구현

### Changed
- **벤치마크 측정 개선**: 실행 중 피크 메모리 측정 (백그라운드 스레드)
- **예외 처리 강화**: bare `except:` 제거, 구체적인 예외 타입 지정
- **가독성 개선**: `chr(10)` → `"\n"`, 매직 넘버 → 상수화

### Fixed
- 가짜 벤치마크 결과 제거 (하드코딩된 15% 개선치)
- 리포트 디렉토리 미생성 문제
- Antigravity 워크플로우 미연동 문제

### Constants Added
```python
MAX_FILES_FOR_PROMPT = 30
MAX_FILES_FOR_REFACTOR = 20
MAX_FILES_FOR_UI = 20
MAX_USER_INPUT_LENGTH = 2000
MAX_PROJECT_NAME_LENGTH = 100
DEFAULT_COMMAND_TIMEOUT = 300
BENCHMARK_TIMEOUT = 60
TOKENS_PER_WORD = 1.3
TOKENS_PER_CHAR = 0.25
```

---

## [1.0.0] - Initial Release

- Claude + Gemini + Antigravity 협업 시스템
- 리팩토링, 추천, UI/UX, 분석, 계획, 신규 프로젝트 모드
- 프로젝트 타입 자동 감지 (Next.js, React, Spring Boot, Python)
- 성능 벤치마킹
- Fallback 모드 (자가 치유)
