# 한국어 음성 분석 서버

FastAPI 기반의 한국어 음성 분석 및 텍스트 평가 시스템입니다.

## 📚 문서

- **[설치 가이드](INSTALLATION_GUIDE.md)**: 상세한 설치 및 설정 방법
- **[Environment.yaml](environment.yaml)**: Conda 환경 설정 파일
- **[Requirements.txt](requirements.txt)**: Python 패키지 목록

## 🎯 주요 기능

- **한국어 음성 분석**: 휴지(20점) + 발화 속도(20점) = 40점
- **텍스트 분석**: 내용 구성(20점) + 논리성(20점) + 어휘 선택력(20점) = 60점
- **총 점수**: 100점 만점 시스템
- **실시간 처리**: S3 → 음성변환 → 분석 → STT → GPT 평가 → DB 저장

## 📊 점수 체계 (v2.0 - 감정 분석 제거)

### 한국어 음성 분석 (40점)

#### 1. 휴지 분석 (20점)
- **20점**: 휴지 비율 17% 미만 (우수)
- **10점**: 휴지 비율 17-25% (보통)
- **0점**: 휴지 비율 25% 이상 (미흡)

#### 2. 발화 속도 (SPS 기반) (20점)
- **20점**: 5.22~5.76 (최적 속도)
- **15점**: 4.68~5.22 또는 5.76~6.12 (양호)
- **10점**: 4.50~4.68 또는 6.12~6.48 (보통)
- **0점**: 4.13~4.50 또는 6.48~6.88 (미흡)

### 텍스트 분석 (60점)
- **내용 구성**: 20점 (주제 적합성, 구조화)
- **논리성**: 20점 (논리적 연결, 일관성)
- **어휘 선택력**: 20점 (적절성, 다양성)

## 🚀 설치 및 실행 방법

### 1. Conda 환경 설정

#### Option 1: environment.yaml 사용 (권장)
```bash
# 1. 환경 생성 및 패키지 설치
conda env create -f environment.yaml

# 2. 환경 활성화
conda activate ko_pipeline
```

#### Option 2: 수동 환경 생성
```bash
# 1. conda 가상환경 생성
conda create -n ko_pipeline python=3.11 -y

# 2. 환경 활성화
conda activate ko_pipeline

# 3. pip 패키지 설치
pip install -r requirements.txt

# 4. PyTorch 설치 (GPU 사용 시)
conda install pytorch torchaudio -c pytorch

# 5. FFmpeg 설치
conda install ffmpeg -c conda-forge
```

### 2. 환경 변수 설정
```bash
# .env.example을 복사하여 .env 파일 생성
cp .env.example .env

# .env 파일 편집하여 실제 설정값 입력
nano .env  # 또는 원하는 편집기 사용
```

### 3. 서버 실행

#### macOS/Linux:
```bash
# 실행 권한 부여 (최초 1회)
chmod +x run_pipeline.sh

# 서버 실행
./run_pipeline.sh
```

#### Windows:
```cmd
run_pipeline.bat
```

#### Python 직접 실행:
```bash
# conda 환경 활성화 후
conda activate ko_pipeline
python app.py
```

### 4. 서버 접속
- **기본 주소**: http://localhost:8001
- **API 문서**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### 5. 환경 관리

#### 환경 목록 확인:
```bash
conda env list
```

#### 환경 삭제:
```bash
conda env remove -n ko_pipeline
```

#### 환경 업데이트:
```bash
conda activate ko_pipeline
conda env update -f environment.yaml
```

## 📋 API 엔드포인트

### POST /analyze
전체 분석 (음성 + 텍스트)
```json
{
    "user_id": "user123",
    "question_num": 1,
    "s3_audio_url": "https://bucket.s3.region.amazonaws.com/audio.webm",
    "gender": "female"
}
```

### POST /analyze/voice-only
음성 분석만
```json
{
    "user_id": "user123", 
    "question_num": 1,
    "s3_audio_url": "https://bucket.s3.region.amazonaws.com/audio.webm",
    "gender": "female"
}
```

## ⚙️ 환경 설정

`.env` 파일에 다음 설정들을 입력하세요:

```env
# MongoDB 설정
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=audio_video_analysis
MONGODB_COLLECTION_NAME=ko_analysis

# MariaDB 설정
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_USER=root
MARIADB_PASSWORD=password
MARIADB_DATABASE=communication_db

# OpenAI 설정
OPENAI_API_KEY=your_openai_api_key_here

# AWS S3 설정
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=your_bucket_name
```

## 🔧 기술 스택

- **FastAPI** (비동기)
- **MongoDB** with motor driver
- **MariaDB** with aiomysql  
- **Whisper** (STT)
- **GPT-4o-mini** (텍스트 평가)
- **FFmpeg** (오디오 변환)
- **boto3** (S3 연동)

## 📁 프로젝트 구조

```
ko_analysis/
├── app.py                 # FastAPI 메인 애플리케이션
├── main.py               # 한국어 음성 분석 실행
├── voice_analysis.py     # 음성 분석 로직
├── run_server.py         # 서버 실행 스크립트
├── start_server.sh       # Unix/Linux 실행 스크립트
├── start_server.bat      # Windows 실행 스크립트
├── src/
│   ├── korean_analysis_service.py  # 전체 워크플로우 관리
│   ├── whisper_service.py          # STT 변환
│   ├── gpt_evaluator.py            # GPT 텍스트 평가
│   ├── audio_converter.py          # 오디오 변환
│   ├── mongodb_service.py          # MongoDB 연동
│   ├── mariadb_service.py          # MariaDB 연동
│   └── s3_service.py               # S3 파일 다운로드
├── model/                # 한국어 분석 모델
├── data/                 # 데이터 파일
└── .env                  # 환경 변수 파일
```

## 🔄 워크플로우

1. **S3 파일 다운로드** → 음성 파일 획득
2. **오디오 변환** → webm을 wav로 변환
3. **한국어 음성 분석** → 휴지, 속도 분석 (40점)
4. **Whisper STT** → 음성을 텍스트로 변환
5. **GPT 텍스트 평가** → 내용, 논리성, 어휘 평가 (60점)
6. **GPT 최종 코멘트** → 종합 피드백 생성
7. **MongoDB 저장** → 상세 분석 결과 저장
8. **MariaDB 저장** → 최종 점수 및 코멘트 저장
