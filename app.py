# ----------------------------------------------------------------------------------------------------
# 작성목적 : FastAPI 기반 한국어 음성 분석 서버
# 작성일 : 이재인

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | FastAPI 기반 한국어 음성 분석 서버 구현 | 이재인
# 2025-06-25 | 기능 추가 | AI-Interview 서버 연동을 위한 /communication 엔드포인트 추가 | 이주형
# ----------------------------------------------------------------------------------------------------

"""
FastAPI 기반 한국어 음성 분석 서버
S3 음성파일 → 분석 → MongoDB/MariaDB 저장 전체 워크플로우
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import logging
from contextlib import asynccontextmanager
from src.korean_analysis_service import KoreanAnalysisService

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 전역 서비스 인스턴스
analysis_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global analysis_service
    
    # 시작 시 초기화
    logger.info("서버 시작 - 서비스 초기화 중...")
    analysis_service = KoreanAnalysisService()
    await analysis_service.initialize()
    logger.info("서버 초기화 완료")
    
    yield
    
    # 종료 시 정리
    logger.info("서버 종료 - 리소스 정리 중...")
    if analysis_service:
        await analysis_service.cleanup()
    logger.info("서버 종료 완료")

# FastAPI 앱 생성
app = FastAPI(
    title="Korean Voice Analysis API",
    description="한국어 음성 분석 서비스 - S3에서 음성파일을 불러와 감정, 휴지, 속도, 텍스트 분석 후 DB 저장",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청 모델
class AnalysisRequest(BaseModel):
    user_id: str
    question_num: int
    s3_audio_url: str
    gender: str = "female"  # male 또는 female

# AI-Interview 서버에서 보내는 요청 모델
class CommunicationAnalysisRequest(BaseModel):
    s3ObjectKey: str

class AnalysisResponse(BaseModel):
    success: bool
    message: str
    total_score: float = None
    ko_score: float = None
    text_score: float = None

# AI-Interview 서버로 보내는 응답 모델
class CommunicationAnalysisResponse(BaseModel):
    resultCode: str
    resultMessage: str

@app.get("/")
async def root():
    """API 상태 확인"""
    return {"message": "Korean Voice Analysis API", "status": "running"}

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_voice(request: AnalysisRequest):
    """
    음성 분석 메인 엔드포인트
    S3 → 변환 → 분석 → STT → GPT 평가 → DB 저장 전체 프로세스
    """
    try:
        logger.info(f"분석 요청 수신: user_id={request.user_id}, question_num={request.question_num}")
        
        if not analysis_service:
            raise HTTPException(status_code=500, detail="서비스가 초기화되지 않았습니다.")
        
        # 전체 분석 프로세스 실행
        result = await analysis_service.analyze_complete_workflow(
            user_id=request.user_id,
            question_num=request.question_num,
            s3_audio_url=request.s3_audio_url,
            gender=request.gender
        )
        
        return AnalysisResponse(
            success=True,
            message="분석이 성공적으로 완료되었습니다.",
            total_score=result.get("total_score"),
            ko_score=result.get("ko_score"),
            text_score=result.get("text_score")
        )
        
    except Exception as e:
        logger.error(f"분석 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")

@app.post("/analyze/voice-only")
async def analyze_voice_only(request: AnalysisRequest):
    """음성 분석만 수행 (텍스트 분석 제외)"""
    try:
        logger.info(f"음성 분석 요청: user_id={request.user_id}, question_num={request.question_num}")
        
        if not analysis_service:
            raise HTTPException(status_code=500, detail="서비스가 초기화되지 않았습니다.")
        
        result = await analysis_service.analyze_voice_only(
            user_id=request.user_id,
            question_num=request.question_num,
            s3_audio_url=request.s3_audio_url,
            gender=request.gender
        )
        
        return AnalysisResponse(
            success=True,
            message="음성 분석이 완료되었습니다.",
            ko_score=result.get("ko_score")
        )
        
    except Exception as e:
        logger.error(f"음성 분석 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"음성 분석 중 오류가 발생했습니다: {str(e)}")

@app.post("/communication", response_model=CommunicationAnalysisResponse)
async def communication_analysis(request: CommunicationAnalysisRequest):
    """
    AI-Interview 서버에서 의사소통 분석 요청을 받는 엔드포인트
    S3 Object Key를 받아서 한국어 음성 분석을 수행하고 결과를 DB에 저장
    
    워크플로우:
    1. S3에서 음성 파일 다운로드
    2. WebM → WAV 변환
    3. 한국어 음성 분석 (휴지 비율 + 발화 속도) - 40점
    4. Whisper STT 변환
    5. GPT 텍스트 분석 (내용구성 + 논리성 + 어휘선택) - 60점
    6. MongoDB/MariaDB에 결과 저장
    """
    try:
        logger.info(f"AI-Interview 서버로부터 의사소통 분석 요청 수신")
        logger.info(f"S3 Object Key: {request.s3ObjectKey}")
        
        if not analysis_service:
            logger.error("분석 서비스가 초기화되지 않았습니다.")
            return CommunicationAnalysisResponse(
                resultCode="5000",
                resultMessage="분석 서비스 초기화 오류"
            )
        
        # S3 Object Key 검증
        if not request.s3ObjectKey or request.s3ObjectKey.strip() == "":
            logger.error("S3 Object Key가 비어있습니다.")
            return CommunicationAnalysisResponse(
                resultCode="4000",
                resultMessage="유효하지 않은 S3 Object Key"
            )
        
        # S3 Object Key를 URL 형태로 변환
        # 예: "bucket-name/path/to/file.webm" → "s3://bucket-name/path/to/file.webm"
        if not request.s3ObjectKey.startswith('s3://'):
            s3_audio_url = f"s3://{request.s3ObjectKey}"
        else:
            s3_audio_url = request.s3ObjectKey
        
        logger.info(f"S3 URL 변환 완료: {s3_audio_url}")
        
        # S3 Object Key에서 user_id와 question_num 추출 시도
        user_id, question_num = _extract_user_info_from_s3_key(request.s3ObjectKey)
        
        if not user_id:
            user_id = "ai_interview_user"
            logger.warning(f"S3 경로에서 user_id 추출 실패, 기본값 사용: {user_id}")
        
        if question_num is None:
            question_num = 1  
            logger.warning(f"S3 경로에서 question_num 추출 실패, 기본값 사용: {question_num}")
        
        logger.info(f"추출된 사용자 정보 - user_id: {user_id}, question_num: {question_num}")
        
        # 전체 한국어 음성 + 텍스트 분석 워크플로우 실행
        logger.info("전체 분석 워크플로우 시작...")
        result = await analysis_service.analyze_complete_workflow(
            user_id=user_id,
            question_num=question_num,
            s3_audio_url=s3_audio_url,
            gender="female"  # 기본값, 필요시 요청에서 받도록 확장 가능
        )
        
        # 분석 성공 여부 확인
        if result.get('success', True):
            total_score = result.get('total_score', 0)
            voice_score = result.get('voice_score', 0)
            text_score = result.get('text_score', 0)
            
            logger.info("의사소통 분석 완료!")
            logger.info(f"  총점: {total_score:.1f}점/100점")
            logger.info(f"  음성 점수: {voice_score:.1f}점/40점")
            logger.info(f"  텍스트 점수: {text_score:.1f}점/60점")
            logger.info("  결과가 MongoDB 및 MariaDB에 저장되었습니다.")
            
            return CommunicationAnalysisResponse(
                resultCode="0000",
                resultMessage="의사소통 분석 요청 완료"
            )
        else:
            logger.error("분석 워크플로우에서 오류가 발생했습니다.")
            return CommunicationAnalysisResponse(
                resultCode="5001",
                resultMessage="분석 처리 중 오류 발생"
            )
        
    except Exception as e:
        logger.error(f"의사소통 분석 중 예외 발생: {str(e)}", exc_info=True)
        return CommunicationAnalysisResponse(
            resultCode="9999",
            resultMessage=f"의사소통 분석 중 시스템 오류가 발생했습니다"
        )

def _extract_user_info_from_s3_key(s3_object_key: str) -> tuple:
    """
    S3 Object Key에서 user_id와 question_num 추출
    
    예상 경로 패턴:
    - team12/interview_audio/{userId}/{question_num}/{파일명}
    - bucket-name/path/{userId}/{question_num}/file.webm
    
    Returns:
        tuple: (user_id, question_num) 또는 (None, None)
    """
    try:
        import re
        
        # S3 URL 프리픽스 제거
        clean_key = s3_object_key.replace('s3://', '')
        if '/' in clean_key:
            # 첫 번째 '/' 이후 부분만 사용 (버킷명 제거)
            parts = clean_key.split('/', 1)
            if len(parts) > 1:
                clean_key = parts[1]
        
        path_parts = clean_key.split('/')
        
        # 패턴 1: team12/interview_audio/{userId}/{question_num}/{파일명}
        if len(path_parts) >= 4 and 'interview_audio' in path_parts:
            interview_idx = path_parts.index('interview_audio')
            if interview_idx + 2 < len(path_parts):
                user_id = path_parts[interview_idx + 1]
                question_part = path_parts[interview_idx + 2]
                
                # 숫자 추출
                question_match = re.search(r'([0-9]+)', question_part)
                if question_match:
                    return user_id, int(question_match.group(1))
        
        # 패턴 2: 파일명에서 추출
        filename = path_parts[-1] if path_parts else s3_object_key
        filename_no_ext = filename.rsplit('.', 1)[0]
        
        # user{id}_question{num} 패턴
        pattern = r'user([a-zA-Z0-9_-]+)_(?:question|q)([0-9]+)'
        match = re.search(pattern, filename_no_ext, re.IGNORECASE)
        if match:
            return match.group(1), int(match.group(2))
        
        # 단순 {userid}_{questionnum} 패턴  
        simple_pattern = r'([a-zA-Z0-9_-]+)_([0-9]+)'
        simple_match = re.search(simple_pattern, filename_no_ext)
        if simple_match:
            return simple_match.group(1), int(simple_match.group(2))
            
        logger.debug(f"S3 경로에서 사용자 정보 추출 실패: {s3_object_key}")
        return None, None
        
    except Exception as e:
        logger.warning(f"S3 경로 파싱 오류: {s3_object_key} - {str(e)}")
        return None, None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8004, 
        reload=True,
        log_level="info"
    )