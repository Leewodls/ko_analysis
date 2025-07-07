# 한국어 음성 분석 시스템

FastAPI 기반의 한국어 음성 분석 및 텍스트 평가 시스템입니다.

## 기술 스택

- **프레임워크**: [FastAPI](https://fastapi.tiangolo.com/) (비동기 웹 프레임워크)
- **언어**: [Python 3.11](https://www.python.org/)
- **AI/ML**: [OpenAI Whisper](https://openai.com/research/whisper), [GPT-4o-mini](https://openai.com/gpt-4/)
- **음성 처리**: [librosa](https://librosa.org/), [Praat-parselmouth](https://parselmouth.readthedocs.io/)
- **데이터베이스**: [MongoDB](https://www.mongodb.com/) (비동기 motor), [MariaDB](https://mariadb.org/) (비동기 aiomysql)
- **클라우드**: [AWS S3](https://aws.amazon.com/s3/), [boto3](https://boto3.amazonaws.com/)
- **오디오 변환**: [FFmpeg](https://ffmpeg.org/)
- **프로세스 관리**: [uvicorn](https://www.uvicorn.org/)

## 프로젝트 구조

```
ko_analysis/
├── app.py                         # FastAPI 메인 애플리케이션
├── main.py                        # 한국어 음성 분석 실행 모듈
├── run_pipeline.py                # 파이프라인 실행 스크립트
├── run_pipeline.bat               # Windows 실행 스크립트
│
├── src/                           # 핵심 소스 코드
│   ├── korean_analysis_service.py # 전체 워크플로우 관리 서비스
│   ├── routers.py                 # FastAPI 라우터 정의
│   ├── schemas.py                 # Pydantic 데이터 모델
│   ├── whisper_service.py         # Whisper STT 서비스
│   ├── gpt_evaluator.py           # GPT 텍스트 평가 서비스
│   ├── category_evaluator.py      # 카테고리별 평가 서비스
│   ├── audio_converter.py         # 오디오 파일 변환 서비스
│   ├── s3_service.py              # AWS S3 연동 서비스
│   ├── mongodb_service.py         # MongoDB 연동 서비스
│   ├── mariadb_service.py         # MariaDB 연동 서비스
│   └── utils.py                   # 유틸리티 함수 모음
│
├── data/                          # 데이터 파일
│   └── json/
│       └── korean_audio_data.json # 한국어 음성 데이터
│
├── output/                        # 출력 결과
│   └── json/
│       └── voice_analysis_result.json # 음성 분석 결과
│
├── prompts/                       # GPT 프롬프트 설정
│   ├── answer_summary.yaml        # 답변 요약 프롬프트
│   ├── communication.yaml         # 의사소통 평가 프롬프트
│   ├── job_compatibility.yaml     # 직무 적합도 평가 프롬프트
│   ├── org_fit.yaml               # 조직 적합성 평가 프롬프트
│   ├── problem_solving.yaml       # 문제 해결 능력 평가 프롬프트
│   ├── tech_stack.yaml            # 기술 스택 평가 프롬프트
│   └── README.md                  # 프롬프트 사용법 가이드
│
├── sql/                           # 데이터베이스 스키마
│   └── create_tables.sql          # 테이블 생성 스크립트
│
├── environment.yaml               # Conda 환경 설정
├── requirements.txt               # Python 패키지 목록
└── INSTALLATION_GUIDE.md          # 상세 설치 가이드
```

## 시스템 아키텍처

### 전체 워크플로우

시스템은 다음과 같은 단계로 음성 분석을 수행합니다:

1. **S3 파일 다운로드**: AWS S3에서 음성 파일 획득
2. **오디오 변환**: WebM/MP3 → WAV 16kHz 모노 변환
3. **한국어 음성 분석**: 휴지 비율 및 발화 속도 분석
4. **STT 변환**: Whisper를 통한 음성-텍스트 변환
5. **텍스트 평가**: GPT-4o-mini를 통한 카테고리별 텍스트 분석
6. **데이터 저장**: MongoDB 및 MariaDB에 결과 저장

### 주요 서비스 컴포넌트

#### KoreanAnalysisService
- **역할**: 전체 분석 워크플로우 통합 관리
- **주요 기능**: 
  - 전체 분석 프로세스 조율
  - 각 서비스 모듈 간 데이터 흐름 관리
  - 결과 통합 및 점수 계산

#### AudioConverter
- **역할**: 다양한 오디오 포맷을 WAV로 변환
- **지원 포맷**: WebM, MP3, MP4, M4A, OGG
- **출력 규격**: 16kHz, 모노 채널 WAV

#### WhisperService
- **역할**: 음성-텍스트 변환 (STT)
- **모델**: OpenAI Whisper
- **언어**: 한국어 최적화

#### GPTEvaluator & CategoryEvaluator
- **역할**: 텍스트 내용 평가
- **평가 영역**: 의사소통, 직무적합도, 조직적합성, 문제해결능력, 기술스택
- **모델**: GPT-4o-mini

#### S3Service
- **역할**: AWS S3 파일 다운로드
- **인증**: AWS 자격증명 기반
- **지원**: 직접 URL 다운로드 백업

#### MongoDBService & MariaDBService
- **역할**: 분석 결과 저장
- **MongoDB**: 상세 분석 결과 및 메타데이터
- **MariaDB**: 정규화된 평가 점수 및 카테고리 결과

## 평가 시스템

### 한국어 음성 분석 (40점)

#### 휴지 분석 (20점)
- **20점**: 휴지 비율 17% 미만 (우수)
- **10점**: 휴지 비율 17-25% (보통)
- **0점**: 휴지 비율 25% 이상 (미흡)

#### 발화 속도 (SPS 기반) (20점)
- **20점**: 5.22~5.76 (최적 속도)
- **15점**: 4.68~5.22 또는 5.76~6.12 (양호)
- **10점**: 4.50~4.68 또는 6.12~6.48 (보통)
- **0점**: 4.13~4.50 또는 6.48~6.88 (미흡)

### 텍스트 분석 (60점)

#### 카테고리별 평가
- **의사소통 능력**: 내용 구성, 논리성, 어휘 선택력
- **직무 적합도**: 기술적 전문성, 실무 경험, 적용 능력
- **조직 적합성**: 협업 능력, 문화 적응력
- **문제 해결 능력**: 분석적 사고, 창의적 접근
- **기술 스택**: 전문 지식, 학습 능력

## API 엔드포인트

### POST /analysis
전체 분석 프로세스 실행
```json
{
    "user_id": "user123",
    "question_num": 1,
    "s3_audio_url": "https://bucket.s3.region.amazonaws.com/audio.webm",
    "gender": "female"
}
```

### POST /analysis/communication
AI-Interview 서버 연동용 의사소통 분석
```json
{
    "s3ObjectKey": "team12/interview_audio/user123/1/recording.webm"
}
```

### GET /health
서버 상태 확인
```json
{
    "status": "healthy",
    "timestamp": "2024-01-01T00:00:00Z"
}
```

## 설치 및 실행

### 환경 요구사항
- Python 3.11+
- Conda (권장)
- FFmpeg
- MongoDB (선택)
- MariaDB

### 1. 환경 설정

#### Conda 환경 생성 (권장)
```bash
# 환경 생성 및 패키지 설치
conda env create -f environment.yaml

# 환경 활성화
conda activate ko_pipeline
```

#### 수동 설치
```bash
# 가상환경 생성
conda create -n ko_pipeline python=3.11 -y
conda activate ko_pipeline

# 패키지 설치
pip install -r requirements.txt

# PyTorch 설치 (GPU 사용 시)
conda install pytorch torchaudio -c pytorch

# FFmpeg 설치
conda install ffmpeg -c conda-forge
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성 및 설정
cp .env.example .env
```

필수 환경 변수:
```env
# MongoDB 설정
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=audio_analysis

# MariaDB 설정
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_USER=root
MARIADB_PASSWORD=password
MARIADB_DATABASE=communication_db

# OpenAI 설정
OPENAI_API_KEY=your_openai_api_key

# AWS S3 설정
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=your_bucket_name
```

### 3. 서버 실행

#### Windows
```cmd
run_pipeline.bat
```

#### macOS/Linux
```bash
chmod +x run_pipeline.sh
./run_pipeline.sh
```

#### Python 직접 실행
```bash
conda activate ko_pipeline
python app.py
# 또는
uvicorn app:app --reload --port 8004
```

### 4. 서버 접속
- **기본 주소**: http://localhost:8004
- **API 문서**: http://localhost:8004/docs
- **ReDoc**: http://localhost:8004/redoc

## 개발 가이드

### 새로운 평가 카테고리 추가

1. `prompts/` 디렉토리에 새로운 YAML 프롬프트 파일 생성
2. `category_evaluator.py`에 카테고리 평가 로직 추가
3. `mariadb_service.py`에 테이블 스키마 업데이트

### 새로운 API 엔드포인트 추가

1. `schemas.py`에 요청/응답 모델 정의
2. `routers.py`에 엔드포인트 구현
3. `korean_analysis_service.py`에 비즈니스 로직 추가

### 데이터베이스 스키마 변경

1. `sql/create_tables.sql` 업데이트
2. 해당 서비스 클래스의 테이블 생성 메서드 수정
3. 마이그레이션 스크립트 작성 (필요시)

## 스크립트

```bash
# 개발 서버 실행
python app.py

# 프로덕션 서버 실행
uvicorn app:app --host 0.0.0.0 --port 8004

# 환경 정보 확인
conda env list

# 환경 업데이트
conda env update -f environment.yaml

# 환경 삭제
conda env remove -n ko_pipeline
```

## 환경 관리

### 패키지 의존성 업데이트
```bash
# requirements.txt 업데이트
pip freeze > requirements.txt

# environment.yaml 업데이트
conda env export > environment.yaml
```

### 로그 관리
- 로그 레벨: INFO
- 로그 위치: 콘솔 출력
- 주요 로그: 분석 진행 상황, 오류 정보, 성능 메트릭

## 성능 최적화

### 메모리 관리
- 임시 파일 자동 정리
- 모델 메모리 효율적 로딩
- 비동기 처리를 통한 동시성 향상

### 처리 속도
- GPU 가속 지원 (PyTorch)
- 파일 스트리밍 다운로드
- 데이터베이스 연결 풀링

## 문제 해결

### 일반적인 오류

#### FFmpeg 관련 오류
```bash
# FFmpeg 재설치
conda install ffmpeg -c conda-forge --force-reinstall
```

#### 모델 로딩 오류
```bash
# Whisper 모델 재다운로드
python -c "import whisper; whisper.load_model('base')"
```

#### 데이터베이스 연결 오류
- 환경 변수 설정 확인
- 네트워크 연결 상태 점검
- 자격 증명 유효성 검사

### 로그 분석
주요 로그 패턴:
- `INFO`: 정상 처리 과정
- `WARNING`: 비중요 오류 (MongoDB 비연결 등)
- `ERROR`: 중요한 처리 오류

## 보안 고려사항

### 환경 변수 관리
- `.env` 파일을 버전 관리에서 제외
- 프로덕션 환경에서 환경 변수 암호화
- API 키 정기 교체

### 접근 제어
- CORS 설정 검토
- API 엔드포인트 인증 추가 고려
- 파일 업로드 검증 강화

## 라이선스

이 프로젝트는 내부 사용을 위한 것이며, 상용 라이브러리 및 API 사용 시 해당 라이선스를 준수해야 합니다.
