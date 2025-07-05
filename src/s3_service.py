# ----------------------------------------------------------------------------------------------------
# 작성목적 : S3 파일 다운로드 서비스
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | S3 파일 다운로드 서비스 | 이재인
# 2025-12-19 | 디버깅 개선 | S3 파일 존재 확인 및 상세 로깅 기능 추가 | 구동빈
# ----------------------------------------------------------------------------------------------------

import os
import boto3
from botocore.exceptions import ClientError
import logging
from urllib.parse import urlparse
import aiofiles
import httpx
import unicodedata

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

    async def check_file_exists(self, s3_url: str) -> dict:
        """
        S3 파일 존재 여부 확인
        
        Args:
            s3_url: S3 파일 URL (s3://bucket/key)
            
        Returns:
            dict: 파일 정보 또는 에러 정보
        """
        try:
            if not self.s3_client:
                return {"exists": False, "error": "S3 클라이언트가 초기화되지 않았습니다."}
            
            parsed = urlparse(s3_url)
            if parsed.scheme != 's3':
                return {"exists": False, "error": "유효하지 않은 S3 URL입니다."}
            
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
            
            logger.info(f"S3 파일 존재 확인: bucket={bucket}, key={key}")
            
            # 한글 파일명 처리를 위해 list_objects_v2로 검색
            response = self.s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=key,
                MaxKeys=1
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'] == key:  # 정확히 일치하는 파일 찾기
                        return {
                            "exists": True,
                            "size": obj['Size'],
                            "last_modified": obj['LastModified'],
                            "content_type": obj.get('ContentType', 'unknown')
                        }
            
            return {"exists": False, "error": "파일이 존재하지 않습니다."}
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            return {"exists": False, "error": f"S3 에러 ({error_code}): {str(e)}"}
        except Exception as e:
            return {"exists": False, "error": f"예상치 못한 에러: {str(e)}"}

    async def list_bucket_contents(self, s3_url: str, max_keys: int = 10) -> dict:
        """
        S3 버킷의 지정된 경로 내용 리스팅
        
        Args:
            s3_url: S3 경로 URL
            max_keys: 최대 반환할 키 개수
            
        Returns:
            dict: 파일 목록 또는 에러 정보
        """
        try:
            if not self.s3_client:
                return {"success": False, "error": "S3 클라이언트가 초기화되지 않았습니다."}
            
            parsed = urlparse(s3_url)
            bucket = parsed.netloc
            prefix = parsed.path.lstrip('/')
            
            # 디렉토리인 경우 마지막에 /를 붙임
            if prefix and not prefix.endswith('/'):
                prefix = prefix + '/'
            
            logger.info(f"S3 버킷 내용 리스팅: bucket={bucket}, prefix={prefix}")
            
            response = self.s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat()
                    })
            
            return {
                "success": True,
                "bucket": bucket,
                "prefix": prefix,
                "file_count": len(files),
                "files": files
            }
            
        except ClientError as e:
            return {"success": False, "error": f"S3 에러: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"예상치 못한 에러: {str(e)}"}
    
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
                # s3://bucket/key 형식 - 정확한 키 찾기 시도
                return await self._download_from_s3_path_with_search(s3_url, local_dir)
            elif parsed_url.scheme in ['http', 'https']:
                # HTTP(S) URL 형식
                return await self._download_from_http_url(s3_url, local_dir)
            else:
                raise ValueError(f"지원하지 않는 URL 형식: {s3_url}")
                
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {str(e)}")
            
            # 디버깅을 위해 상위 디렉토리 내용 확인
            try:
                parsed = urlparse(s3_url)
                parent_path = '/'.join(parsed.path.split('/')[:-1])
                parent_url = f"s3://{parsed.netloc}{parent_path}"
                
                logger.info(f"상위 디렉토리 내용 확인: {parent_url}")
                dir_contents = await self.list_bucket_contents(parent_url)
                if dir_contents.get('success'):
                    logger.info(f"상위 디렉토리 파일 목록: {dir_contents}")
            except Exception as debug_e:
                logger.warning(f"디버깅 정보 수집 실패: {debug_e}")
            
            raise
    
    async def _download_from_s3_path_with_search(self, s3_url: str, local_dir: str) -> str:
        """s3://bucket/key 형식의 URL에서 다운로드 (키 검색 포함)"""
        if not self.s3_client:
            raise ValueError("S3 클라이언트가 초기화되지 않았습니다.")
        
        # s3://bucket/key에서 bucket과 key 추출
        parsed = urlparse(s3_url)
        bucket = parsed.netloc
        original_key = parsed.path.lstrip('/')
        
        # 먼저 원본 키로 시도
        try:
            return await self._download_with_key(bucket, original_key, local_dir)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['NoSuchKey', '404']:
                logger.info(f"원본 키로 다운로드 실패, 정확한 키 검색 중: {original_key}")
                
                # 상위 디렉토리에서 일치하는 파일 검색
                parent_path = '/'.join(original_key.split('/')[:-1])
                target_filename = os.path.basename(original_key)
                
                try:
                    # 디렉토리 리스팅
                    response = self.s3_client.list_objects_v2(
                        Bucket=bucket,
                        Prefix=parent_path + '/' if parent_path else '',
                        MaxKeys=100
                    )
                    
                    if 'Contents' in response:
                        # 유니코드 정규화를 통한 파일명 매칭
                        target_normalized_nfc = unicodedata.normalize('NFC', target_filename)
                        target_normalized_nfd = unicodedata.normalize('NFD', target_filename)
                        
                        logger.info(f"파일명 검색: {target_filename}")
                        logger.info(f"  NFC 정규화: {target_normalized_nfc}")
                        logger.info(f"  NFD 정규화: {target_normalized_nfd}")
                        
                        for obj in response['Contents']:
                            obj_filename = os.path.basename(obj['Key'])
                            if not obj_filename:  # 디렉토리인 경우 건너뛰기
                                continue
                                
                            # 다양한 정규화 형태로 비교
                            obj_normalized_nfc = unicodedata.normalize('NFC', obj_filename)
                            obj_normalized_nfd = unicodedata.normalize('NFD', obj_filename)
                            
                            logger.info(f"S3 파일: {obj_filename}")
                            logger.info(f"  NFC: {obj_normalized_nfc}")
                            logger.info(f"  NFD: {obj_normalized_nfd}")
                            
                            # 정규화된 형태로 매칭 시도
                            if (obj_filename == target_filename or
                                obj_normalized_nfc == target_normalized_nfc or
                                obj_normalized_nfd == target_normalized_nfd or
                                obj_normalized_nfc == target_normalized_nfd or
                                obj_normalized_nfd == target_normalized_nfc):
                                
                                logger.info(f"✅ 매칭된 파일 발견: {obj['Key']}")
                                return await self._download_with_key(bucket, obj['Key'], local_dir)
                    
                    # 여전히 찾지 못한 경우
                    logger.error(f"파일을 찾을 수 없습니다: {target_filename}")
                    logger.info(f"디렉토리 {parent_path}의 파일 목록:")
                    if 'Contents' in response:
                        for obj in response['Contents']:
                            logger.info(f"  - {obj['Key']} (크기: {obj['Size']})")
                    
                    raise FileNotFoundError(f"파일을 찾을 수 없습니다: {target_filename}")
                    
                except Exception as search_e:
                    logger.error(f"키 검색 중 오류: {search_e}")
                    raise
            else:
                raise

    async def _download_with_key(self, bucket: str, key: str, local_dir: str) -> str:
        """지정된 버킷과 키로 파일 다운로드"""
        filename = os.path.basename(key)
        if not filename:
            filename = "audio_file"
        
        local_path = os.path.join(local_dir, filename)
        
        logger.info(f"S3에서 파일 다운로드 중: bucket={bucket}, key={key}, local_path={local_path}")
        
        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        
        # 파일 저장
        with open(local_path, 'wb') as f:
            f.write(response['Body'].read())
        
            logger.info(f"S3에서 파일 다운로드 완료: {local_path}")
            return local_path
            
    async def _download_from_s3_path(self, s3_url: str, local_dir: str) -> str:
        """s3://bucket/key 형식의 URL에서 다운로드 (레거시)"""
        # 새로운 검색 기능이 있는 메소드로 리디렉션
        return await self._download_from_s3_path_with_search(s3_url, local_dir)
    
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