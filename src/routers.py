# ----------------------------------------------------------------------------------------------------
# 작성목적 : FastAPI 라우터 정의
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 2025-06-25 | 최초 구현 | app.py에서 분리하여 독립적인 라우터 모듈 생성 | 이주형
# 2025-12-19 | 디버깅 기능 | S3 디버깅용 엔드포인트 추가 | 구동빈
# ----------------------------------------------------------------------------------------------------

"""
FastAPI 라우터 정의
API 엔드포인트들을 정의합니다.
"""

from fastapi import APIRouter, HTTPException
import logging

from .schemas import (
    AnalysisRequest, 
    AnalysisResponse, 
    CommunicationAnalysisRequest, 
    CommunicationAnalysisResponse,
    HealthResponse,
    RootResponse
)
from .utils import extract_user_info_from_s3_key, format_s3_url

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# 전역 서비스 인스턴스 (app.py에서 주입됨)
analysis_service = None

def set_analysis_service(service):
    """서비스 인스턴스 설정"""
    global analysis_service
    analysis_service = service

@router.get("/", response_model=RootResponse)
async def root():
    """API 상태 확인"""
    return RootResponse(message="Korean Voice Analysis API", status="running")

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스 체크"""
    return HealthResponse(status="healthy")

@router.post("/debug/s3-check")
async def debug_s3_file_check(request: CommunicationAnalysisRequest):
    """
    S3 파일 존재 여부 확인 (디버깅용)
    """
    try:
        if not analysis_service:
            raise HTTPException(status_code=500, detail="서비스가 초기화되지 않았습니다.")
        
        # S3 Object Key를 URL로 변환
        s3_audio_url = format_s3_url(request.s3ObjectKey)
        logger.info(f"S3 URL 변환: {request.s3ObjectKey} -> {s3_audio_url}")
        
        # 파일 존재 여부 확인
        file_check = await analysis_service.s3_service.check_file_exists(s3_audio_url)
        
        # 상위 디렉토리 내용도 확인
        from urllib.parse import urlparse
        parsed = urlparse(s3_audio_url)
        parent_path = '/'.join(parsed.path.split('/')[:-1])
        parent_url = f"s3://{parsed.netloc}{parent_path}"
        
        dir_contents = await analysis_service.s3_service.list_bucket_contents(parent_url, max_keys=20)
        
        return {
            "s3_object_key": request.s3ObjectKey,
            "s3_url": s3_audio_url,
            "file_check": file_check,
            "parent_directory": parent_url,
            "directory_contents": dir_contents
        }
        
    except Exception as e:
        logger.error(f"S3 디버깅 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"디버깅 중 오류: {str(e)}")

@router.post("/debug/s3-list")
async def debug_s3_list_directory(s3_path: str):
    """
    S3 디렉토리 내용 리스팅 (디버깅용)
    """
    try:
        if not analysis_service:
            raise HTTPException(status_code=500, detail="서비스가 초기화되지 않았습니다.")
        
        # S3 경로를 URL로 변환
        s3_url = format_s3_url(s3_path)
        
        # 디렉토리 내용 확인
        dir_contents = await analysis_service.s3_service.list_bucket_contents(s3_url, max_keys=50)
        
        return {
            "s3_path": s3_path,
            "s3_url": s3_url,
            "directory_contents": dir_contents
        }
        
    except Exception as e:
        logger.error(f"S3 디렉토리 리스팅 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"디렉토리 리스팅 중 오류: {str(e)}")

@router.post("/analysis", response_model=AnalysisResponse)
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

@router.post("/analysis/voice-only", response_model=AnalysisResponse)
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

@router.post("/analysis/communication", response_model=CommunicationAnalysisResponse)
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
        s3_audio_url = format_s3_url(request.s3ObjectKey)
        logger.info(f"S3 URL 변환 완료: {s3_audio_url}")
        
        # S3 Object Key에서 user_id와 question_num 추출 시도
        user_id, question_num = extract_user_info_from_s3_key(request.s3ObjectKey)
        
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