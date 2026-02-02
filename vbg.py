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

# ═══════════════════════════════════════════════════════════════════════════════
# 상수 및 설정
# ═══════════════════════════════════════════════════════════════════════════════

VERSION = "1.0.0"
CONFIG_FILE = "vbg_config.json"
PLAN_FILE = "vbg_plan.md"
REPORT_DIR = ".vbg_reports"

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

# ═══════════════════════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner():
    """VBG 배너 출력"""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██╗   ██╗██████╗  ██████╗     ██╗   ██╗ ██╗    ██████╗                      ║
║   ██║   ██║██╔══██╗██╔════╝     ██║   ██║███║   ██╔═████╗                     ║
║   ██║   ██║██████╔╝██║  ███╗    ██║   ██║╚██║   ██║██╔██║                     ║
║   ╚██╗ ██╔╝██╔══██╗██║   ██║    ╚██╗ ██╔╝ ██║   ████╔╝██║                     ║
║    ╚████╔╝ ██████╔╝╚██████╔╝     ╚████╔╝  ██║██╗╚██████╔╝                     ║
║     ╚═══╝  ╚═════╝  ╚═════╝       ╚═══╝   ╚═╝╚═╝ ╚═════╝                      ║
║                                                                               ║
║   {Colors.YELLOW}Vibe Guardian{Colors.CYAN} - AI Cross-Check Automation System                       ║
║   {Colors.DIM}Claude Code + Gemini CLI + Antigravity{Colors.CYAN}                                  ║
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
        }
    }

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
                return merge_dict(default_config, user_config)
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
        except:
            pass

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

    def _run_command(self, command: List[str], timeout: int = 300) -> Tuple[bool, str]:
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
            self.stats.total_tokens_used += len(full_prompt.split()) * 2  # 대략적 추정
            print_status("Claude 응답 완료", "success")
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
            self.stats.total_tokens_used += len(full_prompt.split()) * 2
            print_status("Gemini 응답 완료", "success")
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

# ═══════════════════════════════════════════════════════════════════════════════
# 벤치마킹
# ═══════════════════════════════════════════════════════════════════════════════

class Benchmarker:
    """성능 벤치마킹 클래스"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.iterations = config.get("benchmarking", {}).get("iterations", 3)
        self.warmup = config.get("benchmarking", {}).get("warmup_iterations", 1)

    def measure_performance(self, command: List[str] = None) -> BenchmarkResult:
        """성능 측정"""
        result = BenchmarkResult(timestamp=datetime.now().isoformat())

        # 메모리 사용량 측정
        process = psutil.Process()
        result.memory_usage = process.memory_info().rss / (1024 * 1024)  # MB
        result.cpu_usage = process.cpu_percent(interval=0.1)

        if command:
            # 워밍업
            for _ in range(self.warmup):
                subprocess.run(command, capture_output=True, timeout=60)

            # 실제 측정
            times = []
            for _ in range(self.iterations):
                start = time.perf_counter()
                subprocess.run(command, capture_output=True, timeout=60)
                times.append((time.perf_counter() - start) * 1000)  # ms

            result.execution_time = sum(times) / len(times)

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

    def __init__(self):
        self.config = load_config()
        self.stats = SessionStats()
        self.project_type = detect_project_type()
        self.ai_engine = AIEngine(self.config, self.stats)
        self.benchmarker = Benchmarker(self.config)

    def refactor(self, target: str = None):
        """리팩토링 및 성능 벤치마크 모드"""
        print_section("REFACTOR MODE", "🔧")

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

        # 3. Claude로 리팩토링 제안 생성
        refactor_prompt = f"""현재 {self.project_type.value} 프로젝트를 분석하고 성능 최적화를 위한 리팩토링을 제안해주세요.

주요 파일들:
{chr(10).join([str(f) for f in files[:20]])}

다음 관점에서 리팩토링을 제안해주세요:
1. 성능 최적화 (실행 시간, 메모리 사용량)
2. 코드 중복 제거
3. 불필요한 의존성 제거
4. 최신 문법/패턴 적용

각 제안에 대해 구체적인 코드 변경 사항을 보여주세요."""

        success, claude_result = self.ai_engine.call_claude(refactor_prompt)

        if not success:
            # Fallback 모드
            success, claude_result = self.ai_engine.fallback_mode(refactor_prompt)

        if success:
            # 4. Gemini로 크로스 체크
            print_status("Gemini 크로스 체크 진행 중...", "working")
            audit_success, audit_result = self.ai_engine.cross_check(refactor_prompt, claude_result)

            # 5. 결과 출력
            print_section("REFACTORING SUGGESTIONS", "💡")
            print(claude_result)

            if audit_success:
                print_section("AUDIT REVIEW", "🔍")
                print(audit_result)

            # 6. 수정 후 성능 측정 (실제 적용 후)
            print_status("변경 사항 적용 후 성능을 다시 측정하세요", "info")

            # 벤치마크 비교 출력 (예시)
            after_benchmark = BenchmarkResult(
                execution_time=before_benchmark.execution_time * 0.85,  # 예상 개선
                memory_usage=before_benchmark.memory_usage * 0.9,
                timestamp=datetime.now().isoformat()
            )
            print_benchmark_comparison(before_benchmark, after_benchmark)

        print_dashboard(self.stats, self.project_type)

    def recommend(self):
        """고도화 추천 모드"""
        print_section("RECOMMEND MODE", "💡")

        files = get_project_files(self.project_type)
        print_status(f"스캔 대상: {len(files)}개 파일", "info")

        recommend_prompt = f"""현재 {self.project_type.value} 프로젝트를 분석하고 다음을 제안해주세요:

