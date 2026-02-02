#!/usr/bin/env python3
"""
VBG (Vibe Guardian) - AI Cross-Check Automation Tool
Claude Code + Gemini CLI + Antigravity 협업 시스템
"""

import argparse
import subprocess
import json
import os
import sys
import time
import psutil
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import traceback
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

# ═══════════════════════════════════════════════════════════════════════════════
# 상수 및 설정
# ═══════════════════════════════════════════════════════════════════════════════

VERSION = "2.2.0"
CONFIG_FILE = "vbg_config.json"
PLAN_FILE = "vbg_plan.md"
REPORT_DIR = ".vbg_reports"
SESSION_DIR = ".vbg_sessions"
CURRENT_SESSION_FILE = ".vbg_current_session"
BACKUP_DIR = ".vbg_backups"

# 파일 선택 관련 상수
MAX_FILES_FOR_PROMPT = 30
MAX_FILES_FOR_REFACTOR = 20
MAX_FILES_FOR_UI = 20

# 입력 제한 상수
MAX_USER_INPUT_LENGTH = 2000
MAX_PROJECT_NAME_LENGTH = 100

# 타임아웃 상수 (초)
DEFAULT_COMMAND_TIMEOUT = 300
BENCHMARK_TIMEOUT = 60

# 토큰 추정 상수 (평균적으로 1단어 ≈ 1.3 토큰)
TOKENS_PER_WORD = 1.3
TOKENS_PER_CHAR = 0.25  # 비영어권 문자 고려

# 세션/컨텍스트 관련 상수
MAX_CONTEXT_HISTORY = 10  # 최대 컨텍스트 기록 수
MAX_CONTEXT_TOKENS = 4000  # 컨텍스트에 포함할 최대 토큰
SESSION_EXPIRY_HOURS = 24  # 세션 만료 시간

class Colors:
    """터미널 색상 코드"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 기본 색상
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # 배경 색상
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_YELLOW = "\033[43m"

class ProjectType(Enum):
    """프로젝트 타입"""
    NEXTJS = "nextjs"
    REACT = "react"
    SPRING_BOOT_MAVEN = "spring-boot-maven"
    SPRING_BOOT_GRADLE = "spring-boot-gradle"
    PYTHON = "python"
    UNKNOWN = "unknown"

@dataclass
class BenchmarkResult:
    """벤치마크 결과"""
    execution_time: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    timestamp: str = ""

@dataclass
class SessionStats:
    """세션 통계"""
    claude_calls: int = 0
    gemini_calls: int = 0
    antigravity_calls: int = 0
    total_tokens_used: int = 0
    start_time: float = field(default_factory=time.time)


@dataclass
class ContextEntry:
    """컨텍스트 항목"""
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str
    command: str = ""  # 실행된 명령어 (refactor, recommend 등)
    tokens: int = 0


class SessionManager:
    """세션 및 컨텍스트 관리 클래스"""

    def __init__(self):
        self.session_dir = Path(SESSION_DIR)
        self.session_dir.mkdir(exist_ok=True)
        self.current_session_id: Optional[str] = None
        self.context_history: List[ContextEntry] = []
        self.project_summary: str = ""
        self.session_metadata: Dict[str, Any] = {}

    def create_session(self, project_type: str = "unknown") -> str:
        """새 세션 생성"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session_id = session_id
        self.context_history = []
        self.session_metadata = {
            "id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "project_type": project_type,
            "project_dir": str(Path.cwd()),
            "total_commands": 0
        }
        self._save_current_session_id(session_id)
        self._save_session()
        return session_id

    def load_session(self, session_id: str) -> bool:
        """세션 로드"""
        session_file = self.session_dir / f"{session_id}.json"
        if not session_file.exists():
            return False

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.current_session_id = session_id
            self.session_metadata = data.get("metadata", {})
            self.project_summary = data.get("project_summary", "")
            self.context_history = [
                ContextEntry(**entry) for entry in data.get("context_history", [])
            ]

            # 세션 만료 확인
            created_at = datetime.fromisoformat(self.session_metadata.get("created_at", datetime.now().isoformat()))
            if (datetime.now() - created_at).total_seconds() > SESSION_EXPIRY_HOURS * 3600:
                print_status(f"세션 {session_id}이 만료되었습니다", "warning")
                return False

            return True
        except Exception as e:
            print_status(f"세션 로드 실패: {e}", "error")
            return False

    def load_latest_session(self) -> bool:
        """가장 최근 세션 로드"""
        # 현재 세션 파일에서 ID 읽기
        current_file = Path(CURRENT_SESSION_FILE)
        if current_file.exists():
            try:
                session_id = current_file.read_text().strip()
                if session_id and self.load_session(session_id):
                    return True
            except Exception:
                pass

        # 가장 최근 세션 파일 찾기
        sessions = list(self.session_dir.glob("*.json"))
        if not sessions:
            return False

        latest = max(sessions, key=lambda p: p.stat().st_mtime)
        session_id = latest.stem
        return self.load_session(session_id)

    def add_context(self, role: str, content: str, command: str = ""):
        """컨텍스트 추가"""
        tokens = estimate_tokens(content)
        entry = ContextEntry(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            command=command,
            tokens=tokens
        )
        self.context_history.append(entry)

        # 최대 기록 수 초과 시 오래된 것 제거
        while len(self.context_history) > MAX_CONTEXT_HISTORY:
            self.context_history.pop(0)

        # 토큰 제한 초과 시 오래된 것 제거
        total_tokens = sum(e.tokens for e in self.context_history)
        while total_tokens > MAX_CONTEXT_TOKENS and len(self.context_history) > 1:
            removed = self.context_history.pop(0)
            total_tokens -= removed.tokens

        self.session_metadata["updated_at"] = datetime.now().isoformat()
        self.session_metadata["total_commands"] = self.session_metadata.get("total_commands", 0) + 1
        self._save_session()

    def get_context_prompt(self) -> str:
        """이전 컨텍스트를 프롬프트 형태로 반환"""
        if not self.context_history:
            return ""

        context_parts = ["[이전 대화 컨텍스트]"]

        for entry in self.context_history[-5:]:  # 최근 5개만
            role_label = {"user": "사용자", "assistant": "AI", "system": "시스템"}.get(entry.role, entry.role)
            cmd_info = f" ({entry.command})" if entry.command else ""
            # 너무 긴 내용은 요약
            content = entry.content
            if len(content) > 500:
                content = content[:500] + "... (생략)"
            context_parts.append(f"\n[{role_label}{cmd_info}]\n{content}")

        context_parts.append("\n[현재 요청]")
        return "\n".join(context_parts)

    def set_project_summary(self, summary: str):
        """프로젝트 요약 설정"""
        self.project_summary = summary
        self._save_session()

    def _save_session(self):
        """세션 저장"""
        if not self.current_session_id:
            return

        session_file = self.session_dir / f"{self.current_session_id}.json"
        data = {
            "metadata": self.session_metadata,
            "project_summary": self.project_summary,
            "context_history": [
                {
                    "role": e.role,
                    "content": e.content,
                    "timestamp": e.timestamp,
                    "command": e.command,
                    "tokens": e.tokens
                }
                for e in self.context_history
            ]
        }

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print_status(f"세션 저장 실패: {e}", "warning")

    def _save_current_session_id(self, session_id: str):
        """현재 세션 ID 저장"""
        try:
            Path(CURRENT_SESSION_FILE).write_text(session_id)
        except Exception:
            pass

    def list_sessions(self) -> List[Dict[str, Any]]:
        """세션 목록 반환"""
        sessions = []
        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                metadata = data.get("metadata", {})
                metadata["file"] = session_file.name
                sessions.append(metadata)
            except Exception:
                continue

        # 최신순 정렬
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        session_file = self.session_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False


@dataclass
class CodeChange:
    """코드 변경 항목"""
    file_path: str
    description: str
    original_code: str
    new_code: str
    line_start: int = 0
    line_end: int = 0
    change_type: str = "modify"  # "modify", "create", "delete"


