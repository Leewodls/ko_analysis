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

class AnalysisResponse(BaseModel):
    success: bool
    message: str
    total_score: float = None
    ko_score: float = None
    text_score: float = None

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    ) 