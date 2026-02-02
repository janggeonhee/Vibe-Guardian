# VBG (Vibe Guardian) 설치 가이드

## 사전 요구사항

| 도구 | 필수 | 설치 확인 |
|------|------|----------|
| Python 3.8+ | O | `python --version` |
| psutil | O | `pip install psutil` |
| Claude CLI | O | `claude --version` |
| Gemini CLI | △ | `gemini --version` |
| Antigravity | △ | `antigravity --version` |

---

## Windows (PowerShell) 설치

### 1단계: 폴더 생성 및 파일 복사

```powershell
# tools 폴더 생성
mkdir $HOME\tools -Force

# vbg.py 복사 (현재 위치에 vbg.py가 있다고 가정)
Copy-Item ".\vbg.py" "$HOME\tools\vbg.py"

# 또는 직접 경로 지정
Copy-Item "C:\Users\ghjan\Desktop\geoni\Vibe-Guardian\vbg.py" "$HOME\tools\vbg.py"
```

### 2단계: PowerShell 프로필에 함수 추가

```powershell
# 프로필에 vbg 함수 추가 (줄바꿈 포함)
Add-Content $PROFILE "`nfunction vbg { python `"$HOME\tools\vbg.py`" `$args }"

# 프로필 새로고침
. $PROFILE
```

### 3단계: 의존성 설치

```powershell
pip install psutil
```

### 4단계: 설치 확인

```powershell
vbg --version
vbg --usage
```

---

## macOS / Linux (zsh/bash) 설치

### 방법 A: GitHub에서 설치 (권장)

```bash
# 1. 저장소 클론 (GitHub에 올린 경우)
git clone https://github.com/YOUR_USERNAME/Vibe-Guardian.git
cd Vibe-Guardian

# 2. tools 폴더에 복사
mkdir -p ~/tools
cp vbg.py ~/tools/vbg.py

# 3. 실행 권한 부여
chmod +x ~/tools/vbg.py

# 4. alias 추가 (zsh)
echo 'alias vbg="python3 ~/tools/vbg.py"' >> ~/.zshrc
source ~/.zshrc

# 4-1. alias 추가 (bash 사용시)
echo 'alias vbg="python3 ~/tools/vbg.py"' >> ~/.bashrc
source ~/.bashrc

# 5. 의존성 설치
pip3 install psutil
```

### 방법 B: 파일 직접 생성

```bash
# 1. tools 폴더 생성
mkdir -p ~/tools

# 2. 파일 생성 (복사/붙여넣기)
nano ~/tools/vbg.py
# 또는
code ~/tools/vbg.py

# (vbg.py 내용을 붙여넣고 저장)

# 3. 실행 권한 부여
chmod +x ~/tools/vbg.py

# 4. alias 추가
echo 'alias vbg="python3 ~/tools/vbg.py"' >> ~/.zshrc
source ~/.zshrc

# 5. 의존성 설치
pip3 install psutil
```

### 방법 C: 클라우드/USB로 파일 전송

```bash
# Google Drive, Dropbox, iCloud 등에서 다운로드 후:
mkdir -p ~/tools
cp ~/Downloads/vbg.py ~/tools/vbg.py
chmod +x ~/tools/vbg.py

echo 'alias vbg="python3 ~/tools/vbg.py"' >> ~/.zshrc
source ~/.zshrc

pip3 install psutil
```

---

## Windows ↔ Mac 파일 전송 방법

### 1. GitHub 사용 (권장)

**Windows에서:**
```powershell
cd C:\Users\ghjan\Desktop\geoni\Vibe-Guardian
git init
git add vbg.py vbg_config.json INSTALL.md
git commit -m "Initial VBG setup"
git remote add origin https://github.com/YOUR_USERNAME/Vibe-Guardian.git
git push -u origin main
```

**Mac에서:**
```bash
git clone https://github.com/YOUR_USERNAME/Vibe-Guardian.git
```

### 2. 클라우드 스토리지

- Google Drive / Dropbox / OneDrive / iCloud에 `vbg.py` 업로드
- Mac에서 다운로드

### 3. 이메일로 전송

- `vbg.py` 파일을 자신에게 이메일로 전송
- Mac에서 다운로드

### 4. USB 드라이브

- Windows에서 USB에 복사
- Mac에서 USB 연결 후 복사

---

## 설치 확인

```bash
# 버전 확인
vbg --version

# 상태 확인
vbg --usage

# 도움말
vbg --help
```

### 정상 출력 예시

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║   VBG v1.0                                                                    ║
║   Vibe Guardian - AI Cross-Check Automation System                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

AI Models Status:
  Claude:      ✓ Available
  Gemini:      ✓ Available
  Antigravity: ✗ Not Found
```

---

## 문제 해결

### "python을 찾을 수 없음" 에러

**Windows:**
```powershell
# python3 대신 python 사용 확인
python --version

# 안 되면 Python 재설치 또는 PATH 확인
```

**Mac:**
```bash
# python3 사용
python3 --version

# alias에서 python3으로 변경
alias vbg="python3 ~/tools/vbg.py"
```

### "psutil 모듈 없음" 에러

```bash
pip install psutil    # Windows
pip3 install psutil   # Mac/Linux
```

### "권한 거부" 에러 (Mac/Linux)

```bash
chmod +x ~/tools/vbg.py
```

### alias가 작동하지 않음

```bash
# 현재 쉘 확인
echo $SHELL

# zsh인 경우
source ~/.zshrc

# bash인 경우
source ~/.bashrc

# 또는 터미널 완전히 닫고 다시 열기
```

---

## 설정 파일 위치

| 파일 | 설명 |
|------|------|
| `~/tools/vbg.py` | 메인 스크립트 |
| `./vbg_config.json` | 프로젝트별 설정 (실행 디렉토리) |
| `./vbg_plan.md` | 생성된 계획서 |
| `./.vbg_reports/` | 성능 리포트 저장 |

---

## 빠른 명령어 참조

| 명령어 | 설명 |
|--------|------|
| `vbg --refactor` | 리팩토링 + 성능 벤치마크 |
| `vbg --recommend` | 고도화 추천 |
| `vbg --ui-ux` | UI/UX 개선 (React/Next.js) |
| `vbg --plan "작업"` | 구현 계획 작성 |
| `vbg --new "아이디어"` | 신규 프로젝트 생성 |
| `vbg "질문"` | 코드 분석 Q&A |
| `vbg --usage` | 사용량 확인 |
| `vbg --init` | 설정 초기화 |
