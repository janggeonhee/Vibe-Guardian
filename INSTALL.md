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

### 1단계: 저장소 클론

```powershell
cd C:\Users\YOUR_USERNAME\Desktop
git clone https://github.com/janggeonhee/Vibe-Guardian.git
```

### 2단계: PowerShell 프로필에 함수 추가

```powershell
# 프로필 열기
notepad $PROFILE

# 아래 내용 추가 (경로는 본인에 맞게 수정)
function vbg { python "C:\Users\YOUR_USERNAME\Desktop\Vibe-Guardian\vbg.py" $args }
```

또는 명령어로 추가:
```powershell
Add-Content $PROFILE "`nfunction vbg { python `"C:\Users\YOUR_USERNAME\Desktop\Vibe-Guardian\vbg.py`" `$args }"
```

### 3단계: 프로필 새로고침

```powershell
. $PROFILE
```

### 4단계: 의존성 설치

```powershell
pip install psutil
```

### 5단계: 설치 확인

```powershell
vbg --version
vbg --usage
```

---

## macOS / Linux 설치

### 방법 A: GitHub에서 클론 (권장)

```bash
# 1. 저장소 클론
cd ~/Desktop
git clone https://github.com/janggeonhee/Vibe-Guardian.git

# 2. 실행 권한 부여
chmod +x ~/Desktop/Vibe-Guardian/vbg.py

# 3. alias 추가 (zsh)
echo 'alias vbg="python3 ~/Desktop/Vibe-Guardian/vbg.py"' >> ~/.zshrc
source ~/.zshrc

# 3-1. bash 사용시
echo 'alias vbg="python3 ~/Desktop/Vibe-Guardian/vbg.py"' >> ~/.bashrc
source ~/.bashrc

# 4. 의존성 설치
pip3 install psutil

# 5. 확인
vbg --version
```

### 방법 B: 다른 위치에 설치

```bash
# 원하는 위치에 클론
git clone https://github.com/janggeonhee/Vibe-Guardian.git ~/tools/Vibe-Guardian

# alias 설정 (경로 맞게 수정)
echo 'alias vbg="python3 ~/tools/Vibe-Guardian/vbg.py"' >> ~/.zshrc
source ~/.zshrc
```

---

## 업데이트 방법

개발 폴더를 직접 사용하므로 git pull만 하면 됩니다:

```bash
cd ~/Desktop/Vibe-Guardian   # 또는 설치 경로
git pull
```

복사 작업 불필요!

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
VBG v1.2.0

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
python --version
# 안 되면 Python 재설치 또는 PATH 확인
```

**Mac:**
```bash
python3 --version
# alias에서 python3 사용 확인
```

### "psutil 모듈 없음" 에러

```bash
pip install psutil    # Windows
pip3 install psutil   # Mac/Linux
```

### "권한 거부" 에러 (Mac/Linux)

```bash
chmod +x ~/Desktop/Vibe-Guardian/vbg.py
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

### oh-my-posh 관련 에러 (Windows)

VBG와 무관한 에러입니다. 해결하려면:
```powershell
# PSReadLine 업데이트
Install-Module PSReadLine -Force -SkipPublisherCheck

# 또는 oh-my-posh 업데이트
winget upgrade JanDeDobbeleer.OhMyPosh
```

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
| `vbg --version` | 버전 확인 |