class CodeApplicator:
    """코드 변경 적용 클래스"""

    def __init__(self):
        self.backup_dir = Path(BACKUP_DIR)
        self.backup_dir.mkdir(exist_ok=True)
        self.applied_changes: List[CodeChange] = []
        self.failed_changes: List[Tuple[CodeChange, str]] = []

    def parse_changes_from_response(self, response: str) -> List[CodeChange]:
        """AI 응답에서 코드 변경사항 파싱"""
        changes = []

        # 패턴 1: ```파일경로 또는 ```diff 형식
        # 예: ```src/main.py 또는 ```python:src/main.py
        code_block_pattern = r'```(?:(\w+):)?([^\n`]+)?\n(.*?)```'
        matches = re.findall(code_block_pattern, response, re.DOTALL)

        for lang, file_hint, code in matches:
            if not file_hint:
                continue

            file_path = file_hint.strip()
            if not file_path or file_path in ['python', 'javascript', 'typescript', 'java', 'diff']:
                continue

            # 파일 경로 정리
            file_path = file_path.lstrip('/')
            if Path(file_path).exists():
                change = CodeChange(
                    file_path=file_path,
                    description=f"코드 변경: {file_path}",
                    original_code="",
                    new_code=code.strip(),
                    change_type="modify"
                )
                changes.append(change)

        # 패턴 2: [파일: path] 형식 파싱
        file_section_pattern = r'\[파일[:\s]*([^\]]+)\][\s\n]*(.*?)(?=\[파일|\Z)'
        matches = re.findall(file_section_pattern, response, re.DOTALL)

        for file_path, content in matches:
            file_path = file_path.strip()
            # 코드 블록 추출
            code_match = re.search(r'```\w*\n?(.*?)```', content, re.DOTALL)
            if code_match and Path(file_path).exists():
                change = CodeChange(
                    file_path=file_path,
                    description=f"코드 변경: {file_path}",
                    original_code="",
                    new_code=code_match.group(1).strip(),
                    change_type="modify"
                )
                if change not in [c for c in changes if c.file_path == change.file_path]:
                    changes.append(change)

        return changes

    def create_backup(self, file_path: str) -> Optional[Path]:
        """파일 백업 생성"""
        source = Path(file_path)
        if not source.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.stem}_{timestamp}{source.suffix}"
        backup_path = self.backup_dir / backup_name

        try:
            shutil.copy2(source, backup_path)
            return backup_path
        except Exception as e:
            print_status(f"백업 실패 ({file_path}): {e}", "warning")
            return None

    def show_change_preview(self, change: CodeChange) -> None:
        """변경 미리보기 표시"""
        print(f"\n{Colors.BOLD}{'─' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}📄 파일: {change.file_path}{Colors.RESET}")
        print(f"{Colors.DIM}{change.description}{Colors.RESET}")
        print(f"{Colors.BOLD}{'─' * 60}{Colors.RESET}")

        # 현재 파일 내용 (일부)
        if Path(change.file_path).exists() and change.change_type == "modify":
            try:
                with open(change.file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
                    lines = current_content.split('\n')
                    preview_lines = lines[:20] if len(lines) > 20 else lines
                    print(f"\n{Colors.RED}현재 코드 (처음 20줄):{Colors.RESET}")
                    for i, line in enumerate(preview_lines, 1):
                        print(f"{Colors.DIM}{i:4d}│{Colors.RESET} {line}")
                    if len(lines) > 20:
                        print(f"{Colors.DIM}     ... ({len(lines) - 20}줄 더 있음){Colors.RESET}")
            except Exception:
                pass

        # 새 코드
        print(f"\n{Colors.GREEN}새 코드:{Colors.RESET}")
        new_lines = change.new_code.split('\n')
        preview_new = new_lines[:30] if len(new_lines) > 30 else new_lines
        for i, line in enumerate(preview_new, 1):
            print(f"{Colors.GREEN}{i:4d}│{Colors.RESET} {line}")
        if len(new_lines) > 30:
            print(f"{Colors.DIM}     ... ({len(new_lines) - 30}줄 더 있음){Colors.RESET}")

    def apply_change(self, change: CodeChange) -> Tuple[bool, str]:
        """단일 변경 적용"""
        file_path = Path(change.file_path)

        try:
            if change.change_type == "delete":
                if file_path.exists():
                    self.create_backup(str(file_path))
                    file_path.unlink()
                    return True, "파일 삭제됨"
                return False, "파일이 존재하지 않음"

            elif change.change_type == "create":
                if file_path.exists():
                    return False, "파일이 이미 존재함"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(change.new_code)
                return True, "파일 생성됨"

            else:  # modify
                if not file_path.exists():
                    return False, "파일이 존재하지 않음"

                # 백업 생성
                backup_path = self.create_backup(str(file_path))
                if backup_path:
                    print_status(f"백업 생성: {backup_path}", "info")

                # 파일 수정
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(change.new_code)

                return True, "수정 완료"

        except Exception as e:
            return False, str(e)

    def apply_with_confirmation(self, changes: List[CodeChange]) -> Tuple[int, int]:
        """확인 후 적용 (각 변경마다 y/n)"""
        applied = 0
        skipped = 0

        print(f"\n{Colors.YELLOW}총 {len(changes)}개의 변경사항이 있습니다.{Colors.RESET}")
        print(f"{Colors.DIM}각 변경사항을 확인 후 적용 여부를 선택하세요.{Colors.RESET}\n")

        for i, change in enumerate(changes, 1):
            print(f"\n{Colors.BOLD}[{i}/{len(changes)}]{Colors.RESET}")
            self.show_change_preview(change)

            while True:
                response = get_user_input(
                    f"\n{Colors.YELLOW}이 변경을 적용하시겠습니까? (y/n/q=중단): {Colors.RESET}",
                    max_length=10,
                    required=False
                )

                if response is None or response.lower() == 'q':
                    print_status("변경 적용 중단됨", "warning")
                    return applied, skipped + (len(changes) - i)

                if response.lower() == 'y':
                    success, msg = self.apply_change(change)
                    if success:
                        print_status(f"✓ {msg}: {change.file_path}", "success")
                        self.applied_changes.append(change)
                        applied += 1
                    else:
                        print_status(f"✗ 실패: {msg}", "error")
                        self.failed_changes.append((change, msg))
                        skipped += 1
                    break

                elif response.lower() == 'n':
                    print_status("건너뜀", "info")
                    skipped += 1
                    break

                else:
                    print_status("y, n, 또는 q를 입력하세요", "warning")

        return applied, skipped

    def apply_all(self, changes: List[CodeChange]) -> Tuple[int, int]:
        """일괄 적용 (모든 변경 한번에)"""
        applied = 0
        failed = 0

        print(f"\n{Colors.YELLOW}총 {len(changes)}개의 변경사항을 일괄 적용합니다.{Colors.RESET}")

        # 최종 확인
        confirm = get_user_input(
            f"{Colors.RED}정말 모든 변경을 적용하시겠습니까? (yes/no): {Colors.RESET}",
            max_length=10
        )

        if confirm != "yes":
            print_status("일괄 적용 취소됨", "info")
            return 0, len(changes)

        for i, change in enumerate(changes, 1):
            print(f"\n{Colors.DIM}[{i}/{len(changes)}] {change.file_path}{Colors.RESET}")
            success, msg = self.apply_change(change)

            if success:
                print_status(f"✓ {msg}", "success")
                self.applied_changes.append(change)
                applied += 1
            else:
                print_status(f"✗ {msg}", "error")
                self.failed_changes.append((change, msg))
                failed += 1

        return applied, failed

    def show_summary(self):
        """적용 결과 요약"""
        print(f"\n{Colors.BOLD}{'═' * 60}{Colors.RESET}")
        print(f"{Colors.CYAN}📋 변경 적용 결과{Colors.RESET}")
        print(f"{Colors.BOLD}{'═' * 60}{Colors.RESET}")

        print(f"\n{Colors.GREEN}✓ 적용됨: {len(self.applied_changes)}개{Colors.RESET}")
        for change in self.applied_changes:
            print(f"  - {change.file_path}")

        if self.failed_changes:
            print(f"\n{Colors.RED}✗ 실패: {len(self.failed_changes)}개{Colors.RESET}")
            for change, reason in self.failed_changes:
                print(f"  - {change.file_path}: {reason}")

        print(f"\n{Colors.DIM}백업 위치: {self.backup_dir}{Colors.RESET}")


# ═══════════════════════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner():
    """VBG 배너 출력"""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██╗   ██╗██████╗  ██████╗    ██╗   ██╗██████╗     ██████╗                   ║
║   ██║   ██║██╔══██╗██╔════╝    ██║   ██║╚════██╗   ██╔═████╗                  ║
║   ██║   ██║██████╔╝██║  ███╗   ██║   ██║ █████╔╝   ██║██╔██║                  ║
║   ╚██╗ ██╔╝██╔══██╗██║   ██║   ╚██╗ ██╔╝██╔═══╝    ████╔╝██║                  ║
║    ╚████╔╝ ██████╔╝╚██████╔╝    ╚████╔╝ ███████╗██╗╚██████╔╝                  ║
║     ╚═══╝  ╚═════╝  ╚═════╝      ╚═══╝  ╚══════╝╚═╝ ╚═════╝                   ║
║                                                                               ║
║   {Colors.YELLOW}Vibe Guardian{Colors.CYAN} - AI Cross-Check Automation System                       ║
║   {Colors.DIM}Claude + Gemini + Antigravity | Parallel Execution{Colors.CYAN}                     ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
{Colors.RESET}"""
    print(banner)

def print_section(title: str, icon: str = "►"):
    """섹션 헤더 출력"""
    width = 60
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'═' * width}{Colors.RESET}")
    print(f"{Colors.CYAN}{icon} {title}{Colors.RESET}")
    print(f"{Colors.BLUE}{'═' * width}{Colors.RESET}\n")

def print_status(message: str, status: str = "info"):
    """상태 메시지 출력"""
    icons = {
        "info": f"{Colors.BLUE}ℹ{Colors.RESET}",
        "success": f"{Colors.GREEN}✓{Colors.RESET}",
        "warning": f"{Colors.YELLOW}⚠{Colors.RESET}",
        "error": f"{Colors.RED}✗{Colors.RESET}",
        "working": f"{Colors.CYAN}⟳{Colors.RESET}",
        "claude": f"{Colors.MAGENTA}🤖{Colors.RESET}",
        "gemini": f"{Colors.BLUE}💎{Colors.RESET}",
        "antigravity": f"{Colors.GREEN}🚀{Colors.RESET}",
    }
    icon = icons.get(status, icons["info"])
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"  {Colors.DIM}[{timestamp}]{Colors.RESET} {icon} {message}")

def print_progress_bar(current: int, total: int, prefix: str = "", width: int = 40):
    """프로그레스 바 출력"""
    percent = current / total if total > 0 else 0
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r  {prefix} {Colors.CYAN}[{bar}]{Colors.RESET} {percent*100:.1f}%", end="", flush=True)
    if current >= total:
        print()

def print_dashboard(stats: SessionStats, project_type: ProjectType):
    """대시보드 출력"""
    elapsed = time.time() - stats.start_time
    elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    dashboard = f"""
{Colors.BOLD}┌─────────────────────────────────────────────────────────────┐
│                    {Colors.CYAN}VBG SESSION DASHBOARD{Colors.RESET}{Colors.BOLD}                     │
├─────────────────────────────────────────────────────────────┤
│  {Colors.YELLOW}Project Type:{Colors.RESET}  {project_type.value:<20}                    {Colors.BOLD}│
│  {Colors.YELLOW}Elapsed Time:{Colors.RESET}  {elapsed_str:<20}                    {Colors.BOLD}│
├─────────────────────────────────────────────────────────────┤
│  {Colors.MAGENTA}Claude Calls:{Colors.RESET}      {stats.claude_calls:<8}                          {Colors.BOLD}│
│  {Colors.BLUE}Gemini Calls:{Colors.RESET}      {stats.gemini_calls:<8}                          {Colors.BOLD}│
│  {Colors.GREEN}Antigravity:{Colors.RESET}       {stats.antigravity_calls:<8}                          {Colors.BOLD}│
├─────────────────────────────────────────────────────────────┤
│  {Colors.CYAN}Est. Tokens Used:{Colors.RESET}  {stats.total_tokens_used:<8}                          {Colors.BOLD}│
└─────────────────────────────────────────────────────────────┘{Colors.RESET}
"""
    print(dashboard)

def get_user_input(prompt: str, max_length: int = MAX_USER_INPUT_LENGTH, required: bool = True) -> Optional[str]:
    """사용자 입력 받기 (길이 제한 포함)"""
    try:
        user_input = input(prompt).strip()

        if required and not user_input:
            print_status("입력이 필요합니다", "warning")
            return None

        if len(user_input) > max_length:
            print_status(f"입력이 너무 깁니다 (최대 {max_length}자)", "warning")
            return None

        return user_input
    except EOFError:
        return None
    except KeyboardInterrupt:
        print()
        return None


def print_benchmark_comparison(before: BenchmarkResult, after: BenchmarkResult):
    """벤치마크 비교 결과 출력"""
    time_diff = ((before.execution_time - after.execution_time) / before.execution_time * 100) if before.execution_time > 0 else 0
    mem_diff = ((before.memory_usage - after.memory_usage) / before.memory_usage * 100) if before.memory_usage > 0 else 0

    time_color = Colors.GREEN if time_diff > 0 else Colors.RED
    mem_color = Colors.GREEN if mem_diff > 0 else Colors.RED

    report = f"""
{Colors.BOLD}╔═══════════════════════════════════════════════════════════════════════════════╗
║                        {Colors.CYAN}PERFORMANCE IMPROVEMENT REPORT{Colors.RESET}{Colors.BOLD}                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   {Colors.YELLOW}METRIC{Colors.RESET}{Colors.BOLD}              {Colors.YELLOW}BEFORE{Colors.RESET}{Colors.BOLD}          {Colors.YELLOW}AFTER{Colors.RESET}{Colors.BOLD}          {Colors.YELLOW}CHANGE{Colors.RESET}{Colors.BOLD}         ║
║   ─────────────────────────────────────────────────────────────────────────   ║
║   Execution Time     {before.execution_time:>8.2f}ms      {after.execution_time:>8.2f}ms      {time_color}{time_diff:>+7.1f}%{Colors.RESET}{Colors.BOLD}        ║
║   Memory Usage       {before.memory_usage:>8.2f}MB      {after.memory_usage:>8.2f}MB      {mem_color}{mem_diff:>+7.1f}%{Colors.RESET}{Colors.BOLD}        ║
║                                                                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║   {Colors.GREEN}Overall Performance Score:{Colors.RESET} {Colors.BOLD}{Colors.GREEN}{'★' * min(5, int((time_diff + mem_diff) / 20) + 3)}{'☆' * (5 - min(5, int((time_diff + mem_diff) / 20) + 3))}{Colors.RESET}{Colors.BOLD}                                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(report)

# ═══════════════════════════════════════════════════════════════════════════════
# 설정 관리
# ═══════════════════════════════════════════════════════════════════════════════

def get_default_config() -> Dict[str, Any]:
    """기본 설정 반환"""
    return {
        "version": VERSION,
        "ai_models": {
            "claude": {
                "enabled": True,
                "command": "claude",
                "role": "builder",
                "max_retries": 3
            },
            "gemini": {
                "enabled": True,
                "command": "gemini",
                "role": "auditor",
                "max_retries": 3
            }
        },
        "antigravity": {
            "enabled": True,
            "command": "antigravity",
            "auto_setup": True
        },
        "benchmarking": {
            "enabled": True,
            "iterations": 3,
            "warmup_iterations": 1
        },
        "fallback": {
            "enabled": True,
            "max_self_heal_attempts": 3
        },
        "output": {
            "verbose": True,
            "save_reports": True,
            "report_dir": ".vbg_reports"
        },
        "execution": {
            "parallel": True,  # Claude, Gemini 병렬 실행
            "include_antigravity_in_parallel": False  # Antigravity도 병렬에 포함
        }
    }

def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """설정 유효성 검증"""
    errors = []

    # AI 모델 설정 검증
    ai_models = config.get("ai_models", {})
    for model_name in ["claude", "gemini"]:
        model_config = ai_models.get(model_name, {})
        if model_config.get("enabled", False):
            if not model_config.get("command"):
                errors.append(f"{model_name}: command가 설정되지 않음")
            max_retries = model_config.get("max_retries", 3)
            if not isinstance(max_retries, int) or max_retries < 1 or max_retries > 10:
                errors.append(f"{model_name}: max_retries는 1-10 사이여야 함 (현재: {max_retries})")

    # 벤치마킹 설정 검증
    benchmarking = config.get("benchmarking", {})
    iterations = benchmarking.get("iterations", 3)
    if not isinstance(iterations, int) or iterations < 1 or iterations > 10:
        errors.append(f"benchmarking.iterations는 1-10 사이여야 함 (현재: {iterations})")

    warmup = benchmarking.get("warmup_iterations", 1)
    if not isinstance(warmup, int) or warmup < 0 or warmup > 5:
        errors.append(f"benchmarking.warmup_iterations는 0-5 사이여야 함 (현재: {warmup})")

    # fallback 설정 검증
    fallback = config.get("fallback", {})
    max_attempts = fallback.get("max_self_heal_attempts", 3)
    if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 5:
        errors.append(f"fallback.max_self_heal_attempts는 1-5 사이여야 함 (현재: {max_attempts})")

    # output 설정 검증
    output = config.get("output", {})
    report_dir = output.get("report_dir", REPORT_DIR)
    if not report_dir or not isinstance(report_dir, str):
        errors.append("output.report_dir가 올바르지 않음")

    return len(errors) == 0, errors


def load_config() -> Dict[str, Any]:
    """설정 로드"""
    config_path = Path(CONFIG_FILE)
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config = get_default_config()
                # 기본 설정과 병합
                def merge_dict(base, override):
                    for key, value in override.items():
                        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                            merge_dict(base[key], value)
                        else:
                            base[key] = value
                    return base
                merged_config = merge_dict(default_config, user_config)

                # 설정 검증
                is_valid, errors = validate_config(merged_config)
                if not is_valid:
                    for error in errors:
                        print_status(f"설정 오류: {error}", "warning")
                    print_status("일부 설정이 기본값으로 대체됩니다", "info")

                return merged_config
        except json.JSONDecodeError:
            print_status("설정 파일 파싱 오류, 기본 설정 사용", "warning")
    return get_default_config()

def save_config(config: Dict[str, Any]):
    """설정 저장"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print_status(f"설정 저장됨: {CONFIG_FILE}", "success")

# ═══════════════════════════════════════════════════════════════════════════════
# 프로젝트 감지
# ═══════════════════════════════════════════════════════════════════════════════

def detect_project_type() -> ProjectType:
    """프로젝트 타입 자동 감지"""
    cwd = Path.cwd()

    # Next.js / React 감지
    package_json = cwd / "package.json"
    if package_json.exists():
        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    return ProjectType.NEXTJS
                if "react" in deps:
                    return ProjectType.REACT
        except json.JSONDecodeError as e:
            print_status(f"package.json 파싱 오류: {e}", "warning")
        except PermissionError:
            print_status("package.json 읽기 권한 없음", "warning")
        except Exception as e:
            print_status(f"package.json 읽기 실패: {e}", "warning")

    # Spring Boot Maven 감지
    if (cwd / "pom.xml").exists():
        return ProjectType.SPRING_BOOT_MAVEN

    # Spring Boot Gradle 감지
    if (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
        return ProjectType.SPRING_BOOT_GRADLE

    # Python 감지
    if (cwd / "requirements.txt").exists() or (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists():
        return ProjectType.PYTHON

    return ProjectType.UNKNOWN

def get_project_files(project_type: ProjectType, extensions: List[str] = None) -> List[Path]:
    """프로젝트 파일 목록 가져오기"""
    cwd = Path.cwd()

    if extensions is None:
        ext_map = {
            ProjectType.NEXTJS: [".ts", ".tsx", ".js", ".jsx", ".css"],
            ProjectType.REACT: [".ts", ".tsx", ".js", ".jsx", ".css"],
            ProjectType.SPRING_BOOT_MAVEN: [".java", ".xml", ".properties", ".yml"],
            ProjectType.SPRING_BOOT_GRADLE: [".java", ".kt", ".gradle", ".kts", ".properties", ".yml"],
            ProjectType.PYTHON: [".py"],
            ProjectType.UNKNOWN: [".py", ".js", ".ts", ".java"],
        }
        extensions = ext_map.get(project_type, [])

    files = []
    exclude_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "target", "build", ".next", "dist"}

    for ext in extensions:
        for file in cwd.rglob(f"*{ext}"):
            if not any(excluded in file.parts for excluded in exclude_dirs):
                files.append(file)

    return files


def select_important_files(files: List[Path], max_count: int = 30, project_type: ProjectType = None) -> List[Path]:
    """중요도 기반 파일 선택 (단순 자르기 대신 스마트 선택)"""
    if len(files) <= max_count:
        return files

    # 중요도 점수 계산
    def importance_score(file_path: Path) -> int:
        score = 0
        name = file_path.name.lower()
        parts = [p.lower() for p in file_path.parts]

        # 엔트리 포인트/설정 파일 (최고 우선순위)
        high_priority = ['main', 'index', 'app', 'config', 'settings', 'routes', 'api']
        if any(hp in name for hp in high_priority):
            score += 100

        # 설정/스키마 파일
        config_files = ['package.json', 'tsconfig', 'pom.xml', 'build.gradle', 'requirements.txt', 'pyproject.toml']
        if any(cf in name for cf in config_files):
            score += 90

        # src 폴더 내 파일 우선
        if 'src' in parts:
            score += 50

        # 테스트 파일은 낮은 우선순위
        if 'test' in name or '__test__' in name or 'spec' in name:
            score -= 30

        # 최근 수정된 파일 우선 (존재 시)
        try:
            mtime = file_path.stat().st_mtime
            # 최근 7일 내 수정된 파일 보너스
            if time.time() - mtime < 7 * 24 * 3600:
                score += 20
        except (OSError, PermissionError):
            pass

        # 파일 크기 기반 (너무 큰 파일은 제외 가능성)
        try:
            size = file_path.stat().st_size
            if size < 100:  # 거의 빈 파일
                score -= 20
            elif size > 100000:  # 100KB 이상
                score -= 10
        except (OSError, PermissionError):
            pass

        return score

    # 점수로 정렬 후 상위 N개 선택
    scored_files = [(f, importance_score(f)) for f in files]
    scored_files.sort(key=lambda x: x[1], reverse=True)

    return [f for f, _ in scored_files[:max_count]]


# ═══════════════════════════════════════════════════════════════════════════════
# 토큰 추정
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_tokens(text: str) -> int:
    """텍스트의 토큰 수 추정

    Claude/GPT 모델의 토큰화 방식을 근사하여 추정:
    - 영어: 평균 1단어 ≈ 1.3 토큰
    - 한국어/중국어/일본어: 평균 1문자 ≈ 0.5-1 토큰
    - 코드: 특수문자와 들여쓰기 고려
    """
    if not text:
        return 0

    # 영어 단어 수
    words = re.findall(r'[a-zA-Z]+', text)
    english_tokens = len(words) * TOKENS_PER_WORD

    # 비영어 문자 (한글, 한자, 일본어 등)
    non_english = re.findall(r'[\u3000-\u9fff\uac00-\ud7af]+', text)
    non_english_chars = sum(len(s) for s in non_english)
    non_english_tokens = non_english_chars * 0.5  # 대략 2자당 1토큰

    # 숫자와 특수문자
    special_chars = len(re.findall(r'[0-9\.\,\!\?\:\;\'\"\(\)\[\]\{\}\+\-\*\/\=\<\>\@\#\$\%\^\&\_\|\\]', text))
    special_tokens = special_chars * 0.5

    # 공백/줄바꿈
    whitespace = len(re.findall(r'\s+', text))
    whitespace_tokens = whitespace * 0.1

    total = int(english_tokens + non_english_tokens + special_tokens + whitespace_tokens)
    return max(1, total)  # 최소 1 토큰


# ═══════════════════════════════════════════════════════════════════════════════
# AI 실행 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class AIEngine:
    """AI 엔진 관리 클래스"""

    def __init__(self, config: Dict[str, Any], stats: SessionStats):
        self.config = config
        self.stats = stats
        self.claude_available = self._check_command("claude")
        self.gemini_available = self._check_command("gemini")
        self.antigravity_available = self._check_command("antigravity")

    def _check_command(self, command: str) -> bool:
        """명령어 사용 가능 여부 확인"""
        return shutil.which(command) is not None

    def _run_command(self, command: List[str], timeout: int = DEFAULT_COMMAND_TIMEOUT) -> Tuple[bool, str]:
        """명령어 실행"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd()
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def call_claude(self, prompt: str, context: str = "") -> Tuple[bool, str]:
        """Claude 호출"""
        if not self.claude_available:
            print_status("Claude CLI를 찾을 수 없습니다", "warning")
            return False, "Claude CLI not available"

        print_status("Claude에게 요청 중...", "claude")

        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        # Claude CLI 호출 (--print 옵션으로 비대화형 모드)
        success, output = self._run_command(["claude", "--print", full_prompt])

        if success:
            self.stats.claude_calls += 1
            # 입력 + 출력 토큰 추정
            input_tokens = estimate_tokens(full_prompt)
            output_tokens = estimate_tokens(output)
            self.stats.total_tokens_used += input_tokens + output_tokens
            print_status(f"Claude 응답 완료 (≈{input_tokens + output_tokens} 토큰)", "success")
        else:
            print_status("Claude 호출 실패", "error")

        return success, output

    def call_gemini(self, prompt: str, context: str = "") -> Tuple[bool, str]:
        """Gemini 호출"""
        if not self.gemini_available:
            print_status("Gemini CLI를 찾을 수 없습니다", "warning")
            return False, "Gemini CLI not available"

        print_status("Gemini에게 요청 중...", "gemini")

        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        # Gemini CLI 호출
        success, output = self._run_command(["gemini", "-p", full_prompt])

        if success:
            self.stats.gemini_calls += 1
            # 입력 + 출력 토큰 추정
            input_tokens = estimate_tokens(full_prompt)
            output_tokens = estimate_tokens(output)
            self.stats.total_tokens_used += input_tokens + output_tokens
            print_status(f"Gemini 응답 완료 (≈{input_tokens + output_tokens} 토큰)", "success")
        else:
            print_status("Gemini 호출 실패", "error")

        return success, output

    def call_antigravity(self, command: str = "run") -> Tuple[bool, str]:
        """Antigravity 호출"""
        if not self.antigravity_available:
            print_status("Antigravity를 찾을 수 없습니다", "warning")
            return False, "Antigravity not available"

        print_status(f"Antigravity {command} 실행 중...", "antigravity")

        success, output = self._run_command(["antigravity", command])

        if success:
            self.stats.antigravity_calls += 1
            print_status("Antigravity 실행 완료", "success")
        else:
            print_status("Antigravity 실행 실패", "error")

        return success, output

    def cross_check(self, task: str, claude_result: str) -> Tuple[bool, str]:
        """Claude 결과를 Gemini로 검증"""
        audit_prompt = f"""다음은 Claude가 제안한 코드/솔루션입니다. 코드 리뷰어로서 검토해주세요:

[작업 요청]
{task}

[Claude의 제안]
{claude_result}

다음 관점에서 검토해주세요:
1. 코드 품질 및 가독성
2. 잠재적 버그나 보안 취약점
3. 성능 개선 가능성
4. 베스트 프랙티스 준수 여부

문제가 있다면 구체적인 수정 제안을 해주세요."""

        return self.call_gemini(audit_prompt)

    def run_antigravity_setup(self) -> Tuple[bool, str]:
        """Antigravity 자동 설정 실행"""
        if not self.antigravity_available:
            return False, "Antigravity not available"

        if not self.config.get("antigravity", {}).get("enabled", False):
            return False, "Antigravity disabled in config"

        auto_setup = self.config.get("antigravity", {}).get("auto_setup", False)
        if auto_setup:
            return self.call_antigravity("setup")
        return self.call_antigravity("run")

    def fallback_mode(self, prompt: str, attempt: int = 1) -> Tuple[bool, str]:
        """Fallback 모드: Gemini + 자가 치유"""
        max_attempts = self.config.get("fallback", {}).get("max_self_heal_attempts", 3)

        if attempt > max_attempts:
            return False, "Maximum self-heal attempts exceeded"

        print_status(f"Fallback 모드 활성화 (시도 {attempt}/{max_attempts})", "warning")

        success, result = self.call_gemini(prompt)

        if not success and attempt < max_attempts:
            print_status("자가 치유 시도 중...", "working")
            return self.fallback_mode(prompt, attempt + 1)

        return success, result

    def call_parallel(self, prompt: str, context: str = "", include_antigravity: bool = False) -> Dict[str, Tuple[bool, str]]:
        """Claude, Gemini (선택적으로 Antigravity)를 병렬 실행

        Returns:
            Dict[str, Tuple[bool, str]]: {"claude": (success, output), "gemini": (success, output), ...}
        """
        results = {}
        tasks = {}

        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        with ThreadPoolExecutor(max_workers=3) as executor:
            # Claude 태스크
            if self.claude_available and self.config.get("ai_models", {}).get("claude", {}).get("enabled", True):
                tasks["claude"] = executor.submit(self._call_claude_internal, full_prompt)

            # Gemini 태스크
            if self.gemini_available and self.config.get("ai_models", {}).get("gemini", {}).get("enabled", True):
                tasks["gemini"] = executor.submit(self._call_gemini_internal, full_prompt)

            # Antigravity 태스크 (선택적)
            if include_antigravity and self.antigravity_available and self.config.get("antigravity", {}).get("enabled", False):
                tasks["antigravity"] = executor.submit(self._call_antigravity_internal, "analyze")

            # 결과 수집
            for name, future in tasks.items():
                try:
                    success, output = future.result(timeout=DEFAULT_COMMAND_TIMEOUT)
                    results[name] = (success, output)

                    # 통계 업데이트
                    if success:
                        if name == "claude":
                            self.stats.claude_calls += 1
                            tokens = estimate_tokens(full_prompt) + estimate_tokens(output)
                            self.stats.total_tokens_used += tokens
                            print_status(f"Claude 응답 완료 (≈{tokens} 토큰)", "success")
                        elif name == "gemini":
                            self.stats.gemini_calls += 1
                            tokens = estimate_tokens(full_prompt) + estimate_tokens(output)
                            self.stats.total_tokens_used += tokens
                            print_status(f"Gemini 응답 완료 (≈{tokens} 토큰)", "success")
                        elif name == "antigravity":
                            self.stats.antigravity_calls += 1
                            print_status("Antigravity 응답 완료", "success")
                    else:
                        print_status(f"{name} 호출 실패", "warning")

                except FuturesTimeoutError:
                    results[name] = (False, f"{name} timed out")
                    print_status(f"{name} 타임아웃", "error")
                except Exception as e:
                    results[name] = (False, str(e))
                    print_status(f"{name} 오류: {e}", "error")

        return results

    def _call_claude_internal(self, prompt: str) -> Tuple[bool, str]:
        """내부용 Claude 호출 (통계 업데이트 없음)"""
        return self._run_command(["claude", "--print", prompt])

    def _call_gemini_internal(self, prompt: str) -> Tuple[bool, str]:
        """내부용 Gemini 호출 (통계 업데이트 없음)"""
        return self._run_command(["gemini", "-p", prompt])

    def _call_antigravity_internal(self, command: str) -> Tuple[bool, str]:
        """내부용 Antigravity 호출 (통계 업데이트 없음)"""
        return self._run_command(["antigravity", command])

    def synthesize_results(self, results: Dict[str, Tuple[bool, str]], task_description: str) -> str:
        """여러 AI 결과를 종합하여 최종 결과 생성"""
        successful_results = {k: v[1] for k, v in results.items() if v[0]}

        if not successful_results:
            return "모든 AI 호출이 실패했습니다."

        if len(successful_results) == 1:
            return list(successful_results.values())[0]

        # 여러 결과가 있으면 종합
        synthesis = f"""
{Colors.BOLD}{'═' * 70}
                    종합 분석 결과 (Synthesized Results)
{'═' * 70}{Colors.RESET}
"""
        for ai_name, output in successful_results.items():
            icon = {"claude": "🤖", "gemini": "💎", "antigravity": "🚀"}.get(ai_name, "🔹")
            synthesis += f"""
{Colors.CYAN}{icon} {ai_name.upper()} 의견:{Colors.RESET}
{'─' * 50}
{output}
"""

        # 공통점/차이점 분석 요청 (가장 빠른 AI 사용)
        if len(successful_results) >= 2:
            synthesis += f"""
{Colors.YELLOW}{'─' * 70}
💡 TIP: 위 결과들의 공통 제안사항을 우선 적용하고,
       상충되는 부분은 프로젝트 상황에 맞게 선택하세요.
{'─' * 70}{Colors.RESET}
"""

        return synthesis


# ═══════════════════════════════════════════════════════════════════════════════
# 벤치마킹
# ═══════════════════════════════════════════════════════════════════════════════

class Benchmarker:
    """성능 벤치마킹 클래스"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.iterations = min(10, max(1, config.get("benchmarking", {}).get("iterations", 3)))
        self.warmup = min(5, max(0, config.get("benchmarking", {}).get("warmup_iterations", 1)))

    def _measure_command_with_memory(self, command: List[str], timeout: int = BENCHMARK_TIMEOUT) -> Tuple[float, float, float]:
        """명령 실행 시간과 메모리 피크 측정"""
        import threading

        peak_memory = 0
        cpu_samples = []
        stop_monitoring = threading.Event()

        def monitor_resources():
            """백그라운드에서 리소스 모니터링"""
            nonlocal peak_memory
            process = psutil.Process()
            while not stop_monitoring.is_set():
                try:
                    mem = process.memory_info().rss / (1024 * 1024)
                    cpu = process.cpu_percent(interval=0.05)
                    peak_memory = max(peak_memory, mem)
                    cpu_samples.append(cpu)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
                time.sleep(0.1)

        # 모니터링 스레드 시작
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()

        try:
            start = time.perf_counter()
            subprocess.run(command, capture_output=True, timeout=timeout)
            execution_time = (time.perf_counter() - start) * 1000  # ms
        except subprocess.TimeoutExpired:
            execution_time = timeout * 1000
        except Exception:
            execution_time = 0
        finally:
            stop_monitoring.set()
            monitor_thread.join(timeout=1)

        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
        return execution_time, peak_memory, avg_cpu

    def measure_performance(self, command: List[str] = None) -> BenchmarkResult:
        """성능 측정 (개선된 메모리/CPU 측정)"""
        result = BenchmarkResult(timestamp=datetime.now().isoformat())

        # 기본 메모리/CPU 측정 (명령이 없을 때)
        process = psutil.Process()
        result.memory_usage = process.memory_info().rss / (1024 * 1024)  # MB
        result.cpu_usage = process.cpu_percent(interval=0.1)

        if command:
            # 워밍업 (측정하지 않음)
            for i in range(self.warmup):
                try:
                    subprocess.run(command, capture_output=True, timeout=BENCHMARK_TIMEOUT)
                except (subprocess.TimeoutExpired, Exception):
                    pass

            # 실제 측정
            times = []
            peak_memories = []
            cpu_usages = []

            for i in range(self.iterations):
                exec_time, peak_mem, avg_cpu = self._measure_command_with_memory(command)
                times.append(exec_time)
                peak_memories.append(peak_mem)
                cpu_usages.append(avg_cpu)

            # 평균값 계산
            result.execution_time = sum(times) / len(times) if times else 0
            result.memory_usage = max(peak_memories) if peak_memories else result.memory_usage  # 피크 메모리
            result.cpu_usage = sum(cpu_usages) / len(cpu_usages) if cpu_usages else 0

        return result

    def measure_build_performance(self, project_type: ProjectType) -> BenchmarkResult:
        """프로젝트 빌드 성능 측정"""
        commands = {
            ProjectType.NEXTJS: ["npm", "run", "build"],
            ProjectType.REACT: ["npm", "run", "build"],
            ProjectType.SPRING_BOOT_MAVEN: ["mvn", "compile", "-q"],
            ProjectType.SPRING_BOOT_GRADLE: ["gradle", "compileJava", "-q"],
            ProjectType.PYTHON: ["python", "-m", "py_compile"],
        }

        command = commands.get(project_type)
        if command:
            return self.measure_performance(command)
        return self.measure_performance()

# ═══════════════════════════════════════════════════════════════════════════════
# 핵심 기능 구현
# ═══════════════════════════════════════════════════════════════════════════════

class VBGCore:
    """VBG 핵심 기능 클래스"""

    def __init__(self, continue_session: bool = False, session_id: str = None):
        self.config = load_config()
        self.stats = SessionStats()
        self.project_type = detect_project_type()
        self.ai_engine = AIEngine(self.config, self.stats)
        self.benchmarker = Benchmarker(self.config)
        self.code_applicator = CodeApplicator()

        # 세션 관리자 초기화
        self.session_manager = SessionManager()
        self._init_session(continue_session, session_id)

        # 리포트 디렉토리 생성
        if self.config.get("output", {}).get("save_reports", True):
            report_dir = Path(self.config.get("output", {}).get("report_dir", REPORT_DIR))
            report_dir.mkdir(exist_ok=True)
            self.report_dir = report_dir
        else:
            self.report_dir = None

    def _init_session(self, continue_session: bool, session_id: str):
        """세션 초기화"""
        if session_id:
            # 특정 세션 로드
            if self.session_manager.load_session(session_id):
                print_status(f"세션 '{session_id}' 로드됨", "success")
                self._show_context_summary()
            else:
                print_status(f"세션 '{session_id}'을 찾을 수 없어 새 세션 생성", "warning")
                self.session_manager.create_session(self.project_type.value)
        elif continue_session:
            # 최근 세션 이어서
            if self.session_manager.load_latest_session():
                print_status(f"이전 세션 '{self.session_manager.current_session_id}' 이어서 진행", "success")
                self._show_context_summary()
            else:
                print_status("이전 세션이 없어 새 세션 생성", "info")
                self.session_manager.create_session(self.project_type.value)
        else:
            # 새 세션 생성
            self.session_manager.create_session(self.project_type.value)

    def _show_context_summary(self):
        """컨텍스트 요약 표시"""
        if self.session_manager.context_history:
            history_count = len(self.session_manager.context_history)
            total_tokens = sum(e.tokens for e in self.session_manager.context_history)
            commands = [e.command for e in self.session_manager.context_history if e.command]
            recent_commands = list(dict.fromkeys(commands[-5:]))  # 최근 5개 중복 제거

            print(f"\n{Colors.DIM}📚 컨텍스트: {history_count}개 기록, ≈{total_tokens} 토큰{Colors.RESET}")
            if recent_commands:
                print(f"{Colors.DIM}   최근 명령: {', '.join(recent_commands)}{Colors.RESET}\n")

    def _get_context_enhanced_prompt(self, prompt: str, command: str) -> str:
        """컨텍스트가 포함된 프롬프트 생성"""
        context = self.session_manager.get_context_prompt()
        if context:
            return f"{context}\n\n{prompt}"
        return prompt

    def _save_interaction(self, command: str, user_input: str, ai_response: str):
        """상호작용 저장"""
        # 사용자 입력 저장
        self.session_manager.add_context("user", user_input, command)
        # AI 응답 저장 (요약)
        response_summary = ai_response[:1000] if len(ai_response) > 1000 else ai_response
        self.session_manager.add_context("assistant", response_summary, command)

    def save_report(self, report_type: str, content: str) -> Optional[Path]:
        """리포트 파일 저장"""
        if not self.report_dir:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_{timestamp}.md"
        filepath = self.report_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# VBG {report_type.upper()} Report\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write(f"Project Type: {self.project_type.value}\n\n")
                f.write("---\n\n")
                f.write(content)
            print_status(f"리포트 저장됨: {filepath}", "success")
            return filepath
        except Exception as e:
            print_status(f"리포트 저장 실패: {e}", "warning")
            return None

    def _is_parallel_enabled(self) -> bool:
        """병렬 실행 활성화 여부 확인"""
        return self.config.get("execution", {}).get("parallel", True)

    def _include_antigravity_in_parallel(self) -> bool:
        """Antigravity 병렬 포함 여부 확인"""
        return self.config.get("execution", {}).get("include_antigravity_in_parallel", False)

    def refactor(self, target: str = None, apply_mode: str = None):
        """리팩토링 및 성능 벤치마크 모드

        Args:
            target: 리팩토링 대상 (미구현)
            apply_mode: "confirm" (확인 후 적용), "all" (일괄 적용), None (제안만)
        """
        print_section("REFACTOR MODE", "🔧")

        # 실행 모드 표시
        parallel_mode = self._is_parallel_enabled()
        if parallel_mode:
            print_status("⚡ 병렬 실행 모드 활성화", "info")

        if apply_mode:
            mode_text = "확인 후 적용" if apply_mode == "confirm" else "일괄 적용"
            print_status(f"🔨 적용 모드: {mode_text}", "info")

        # 1. 수정 전 성능 측정
        print_status("수정 전 성능 측정 중...", "working")
        before_benchmark = self.benchmarker.measure_build_performance(self.project_type)
        print_status(f"기준 성능: {before_benchmark.execution_time:.2f}ms, {before_benchmark.memory_usage:.2f}MB", "info")

        # 2. 대상 파일 분석
        files = get_project_files(self.project_type)
        print_status(f"분석 대상: {len(files)}개 파일", "info")

        if not files:
            print_status("리팩토링 대상 파일을 찾을 수 없습니다", "warning")
            return

        # 3. 프롬프트 생성 (적용 모드일 때는 구조화된 형식 요청)
        selected_files = select_important_files(files, MAX_FILES_FOR_REFACTOR, self.project_type)

        if apply_mode:
            # 적용 모드: 구조화된 응답 요청
            base_prompt = f"""현재 {self.project_type.value} 프로젝트를 분석하고 성능 최적화를 위한 리팩토링을 수행해주세요.

주요 파일들 ({len(files)}개 중 {len(selected_files)}개 선택):
{"\n".join([str(f) for f in selected_files])}

다음 관점에서 리팩토링을 제안해주세요:
1. 성능 최적화 (실행 시간, 메모리 사용량)
2. 코드 중복 제거
3. 불필요한 의존성 제거
4. 최신 문법/패턴 적용

중요: 각 파일 변경사항을 다음 형식으로 제공해주세요:

[파일: 경로/파일명.확장자]
설명: 변경 내용 설명

```언어
전체 수정된 코드 내용
```

반드시 파일 전체 내용을 제공해주세요. 부분 코드가 아닌 전체 파일을 출력해주세요."""
        else:
            # 일반 모드: 제안만
            base_prompt = f"""현재 {self.project_type.value} 프로젝트를 분석하고 성능 최적화를 위한 리팩토링을 제안해주세요.

주요 파일들 ({len(files)}개 중 {len(selected_files)}개 선택):
{"\n".join([str(f) for f in selected_files])}

다음 관점에서 리팩토링을 제안해주세요:
1. 성능 최적화 (실행 시간, 메모리 사용량)
2. 코드 중복 제거
3. 불필요한 의존성 제거
4. 최신 문법/패턴 적용

각 제안에 대해 구체적인 코드 변경 사항을 보여주세요."""

        # 컨텍스트 포함 프롬프트
        refactor_prompt = self._get_context_enhanced_prompt(base_prompt, "refactor")

        # 4. AI 호출 (병렬 또는 순차)
        start_time = time.time()

        if parallel_mode:
            # 병렬 실행
            print_status("Claude + Gemini 병렬 분석 중...", "working")
            results = self.ai_engine.call_parallel(
                refactor_prompt,
                include_antigravity=self._include_antigravity_in_parallel()
            )
            elapsed = time.time() - start_time
            print_status(f"병렬 분석 완료 ({elapsed:.1f}초)", "success")

            # 결과 종합
            final_result = self.ai_engine.synthesize_results(results, "리팩토링 제안")
            success = any(r[0] for r in results.values())
        else:
            # 순차 실행 (기존 방식)
            success, claude_result = self.ai_engine.call_claude(refactor_prompt)

            if not success:
                success, claude_result = self.ai_engine.fallback_mode(refactor_prompt)

            if success:
                print_status("Gemini 크로스 체크 진행 중...", "working")
                audit_success, audit_result = self.ai_engine.cross_check(refactor_prompt, claude_result)
                elapsed = time.time() - start_time

                final_result = claude_result
                if audit_success:
                    final_result += f"\n\n{Colors.CYAN}{'═' * 50}\n🔍 GEMINI AUDIT\n{'═' * 50}{Colors.RESET}\n\n{audit_result}"

        if success:
            # 5. 결과 출력
            print_section("REFACTORING SUGGESTIONS", "💡")
            print(final_result)

            # 6. 리포트 저장
            report_content = f"## 리팩토링 제안\n\n{final_result}"
            report_content += f"\n\n## 기준 벤치마크\n- 실행 시간: {before_benchmark.execution_time:.2f}ms\n- 메모리: {before_benchmark.memory_usage:.2f}MB"
            report_content += f"\n\n## 실행 정보\n- 모드: {'병렬' if parallel_mode else '순차'}\n- 소요 시간: {elapsed:.1f}초"
            self.save_report("refactor", report_content)

            # 7. 코드 적용 (apply_mode가 설정된 경우)
            if apply_mode:
                print_section("CODE APPLICATION", "🔨")
                changes = self.code_applicator.parse_changes_from_response(final_result)

                if not changes:
                    print_status("적용 가능한 코드 변경사항을 찾을 수 없습니다", "warning")
                    print_status("AI 응답에서 [파일: 경로] 형식의 코드 블록을 찾지 못했습니다", "info")
                else:
                    print_status(f"{len(changes)}개의 변경사항 감지됨", "info")

                    if apply_mode == "confirm":
                        applied, skipped = self.code_applicator.apply_with_confirmation(changes)
                    else:  # "all"
                        applied, skipped = self.code_applicator.apply_all(changes)

                    self.code_applicator.show_summary()

                    # 적용 후 재측정 안내
                    if applied > 0:
                        print_section("POST-APPLICATION", "📊")
                        print_status("변경사항이 적용되었습니다. 성능을 다시 측정합니다...", "working")
                        after_benchmark = self.benchmarker.measure_build_performance(self.project_type)
                        print_benchmark_comparison(before_benchmark, after_benchmark)
            else:
                # 적용 모드가 아닌 경우 안내
                print_section("NEXT STEPS", "📌")
                print(f"""
{Colors.YELLOW}제안된 변경사항을 적용하려면:{Colors.RESET}

  {Colors.CYAN}vbg --refactor --apply{Colors.RESET}      확인 후 적용 (각 변경마다 y/n)
  {Colors.CYAN}vbg --refactor --apply-all{Colors.RESET}  일괄 적용 (모든 변경 한번에)

{Colors.DIM}기준 벤치마크 (Before):{Colors.RESET}
  - 실행 시간: {before_benchmark.execution_time:.2f}ms
  - 메모리: {before_benchmark.memory_usage:.2f}MB
""")

            # 8. 컨텍스트 저장
            self._save_interaction("refactor", base_prompt, final_result)

        print_dashboard(self.stats, self.project_type)

    def recommend(self):
        """고도화 추천 모드"""
        print_section("RECOMMEND MODE", "💡")

        parallel_mode = self._is_parallel_enabled()
        if parallel_mode:
            print_status("⚡ 병렬 실행 모드 활성화", "info")

        files = get_project_files(self.project_type)
        print_status(f"스캔 대상: {len(files)}개 파일", "info")

        selected_files = select_important_files(files, MAX_FILES_FOR_PROMPT, self.project_type)
        base_prompt = f"""현재 {self.project_type.value} 프로젝트를 분석하고 다음을 제안해주세요:

프로젝트 파일 ({len(files)}개 중 {len(selected_files)}개 선택):
{"\n".join([str(f) for f in selected_files])}

1. 아키텍처 개선점
   - 현재 구조의 문제점
   - 권장 아키텍처 패턴

2. 신규 기능 제안
   - 사용자 경험 향상을 위한 기능
   - 개발자 경험 향상을 위한 기능

3. 기술 스택 업그레이드
   - 업데이트가 필요한 의존성
   - 새로 도입하면 좋을 라이브러리

4. 테스트/품질 개선
   - 테스트 커버리지 향상 방안
   - CI/CD 파이프라인 개선

각 제안에 우선순위(높음/중간/낮음)를 표시하고 구현 복잡도를 알려주세요."""

        recommend_prompt = self._get_context_enhanced_prompt(base_prompt, "recommend")
        start_time = time.time()

        if parallel_mode:
            # 병렬 실행
            print_status("Claude + Gemini 병렬 분석 중...", "working")
            results = self.ai_engine.call_parallel(
                recommend_prompt,
                include_antigravity=self._include_antigravity_in_parallel()
            )
            elapsed = time.time() - start_time
            print_status(f"병렬 분석 완료 ({elapsed:.1f}초)", "success")

            final_result = self.ai_engine.synthesize_results(results, "고도화 추천")
            success = any(r[0] for r in results.values())
        else:
            # 순차 실행
            success, result = self.ai_engine.call_claude(recommend_prompt)

            if not success:
                success, result = self.ai_engine.fallback_mode(recommend_prompt)

            if success:
                audit_success, audit = self.ai_engine.cross_check("고도화 추천", result)
                elapsed = time.time() - start_time

                final_result = result
                if audit_success and audit:
                    final_result += f"\n\n{Colors.CYAN}{'═' * 50}\n🔍 ADDITIONAL INSIGHTS\n{'═' * 50}{Colors.RESET}\n\n{audit}"

        if success:
            print_section("RECOMMENDATIONS", "📋")
            print(final_result)

            # 리포트 저장
            report_content = f"## 추천 사항\n\n{final_result}"
            report_content += f"\n\n## 실행 정보\n- 모드: {'병렬' if parallel_mode else '순차'}\n- 소요 시간: {elapsed:.1f}초"
            self.save_report("recommend", report_content)

            # 컨텍스트 저장
            self._save_interaction("recommend", base_prompt, final_result)

        print_dashboard(self.stats, self.project_type)

    def ui_ux(self):
        """UI/UX 개선 모드"""
        print_section("UI/UX MODE", "🎨")

        if self.project_type not in [ProjectType.NEXTJS, ProjectType.REACT]:
            print_status("이 모드는 React/Next.js 프로젝트에서만 사용 가능합니다", "warning")
            return

        parallel_mode = self._is_parallel_enabled()
        if parallel_mode:
            print_status("⚡ 병렬 실행 모드 활성화", "info")

        # UI 관련 파일 찾기
        ui_files = get_project_files(self.project_type, [".tsx", ".jsx", ".css", ".scss"])
        print_status(f"UI 컴포넌트: {len(ui_files)}개 파일", "info")

        selected_ui_files = select_important_files(ui_files, MAX_FILES_FOR_UI, self.project_type)
        ui_prompt = f"""현재 React/Next.js 프로젝트의 UI/UX를 분석하고 개선점을 제안해주세요.

UI 파일들 ({len(ui_files)}개 중 {len(selected_ui_files)}개 선택):
{"\n".join([str(f) for f in selected_ui_files])}

다음 관점에서 분석해주세요:

1. 컴포넌트 구조
   - 재사용성 향상 방안
   - 컴포넌트 분리/통합 제안

2. 스타일링 최적화
   - Tailwind CSS 최적화
   - CSS 중복 제거
   - 일관된 디자인 시스템

3. UX 흐름 개선
   - 사용자 여정 최적화
   - 인터랙션 개선
   - 로딩/에러 상태 처리

4. 접근성(a11y) 개선
   - WCAG 가이드라인 준수
   - 키보드 내비게이션
   - 스크린 리더 지원

각 개선 사항에 대해 구체적인 코드 예시를 포함해주세요."""

        start_time = time.time()

        if parallel_mode:
            print_status("Claude + Gemini 병렬 분석 중...", "working")
            results = self.ai_engine.call_parallel(ui_prompt)
            elapsed = time.time() - start_time
            print_status(f"병렬 분석 완료 ({elapsed:.1f}초)", "success")

            final_result = self.ai_engine.synthesize_results(results, "UI/UX 개선")
            success = any(r[0] for r in results.values())
        else:
            success, final_result = self.ai_engine.call_claude(ui_prompt)
            if not success:
                success, final_result = self.ai_engine.fallback_mode(ui_prompt)
            elapsed = time.time() - start_time

        if success:
            print_section("UI/UX IMPROVEMENTS", "✨")
            print(final_result)

            # 리포트 저장
            report_content = f"## UI/UX 개선 제안\n\n{final_result}"
            report_content += f"\n\n## 실행 정보\n- 모드: {'병렬' if parallel_mode else '순차'}\n- 소요 시간: {elapsed:.1f}초"
            self.save_report("ui_ux", report_content)

            # 컨텍스트 저장
            self._save_interaction("ui_ux", "UI/UX 개선 분석", final_result)

        print_dashboard(self.stats, self.project_type)

    def analyze(self, question: str):
        """분석(Q&A) 모드"""
        print_section("ANALYSIS MODE", "🔎")

        parallel_mode = self._is_parallel_enabled()
        if parallel_mode:
            print_status("⚡ 병렬 실행 모드 활성화", "info")

        files = get_project_files(self.project_type)

        selected_files = select_important_files(files, MAX_FILES_FOR_PROMPT, self.project_type)
        base_prompt = f"""다음 질문에 대해 {self.project_type.value} 프로젝트를 분석하여 답변해주세요.

[질문]
{question}

[프로젝트 파일] ({len(files)}개 중 {len(selected_files)}개 선택)
{"\n".join([str(f) for f in selected_files])}

분석 보고서 형식으로 답변해주세요:
1. 요약
2. 상세 분석
3. 관련 코드/파일 위치
4. 추가 권장 사항 (있는 경우)

코드 수정은 하지 마시고 분석만 해주세요."""

        analysis_prompt = self._get_context_enhanced_prompt(base_prompt, "analyze")
        start_time = time.time()

        if parallel_mode:
            print_status("Claude + Gemini 병렬 분석 중...", "working")
            results = self.ai_engine.call_parallel(analysis_prompt)
            elapsed = time.time() - start_time
            print_status(f"병렬 분석 완료 ({elapsed:.1f}초)", "success")

            final_result = self.ai_engine.synthesize_results(results, "코드 분석")
            success = any(r[0] for r in results.values())
        else:
            success, final_result = self.ai_engine.call_claude(analysis_prompt)
            if not success:
                success, final_result = self.ai_engine.fallback_mode(analysis_prompt)
            elapsed = time.time() - start_time

        if success:
            print_section("ANALYSIS REPORT", "📊")
            print(final_result)

            # 리포트 저장
            report_content = f"## 질문\n\n{question}\n\n## 분석 결과\n\n{final_result}"
            report_content += f"\n\n## 실행 정보\n- 모드: {'병렬' if parallel_mode else '순차'}\n- 소요 시간: {elapsed:.1f}초"
            self.save_report("analysis", report_content)

            # 컨텍스트 저장
            self._save_interaction("analyze", question, final_result)

        print_dashboard(self.stats, self.project_type)

    def plan(self, task: str = None):
        """계획 모드"""
        print_section("PLAN MODE", "📝")

        files = get_project_files(self.project_type)

        if not task:
            task = get_user_input(f"{Colors.CYAN}구현할 기능/작업을 설명해주세요: {Colors.RESET}", max_length=MAX_USER_INPUT_LENGTH)
            if not task:
                return

        selected_files = select_important_files(files, MAX_FILES_FOR_PROMPT, self.project_type)
        plan_prompt = f"""다음 작업에 대한 상세 구현 계획을 작성해주세요.

[작업 설명]
{task}

[프로젝트 타입]
{self.project_type.value}

[기존 파일] ({len(files)}개 중 {len(selected_files)}개 선택)
{"\n".join([str(f) for f in selected_files])}

다음 형식으로 구현 계획서를 작성해주세요:

# 구현 계획서

## 1. 개요
- 목표
- 범위

## 2. 기술적 접근 방식
- 사용할 패턴/아키텍처
- 필요한 라이브러리

## 3. 수정/생성 파일 목록
- 각 파일별 변경 사항

## 4. 구현 단계
- 단계별 작업 내용
- 예상 코드 변경

## 5. 테스트 계획
- 테스트 케이스
- 검증 방법

## 6. 리스크 및 고려사항
- 잠재적 문제
- 대안"""

        success, result = self.ai_engine.call_claude(plan_prompt)

        if not success:
            success, result = self.ai_engine.fallback_mode(plan_prompt)

        if success:
            # 계획서 파일로 저장
            with open(PLAN_FILE, 'w', encoding='utf-8') as f:
                f.write(result)

            print_section("IMPLEMENTATION PLAN", "📋")
            print(result)
            print_status(f"계획서 저장됨: {PLAN_FILE}", "success")

        print_dashboard(self.stats, self.project_type)

    def new_project(self, idea: str = None):
        """신규 프로젝트 빌더 모드"""
        print_section("NEW PROJECT BUILDER", "🏗️")

        if not idea:
            idea = get_user_input(f"{Colors.CYAN}프로젝트 아이디어를 설명해주세요: {Colors.RESET}", max_length=MAX_USER_INPUT_LENGTH)
            if not idea:
                return

        new_prompt = f"""다음 아이디어로 새 프로젝트를 생성해주세요.

[아이디어]
{idea}

다음을 포함하여 응답해주세요:

1. 추천 기술 스택
   - 프론트엔드/백엔드
   - 데이터베이스
   - 기타 도구

2. 폴더 구조
```
project-name/
├── src/
│   ├── ...
```

3. 필수 설정 파일 내용
   - package.json 또는 pom.xml/build.gradle
   - 환경 설정 파일

4. 초기 셋업 명령어
```bash
# 프로젝트 생성 명령어
```

5. getting_started.md 내용
   - 설치 방법
   - 실행 방법
   - 개발 가이드"""

        success, result = self.ai_engine.call_claude(new_prompt)

        if not success:
            success, result = self.ai_engine.fallback_mode(new_prompt)

        if success:
            print_section("PROJECT BLUEPRINT", "📐")
            print(result)

            # 리포트 저장
            self.save_report("new_project", f"## 아이디어\n\n{idea}\n\n## 프로젝트 블루프린트\n\n{result}")

            # 프로젝트 생성 확인
            confirm = get_user_input(f"\n{Colors.YELLOW}프로젝트 구조를 생성하시겠습니까? (y/n): {Colors.RESET}", max_length=10, required=False)
            if confirm and confirm.lower() == 'y':
                project_name = get_user_input(f"{Colors.CYAN}프로젝트 폴더 이름: {Colors.RESET}", max_length=MAX_PROJECT_NAME_LENGTH)
                if not project_name:
                    return

                # 프로젝트 폴더가 이미 존재하는지 확인
                project_path = Path.cwd() / project_name
                if project_path.exists():
                    print_status(f"'{project_name}' 폴더가 이미 존재합니다", "error")
                    return

                print_status("Claude에게 프로젝트 생성 요청 중...", "working")

                create_prompt = f"""다음 블루프린트를 기반으로 '{project_name}' 폴더에 프로젝트를 생성해주세요.

[블루프린트]
{result}

다음 작업을 수행해주세요:
1. '{project_name}' 폴더 생성
2. 필요한 모든 파일과 폴더 구조 생성
3. package.json, 설정 파일 등 초기 파일 내용 작성
4. README.md 또는 getting_started.md 작성

실제로 파일을 생성해주세요."""

                create_success, create_result = self.ai_engine.call_claude(create_prompt)

                if create_success:
                    print_status("프로젝트 구조 생성 완료", "success")
                    print(create_result)
                else:
                    print_status("프로젝트 생성 실패 - 수동으로 블루프린트를 참고하여 생성하세요", "warning")

        print_dashboard(self.stats, self.project_type)

    def show_usage(self):
        """사용량 및 상태 표시"""
        print_section("USAGE & STATUS", "📊")

        parallel_enabled = self._is_parallel_enabled()
        parallel_status = f"{Colors.GREEN}✓ 활성화{Colors.RESET}" if parallel_enabled else f"{Colors.YELLOW}✗ 비활성화{Colors.RESET}"

        # 세션 정보
        session_id = self.session_manager.current_session_id or "없음"
        context_count = len(self.session_manager.context_history)
        context_tokens = sum(e.tokens for e in self.session_manager.context_history)

        status = f"""
{Colors.BOLD}AI Models Status:{Colors.RESET}
  {Colors.MAGENTA}Claude:{Colors.RESET}      {'✓ Available' if self.ai_engine.claude_available else '✗ Not Found'}
  {Colors.BLUE}Gemini:{Colors.RESET}      {'✓ Available' if self.ai_engine.gemini_available else '✗ Not Found'}
  {Colors.GREEN}Antigravity:{Colors.RESET} {'✓ Available' if self.ai_engine.antigravity_available else '✗ Not Found'}

{Colors.BOLD}Execution Mode:{Colors.RESET}
  병렬 실행:   {parallel_status}

{Colors.BOLD}Session Info:{Colors.RESET}
  현재 세션:   {session_id}
  컨텍스트:    {context_count}개 기록, ≈{context_tokens} 토큰

{Colors.BOLD}Project Info:{Colors.RESET}
  Type:        {self.project_type.value}
  Directory:   {Path.cwd()}

{Colors.BOLD}Configuration:{Colors.RESET}
  Config File: {CONFIG_FILE}
  Plan File:   {PLAN_FILE}
  Reports Dir: {REPORT_DIR}
  Sessions Dir: {SESSION_DIR}
"""
        print(status)
        print_dashboard(self.stats, self.project_type)

    def show_sessions(self):
        """세션 목록 표시"""
        print_section("SESSION LIST", "📚")

        sessions = self.session_manager.list_sessions()

        if not sessions:
            print_status("저장된 세션이 없습니다", "info")
            return

        print(f"\n{Colors.BOLD}{'ID':<20} {'생성일':<20} {'프로젝트':<15} {'명령 수':<10}{Colors.RESET}")
        print("─" * 70)

        for session in sessions[:10]:  # 최근 10개만
            session_id = session.get("id", "unknown")
            created = session.get("created_at", "")[:16].replace("T", " ")
            project = session.get("project_type", "unknown")[:13]
            commands = session.get("total_commands", 0)

            # 현재 세션 표시
            current_marker = " ◀" if session_id == self.session_manager.current_session_id else ""
            print(f"  {session_id:<18} {created:<20} {project:<15} {commands:<10}{Colors.CYAN}{current_marker}{Colors.RESET}")

        print(f"\n{Colors.DIM}총 {len(sessions)}개 세션 (최근 10개 표시){Colors.RESET}")
        print(f"\n{Colors.YELLOW}세션 이어서 하기:{Colors.RESET} vbg -c 또는 vbg --continue")
        print(f"{Colors.YELLOW}특정 세션 로드:{Colors.RESET} vbg --session <session_id>")

# ═══════════════════════════════════════════════════════════════════════════════
# CLI 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="VBG (Vibe Guardian) - AI Cross-Check Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vbg --refactor          성능 측정 후 AI 리팩토링 제안 (병렬 실행)
  vbg --recommend         고도화 및 기능 추가 제안 (병렬 실행)
  vbg --refactor --seq    순차 실행 모드 (Claude → Gemini)
  vbg --ui-ux             UI/UX 개선 분석 (React/Next.js)
  vbg --plan              구현 전 설계도 작성
  vbg --new               신규 프로젝트 생성
  vbg "질문"              코드 분석 및 Q&A
  vbg --usage             사용량 및 상태 확인
  vbg --init              설정 파일 초기화

Auto-Apply:
  vbg --refactor --apply      제안 후 확인하며 적용 (y/n)
  vbg --refactor --apply-all  제안 후 일괄 적용

Session/Context:
  vbg -c --refactor       이전 세션 이어서 작업
  vbg --sessions          세션 목록 확인
  vbg --session <id>      특정 세션 로드
        """
    )

    parser.add_argument("question", nargs="?", help="분석할 질문")
    parser.add_argument("--refactor", "-r", action="store_true", help="리팩토링 및 성능 벤치마크")
    parser.add_argument("--recommend", "-R", action="store_true", help="고도화 추천")
    parser.add_argument("--ui-ux", "-u", action="store_true", help="UI/UX 개선")
    parser.add_argument("--plan", "-p", nargs="?", const="", help="구현 계획 작성")
    parser.add_argument("--new", "-n", nargs="?", const="", help="신규 프로젝트 생성")
    parser.add_argument("--usage", action="store_true", help="사용량 표시")
    parser.add_argument("--init", action="store_true", help="설정 초기화")
    parser.add_argument("--version", "-v", action="version", version=f"VBG v{VERSION}")
    parser.add_argument("--quiet", "-q", action="store_true", help="배너 숨기기")

    # 코드 적용 옵션
    parser.add_argument("--apply", action="store_true",
                        help="제안된 코드 변경사항을 확인 후 적용 (각 변경마다 y/n)")
    parser.add_argument("--apply-all", action="store_true",
                        help="제안된 코드 변경사항을 일괄 적용")

    # 실행 모드 옵션
    parser.add_argument("--sequential", "--seq", "-s", action="store_true",
                        help="순차 실행 모드 (병렬 대신 Claude→Gemini 순서로 실행)")
    parser.add_argument("--parallel", action="store_true",
                        help="병렬 실행 모드 강제 (기본값)")

    # 세션/컨텍스트 옵션
    parser.add_argument("--continue", "-c", dest="continue_session", action="store_true",
                        help="이전 세션 이어서 작업 (컨텍스트 유지)")
    parser.add_argument("--session", "-S", type=str, metavar="ID",
                        help="특정 세션 ID로 로드")
    parser.add_argument("--sessions", action="store_true",
                        help="세션 목록 표시")

    args = parser.parse_args()

    # 배너 출력
    if not args.quiet:
        print_banner()

    # 설정 초기화
    if args.init:
        save_config(get_default_config())
        print_status("설정 파일이 초기화되었습니다", "success")
        return

    # VBG 코어 초기화 (세션 옵션 포함)
    try:
        vbg = VBGCore(
            continue_session=args.continue_session,
            session_id=args.session
        )
    except Exception as e:
        print_status(f"초기화 실패: {e}", "error")
        return

    # 실행 모드 설정 (CLI 옵션이 설정 파일보다 우선)
    if args.sequential:
        vbg.config.setdefault("execution", {})["parallel"] = False
        print_status("순차 실행 모드로 전환됨", "info")
    elif args.parallel:
        vbg.config.setdefault("execution", {})["parallel"] = True
        print_status("병렬 실행 모드로 전환됨", "info")

    # 명령어 실행
    try:
        if args.sessions:
            vbg.show_sessions()
        elif args.refactor:
            vbg.refactor()
        elif args.recommend:
            vbg.recommend()
        elif args.ui_ux:
            vbg.ui_ux()
        elif args.plan is not None:
            vbg.plan(args.plan if args.plan else None)
        elif args.new is not None:
            vbg.new_project(args.new if args.new else None)
        elif args.usage:
            vbg.show_usage()
        elif args.question:
            vbg.analyze(args.question)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}작업이 취소되었습니다.{Colors.RESET}")
    except Exception as e:
        print_status(f"오류 발생: {e}", "error")
        if os.environ.get("VBG_DEBUG"):
            traceback.print_exc()

if __name__ == "__main__":
    main()
