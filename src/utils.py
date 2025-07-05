# ----------------------------------------------------------------------------------------------------
# 작성목적 : 유틸리티 함수 모음. 공통으로 사용되는 헬퍼 함수들을 정의합니다.
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 2025-06-25 | 최초 구현 | S3 경로 파싱 등 유틸리티 함수 분리 | 이주형
# 2025-07-03 | 버그 수정 | S3 버킷명을 환경변수로 관리하여 404 오류 해결 | 구동빈
# ----------------------------------------------------------------------------------------------------

import os
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def extract_user_info_from_s3_key(s3_object_key: str) -> Tuple[Optional[str], Optional[int]]:
    """
    S3 Object Key에서 user_id와 question_num 추출
    
    예상 경로 패턴:
    - team12/interview_video/{user_id}/{question_id}/{파일명}
    - team12/interview_audio/{user_id}/{question_id}/{파일명}
    - bucket-name/path/{user_id}/{question_id}/file.webm
    
    Args:
        s3_object_key: S3 Object Key 또는 URL
        
    Returns:
        tuple: (user_id, question_num) 또는 (None, None)
    """
    try:
        # S3 URL 프리픽스 제거
        clean_key = s3_object_key.replace('s3://', '')
        if '/' in clean_key:
            # 첫 번째 '/' 이후 부분만 사용 (버킷명 제거)
            parts = clean_key.split('/', 1)
            if len(parts) > 1:
                clean_key = parts[1]
        
        path_parts = clean_key.split('/')
        logger.debug(f"S3 경로 파싱: {s3_object_key} -> {path_parts}")
        
        # 패턴 1: team12/interview_video/{user_id}/{question_id}/{파일명}
        # 패턴 2: team12/interview_audio/{user_id}/{question_id}/{파일명}
        if len(path_parts) >= 4:
            for interview_type in ['interview_video', 'interview_audio']:
                if interview_type in path_parts:
                    interview_idx = path_parts.index(interview_type)
                    if interview_idx + 2 < len(path_parts):
                        user_id = path_parts[interview_idx + 1]
                        question_id = path_parts[interview_idx + 2]
                        
                        # user_id와 question_id가 숫자인지 확인
                        try:
                            question_num = int(question_id)
                            logger.info(f"S3 경로에서 추출 성공: user_id={user_id}, question_num={question_num}")
                            return user_id, question_num
                        except ValueError:
                            logger.warning(f"question_id가 숫자가 아님: {question_id}")
                            continue
        
        # 패턴 3: 파일명에서 추출
        filename = path_parts[-1] if path_parts else s3_object_key
        filename_no_ext = filename.rsplit('.', 1)[0]
        
        # user{id}_question{num} 패턴
        pattern = r'user([a-zA-Z0-9_-]+)_(?:question|q)([0-9]+)'
        match = re.search(pattern, filename_no_ext, re.IGNORECASE)
        if match:
            logger.info(f"파일명에서 추출 성공 (패턴1): user_id={match.group(1)}, question_num={int(match.group(2))}")
            return match.group(1), int(match.group(2))
        
        # 단순 {userid}_{questionnum} 패턴  
        simple_pattern = r'([a-zA-Z0-9_-]+)_([0-9]+)'
        simple_match = re.search(simple_pattern, filename_no_ext)
        if simple_match:
            logger.info(f"파일명에서 추출 성공 (패턴2): user_id={simple_match.group(1)}, question_num={int(simple_match.group(2))}")
            return simple_match.group(1), int(simple_match.group(2))
            
        logger.warning(f"S3 경로에서 사용자 정보 추출 실패: {s3_object_key}")
        return None, None
        
    except Exception as e:
        logger.error(f"S3 경로 파싱 오류: {s3_object_key} - {str(e)}")
        return None, None

def format_s3_url(s3_object_key: str) -> str:
    """
    S3 Object Key를 URL 형태로 변환
    버킷명은 .env의 S3_BUCKET_NAME 환경변수에서 가져옴
    
    Args:
        s3_object_key: S3 Object Key (버킷명 제외한 경로)
        
    Returns:
        str: s3://{bucket_name}/{object_key} 형태의 URL
    """
    # 환경변수에서 버킷명 가져오기
    bucket_name = os.getenv('S3_BUCKET_NAME', 'skala25a')  # 기본값은 skala25a
    
    # 이미 완전한 S3 URL인 경우 그대로 반환
    if s3_object_key.startswith('s3://'):
        return s3_object_key
    
    # 버킷명이 이미 포함된 경우 제거
    if s3_object_key.startswith(f'{bucket_name}/'):
        s3_object_key = s3_object_key[len(bucket_name)+1:]  # '{bucket_name}/' 제거
    
    # 환경변수 버킷명과 함께 S3 URL 생성
    return f"s3://{bucket_name}/{s3_object_key}"