# ----------------------------------------------------------------------------------------------------
# 작성목적 : FastAPI Pydantic 스키마 정의
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 2025-06-25 | 최초 구현 | app.py에서 분리하여 독립적인 스키마 모듈 생성 | 이주형
# ----------------------------------------------------------------------------------------------------

from pydantic import BaseModel
from typing import Optional

class AnalysisRequest(BaseModel):
    """기본 음성 분석 요청 모델"""
    user_id: str
    question_num: int
    s3_audio_url: str
    gender: str = "female"  # male 또는 female

class AnalysisResponse(BaseModel):
    """기본 음성 분석 응답 모델"""
    success: bool
    message: str
    total_score: Optional[float] = None
    ko_score: Optional[float] = None
    text_score: Optional[float] = None

class CommunicationAnalysisRequest(BaseModel):
    """AI-Interview 서버에서 보내는 요청 모델"""
    s3ObjectKey: str

class CommunicationAnalysisResponse(BaseModel):
    """AI-Interview 서버로 보내는 응답 모델"""
    resultCode: str
    resultMessage: str

class HealthResponse(BaseModel):
    """헬스 체크 응답 모델"""
    status: str

class RootResponse(BaseModel):
    """루트 엔드포인트 응답 모델"""
    message: str
    status: str