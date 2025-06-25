# ----------------------------------------------------------------------------------------------------
# 작성목적 : FastAPI 기반 한국어 음성 분석 서버
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | FastAPI 기반 한국어 음성 분석 서버 구현 | 이재인
# 2025-06-25 | 기능 추가 | AI-Interview 서버 연동을 위한 /communication 엔드포인트 추가 | 이주형
# ----------------------------------------------------------------------------------------------------

"""
FastAPI 기반 한국어 음성 분석 서버
S3 음성파일 → 분석 → MongoDB/MariaDB 저장 전체 워크플로우
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from contextlib import asynccontextmanager

# 내부 모듈 임포트
from src.korean_analysis_service import KoreanAnalysisService
from src.routers import router, set_analysis_service

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
    
    # 라우터에 서비스 인스턴스 주입
    set_analysis_service(analysis_service)
    
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

# 라우터 등록
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8004, 
        reload=True,
        log_level="info"
    )