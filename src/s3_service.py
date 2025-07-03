# ----------------------------------------------------------------------------------------------------
# 작성목적 : S3 파일 다운로드 서비스
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | S3 파일 다운로드 서비스 | 이재인
# ----------------------------------------------------------------------------------------------------

import os
import boto3
from botocore.exceptions import ClientError
import logging
from urllib.parse import urlparse
import aiofiles
import httpx

logger = logging.getLogger(__name__)

class S3Service:
    """S3 파일 다운로드 서비스"""
    
    def __init__(self):
        # AWS 자격 증명은 환경변수에서 가져옴
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'ap-northeast-2')
        
        # S3 클라이언트 초기화
        self.s3_client = None
        self._initialize_s3_client()
    
    def _initialize_s3_client(self):
        """S3 클라이언트 초기화"""
        try:
            if self.aws_access_key and self.aws_secret_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.aws_region
                )
                logger.info("S3 클라이언트 초기화 완료")
            else:
                logger.warning("S3 자격 증명이 없습니다. 직접 URL 다운로드를 사용합니다.")
        except Exception as e:
            logger.error(f"S3 클라이언트 초기화 실패: {str(e)}")
    
    async def download_file(self, s3_url: str, local_dir: str) -> str:
        """
        S3 URL에서 파일을 다운로드
        
        Args:
            s3_url: S3 파일 URL (s3://bucket/key 또는 https URL)
            local_dir: 로컬 저장 디렉토리
            
        Returns:
            str: 다운로드된 파일의 로컬 경로
        """
        try:
            logger.info(f"S3 파일 다운로드 시작: {s3_url}")
            
            # URL 파싱
            parsed_url = urlparse(s3_url)
            
            if parsed_url.scheme == 's3':
                # s3://bucket/key 형식
                return await self._download_from_s3_path(s3_url, local_dir)
            elif parsed_url.scheme in ['http', 'https']:
                # HTTP(S) URL 형식
                return await self._download_from_http_url(s3_url, local_dir)
            else:
                raise ValueError(f"지원하지 않는 URL 형식: {s3_url}")
                
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {str(e)}")
            raise
    
    async def _download_from_s3_path(self, s3_url: str, local_dir: str) -> str:
        """s3://bucket/key 형식의 URL에서 다운로드"""
        if not self.s3_client:
            raise ValueError("S3 클라이언트가 초기화되지 않았습니다.")
        
        # s3://bucket/key에서 bucket과 key 추출
        parsed = urlparse(s3_url)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        
        # 파일명 추출
        filename = os.path.basename(key)
        if not filename:
            filename = "audio_file"
        
        local_path = os.path.join(local_dir, filename)
        
        try:
            # S3에서 파일 다운로드
            self.s3_client.download_file(bucket, key, local_path)
            logger.info(f"S3에서 파일 다운로드 완료: {local_path}")
            return local_path
            
        except ClientError as e:
            logger.error(f"S3 다운로드 실패: {str(e)}")
            raise
    
    async def _download_from_http_url(self, url: str, local_dir: str) -> str:
        """HTTP(S) URL에서 파일 다운로드"""
        try:
            # URL에서 파일명 추출
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename or '.' not in filename:
                filename = "audio_file.webm"  # 기본 확장자
            
            local_path = os.path.join(local_dir, filename)
            
            # HTTP 클라이언트로 파일 다운로드
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # 파일 저장
                async with aiofiles.open(local_path, 'wb') as f:
                    await f.write(response.content)
            
            logger.info(f"HTTP URL에서 파일 다운로드 완료: {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"HTTP 다운로드 실패: {str(e)}")
            raise
    
    def get_file_info(self, s3_url: str) -> dict:
        """S3 파일 정보 조회"""
        try:
            if not self.s3_client:
                return {"error": "S3 클라이언트가 초기화되지 않았습니다."}
            
            parsed = urlparse(s3_url)
            if parsed.scheme != 's3':
                return {"error": "S3 URL이 아닙니다."}
            
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
            
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            
            return {
                "size": response.get('ContentLength'),
                "last_modified": response.get('LastModified'),
                "content_type": response.get('ContentType')
            }
            
        except ClientError as e:
            logger.error(f"S3 파일 정보 조회 실패: {str(e)}")
            return {"error": str(e)} 