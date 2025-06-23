# 한국어 음성 분석 시스템 설치 가이드

## 📋 시스템 요구사항

### 운영체제
- macOS (10.14 이상)
- Windows 10/11
- Linux (Ubuntu 18.04 이상 권장)

### 하드웨어 요구사항
- **메모리**: 최소 8GB RAM (16GB 권장)
- **저장공간**: 최소 10GB 여유 공간
- **GPU**: CUDA 지원 GPU (선택사항, 성능 향상)

### 필수 소프트웨어
- **Anaconda** 또는 **Miniconda** (Python 3.11)
- **FFmpeg** (오디오 처리용)
- **Git** (소스코드 다운로드용)

## 🔧 단계별 설치 가이드

### 1단계: Anaconda/Miniconda 설치

#### macOS
```bash
# Homebrew를 통한 설치
brew install --cask anaconda

# 또는 Miniconda 설치
brew install --cask miniconda
```

#### Windows
1. [Anaconda 공식 웹사이트](https://www.anaconda.com/download)에서 Windows용 설치 파일 다운로드
2. 설치 파일 실행 후 안내에 따라 설치

#### Linux (Ubuntu/Debian)
```bash
# Miniconda 다운로드 및 설치
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 설치 후 터미널 재시작 또는
source ~/.bashrc
```

### 2단계: 프로젝트 다운로드

```bash
# 프로젝트 클론 (Git 사용 시)
git clone <repository-url>
cd ko_analysis

# 또는 ZIP 파일 다운로드 후 압축 해제
```

### 3단계: Conda 환경 생성 및 설정

#### 방법 1: environment.yaml 사용 (권장)

```bash
# 1. 환경 생성 및 패키지 자동 설치
conda env create -f environment.yaml

# 2. 환경 활성화
conda activate ko_pipeline

# 3. 설치 확인
conda list
```

#### 방법 2: 수동 설정

```bash
# 1. 새 환경 생성
conda create -n ko_pipeline python=3.11 -y

# 2. 환경 활성화
conda activate ko_pipeline

# 3. 기본 패키지 설치
conda install pytorch torchaudio -c pytorch
conda install ffmpeg -c conda-forge

# 4. Python 패키지 설치
pip install -r requirements.txt
```

### 4단계: 환경 변수 설정

```bash
# 1. 예시 파일 복사
cp .env.example .env

# 2. 환경 변수 파일 편집
nano .env  # Linux/macOS
notepad .env  # Windows
```

#### 필수 설정 항목:

```env
# OpenAI API 키 (필수)
OPENAI_API_KEY=sk-your-actual-api-key-here

# AWS 자격증명 (S3 사용 시 필수)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-northeast-2

# 데이터베이스 설정
MONGODB_URI=mongodb://localhost:27017/
MARIADB_HOST=localhost
MARIADB_USER=root
MARIADB_PASSWORD=your-password
```

### 5단계: 데이터베이스 설정

#### MongoDB 설치 및 실행

**macOS:**
```bash
# Homebrew로 설치
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb/brew/mongodb-community
```

**Windows:**
1. [MongoDB 공식 사이트](https://www.mongodb.com/try/download/community)에서 다운로드
2. 설치 후 서비스로 실행

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install mongodb
sudo systemctl start mongodb
sudo systemctl enable mongodb
```

#### MariaDB 설치 및 실행

**macOS:**
```bash
brew install mariadb
brew services start mariadb
```

**Windows:**
1. [MariaDB 공식 사이트](https://mariadb.org/download/)에서 다운로드
2. 설치 후 서비스로 실행

**Linux:**
```bash
sudo apt-get install mariadb-server
sudo systemctl start mariadb
sudo systemctl enable mariadb
```

### 6단계: 설치 검증

```bash
# 1. 환경 활성화
conda activate ko_pipeline

# 2. Python 의존성 확인
python -c "import fastapi, openai, librosa, transformers; print('모든 패키지 정상 설치됨')"

# 3. 서버 실행 테스트
python app.py
```

서버가 정상적으로 시작되면 브라우저에서 `http://localhost:8001/docs`에 접속하여 API 문서를 확인할 수 있습니다.

## 🚨 문제 해결

### 일반적인 문제들

#### 1. FFmpeg 관련 오류
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# Windows (chocolatey 사용)
choco install ffmpeg
```

#### 2. PyTorch 설치 오류
```bash
# CPU 버전
conda install pytorch torchaudio cpuonly -c pytorch

# GPU 버전 (CUDA 11.8)
conda install pytorch torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia
```

#### 3. 메모리 부족 오류
- Whisper 모델 크기를 `base`에서 `tiny`로 변경
- `.env` 파일에서 `WHISPER_MODEL_SIZE=tiny` 설정

#### 4. 포트 충돌 오류
```bash
# 다른 포트 사용
uvicorn app:app --host 0.0.0.0 --port 8002
```

#### 5. 패키지 의존성 충돌
```bash
# 환경 완전 재생성
conda env remove -n ko_pipeline
conda env create -f environment.yaml
```

### 로그 확인

```bash
# 애플리케이션 로그 확인
tail -f pipeline.log

# 시스템 로그 확인 (Linux)
journalctl -f
```

## 📞 지원

설치 중 문제가 발생하면:

1. **로그 확인**: `pipeline.log` 파일의 오류 메시지 확인
2. **환경 정보 수집**:
   ```bash
   conda info
   conda list
   python --version
   ```
3. **이슈 리포트**: 오류 메시지와 환경 정보를 포함하여 문의

## 🔄 업데이트

### 패키지 업데이트
```bash
conda activate ko_pipeline
conda env update -f environment.yaml --prune
```

### 환경 백업 및 복원
```bash
# 현재 환경 백업
conda env export > my_environment.yaml

# 환경 복원
conda env create -f my_environment.yaml
``` 