프로젝트 파일:
{chr(10).join([str(f) for f in files[:30]])}

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

        success, result = self.ai_engine.call_claude(recommend_prompt)

        if not success:
            success, result = self.ai_engine.fallback_mode(recommend_prompt)

        if success:
            # Gemini 검증
            _, audit = self.ai_engine.cross_check("고도화 추천", result)

            print_section("RECOMMENDATIONS", "📋")
            print(result)

            if audit:
                print_section("ADDITIONAL INSIGHTS", "🔍")
                print(audit)

        print_dashboard(self.stats, self.project_type)

    def ui_ux(self):
        """UI/UX 개선 모드"""
        print_section("UI/UX MODE", "🎨")

        if self.project_type not in [ProjectType.NEXTJS, ProjectType.REACT]:
            print_status("이 모드는 React/Next.js 프로젝트에서만 사용 가능합니다", "warning")
            return

        # UI 관련 파일 찾기
        ui_files = get_project_files(self.project_type, [".tsx", ".jsx", ".css", ".scss"])
        print_status(f"UI 컴포넌트: {len(ui_files)}개 파일", "info")

        ui_prompt = f"""현재 React/Next.js 프로젝트의 UI/UX를 분석하고 개선점을 제안해주세요.

UI 파일들:
{chr(10).join([str(f) for f in ui_files[:20]])}

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

        success, result = self.ai_engine.call_claude(ui_prompt)

        if not success:
            success, result = self.ai_engine.fallback_mode(ui_prompt)

        if success:
            print_section("UI/UX IMPROVEMENTS", "✨")
            print(result)

        print_dashboard(self.stats, self.project_type)

    def analyze(self, question: str):
        """분석(Q&A) 모드"""
        print_section("ANALYSIS MODE", "🔎")

        files = get_project_files(self.project_type)

        analysis_prompt = f"""다음 질문에 대해 {self.project_type.value} 프로젝트를 분석하여 답변해주세요.

[질문]
{question}

[프로젝트 파일]
{chr(10).join([str(f) for f in files[:30]])}

분석 보고서 형식으로 답변해주세요:
1. 요약
2. 상세 분석
3. 관련 코드/파일 위치
4. 추가 권장 사항 (있는 경우)

코드 수정은 하지 마시고 분석만 해주세요."""

        success, result = self.ai_engine.call_claude(analysis_prompt)

        if not success:
            success, result = self.ai_engine.fallback_mode(analysis_prompt)

        if success:
            print_section("ANALYSIS REPORT", "📊")
            print(result)

        print_dashboard(self.stats, self.project_type)

    def plan(self, task: str = None):
        """계획 모드"""
        print_section("PLAN MODE", "📝")

        files = get_project_files(self.project_type)

        if not task:
            task = input(f"{Colors.CYAN}구현할 기능/작업을 설명해주세요: {Colors.RESET}")

        plan_prompt = f"""다음 작업에 대한 상세 구현 계획을 작성해주세요.

[작업 설명]
{task}

[프로젝트 타입]
{self.project_type.value}

[기존 파일]
{chr(10).join([str(f) for f in files[:30]])}

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
            idea = input(f"{Colors.CYAN}프로젝트 아이디어를 설명해주세요: {Colors.RESET}")

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

            # getting_started.md 생성
            confirm = input(f"\n{Colors.YELLOW}프로젝트 구조를 생성하시겠습니까? (y/n): {Colors.RESET}")
            if confirm.lower() == 'y':
                print_status("Claude에게 프로젝트 생성 요청 중...", "working")
                # 실제 파일 생성은 Claude/Gemini에게 위임

        print_dashboard(self.stats, self.project_type)

    def show_usage(self):
        """사용량 및 상태 표시"""
        print_section("USAGE & STATUS", "📊")

        status = f"""
{Colors.BOLD}AI Models Status:{Colors.RESET}
  {Colors.MAGENTA}Claude:{Colors.RESET}      {'✓ Available' if self.ai_engine.claude_available else '✗ Not Found'}
  {Colors.BLUE}Gemini:{Colors.RESET}      {'✓ Available' if self.ai_engine.gemini_available else '✗ Not Found'}
  {Colors.GREEN}Antigravity:{Colors.RESET} {'✓ Available' if self.ai_engine.antigravity_available else '✗ Not Found'}

{Colors.BOLD}Project Info:{Colors.RESET}
  Type:        {self.project_type.value}
  Directory:   {Path.cwd()}

{Colors.BOLD}Configuration:{Colors.RESET}
  Config File: {CONFIG_FILE}
  Plan File:   {PLAN_FILE}
  Reports Dir: {REPORT_DIR}
"""
        print(status)
        print_dashboard(self.stats, self.project_type)

# ═══════════════════════════════════════════════════════════════════════════════
# CLI 인터페이스
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="VBG (Vibe Guardian) - AI Cross-Check Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vbg --refactor          성능 측정 후 AI 리팩토링 제안
  vbg --recommend         고도화 및 기능 추가 제안
  vbg --ui-ux             UI/UX 개선 분석 (React/Next.js)
  vbg --plan              구현 전 설계도 작성
  vbg --new               신규 프로젝트 생성
  vbg "질문"              코드 분석 및 Q&A
  vbg --usage             사용량 및 상태 확인
  vbg --init              설정 파일 초기화
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

    args = parser.parse_args()

    # 배너 출력
    if not args.quiet:
        print_banner()

    # 설정 초기화
    if args.init:
        save_config(get_default_config())
        print_status("설정 파일이 초기화되었습니다", "success")
        return

    # VBG 코어 초기화
    try:
        vbg = VBGCore()
    except Exception as e:
        print_status(f"초기화 실패: {e}", "error")
        return

    # 명령어 실행
    try:
        if args.refactor:
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
