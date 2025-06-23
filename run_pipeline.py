#!/usr/bin/env python3
"""
한국어 음성 분석 파이프라인
S3 → 변환 → 분석 → STT → GPT → DB 저장 전체 워크플로우 실행

사용법:
    python run_pipeline.py --mode s3_scan     # S3 버킷 전체 스캔
    python run_pipeline.py --mode single_file --url "s3://bucket/file.webm" --user_id "user123" --question_num 1
"""

import asyncio
import logging
import argparse
import os
import sys
import time
from typing import List, Dict, Any, Tuple
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
import re

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

# 서비스 임포트
from src.korean_analysis_service import KoreanAnalysisService

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pipeline.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class S3FileScanner:
    """S3 버킷에서 오디오 파일을 스캔하고 분석 대상 목록을 생성"""
    
    def __init__(self):
        self.s3_client = None
        self._initialize_s3_client()
        
    def _initialize_s3_client(self):
        """S3 클라이언트 초기화"""
        try:
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_REGION', 'ap-northeast-2')
            
            if aws_access_key and aws_secret_key:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
                logger.info("S3 클라이언트 초기화 완료")
            else:
                logger.error("AWS 자격 증명이 없습니다. .env 파일을 확인하세요.")
                
        except Exception as e:
            logger.error(f"S3 클라이언트 초기화 실패: {str(e)}")
    
    def scan_audio_files(self, bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        """
        S3 버킷에서 오디오 파일 스캔
        
        Args:
            bucket_name: S3 버킷 이름
            prefix: 스캔할 경로 prefix
            
        Returns:
            List[Dict]: 분석 대상 파일 목록
        """
        try:
            if not self.s3_client:
                raise ValueError("S3 클라이언트가 초기화되지 않았습니다.")
            
            logger.info(f"S3 버킷 스캔 시작: s3://{bucket_name}/{prefix}")
            
            # 지원하는 오디오 파일 확장자
            audio_extensions = {'.webm', '.mp3', '.mp4', '.m4a', '.wav', '.ogg'}
            
            analysis_targets = []
            
            # S3 객체 목록 가져오기
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            total_files = 0
            audio_files = 0
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    total_files += 1
                    file_key = obj['Key']
                    file_size = obj['Size']
                    
                    # 파일 확장자 확인
                    file_ext = os.path.splitext(file_key)[1].lower()
                    if file_ext not in audio_extensions:
                        continue
                    
                    audio_files += 1
                    
                    # 파일명에서 user_id, question_num 추출 시도
                    user_id, question_num = self._extract_user_info_from_filename(file_key)
                    
                    if user_id and question_num is not None:
                        s3_url = f"s3://{bucket_name}/{file_key}"
                        analysis_targets.append({
                            'user_id': user_id,
                            'question_num': question_num,
                            's3_url': s3_url,
                            'file_size': file_size,
                            'file_key': file_key
                        })
                        logger.info(f"  분석 대상 추가: {user_id} - 질문{question_num} ({file_ext})")
                    else:
                        logger.warning(f"  파일명에서 사용자 정보 추출 실패: {file_key}")
            
            logger.info(f"스캔 완료: 총 {total_files}개 파일 중 오디오 {audio_files}개, 분석 대상 {len(analysis_targets)}개")
            return analysis_targets
            
        except ClientError as e:
            logger.error(f"S3 스캔 실패: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"파일 스캔 중 오류: {str(e)}")
            return []
    
    def _extract_user_info_from_filename(self, file_key: str) -> Tuple[str, int]:
        """
        S3 경로에서 user_id와 question_num 추출
        
        예상 경로 구조: team12/interview_audio/{userId}/{question_num}/{파일명}
        
        Returns:
            Tuple[str, int]: (user_id, question_num) 또는 (None, None)
        """
        try:
            # 경로를 슬래시로 분할
            path_parts = file_key.split('/')
            
            # team12/interview_audio/{userId}/{question_num}/{파일명} 구조 확인
            if len(path_parts) >= 5:
                # 예: ['team12', 'interview_audio', 'userId', 'question_num', 'filename.webm']
                if path_parts[0] == 'team12' and path_parts[1] == 'interview_audio':
                    user_id = path_parts[2]
                    question_num_str = path_parts[3]
                    
                    # question_num이 숫자인지 확인
                    if question_num_str.isdigit():
                        return user_id, int(question_num_str)
                    
                    # question_num에서 숫자 추출 시도 (예: "question1", "q1" 등)
                    question_match = re.search(r'([0-9]+)', question_num_str)
                    if question_match:
                        return user_id, int(question_match.group(1))
            
            # 기존 패턴들도 시도
            filename = os.path.basename(file_key)
            filename_no_ext = os.path.splitext(filename)[0]
            
            # 패턴 1: user{id}_question{num} 또는 user{id}_q{num}
            pattern1 = r'user([a-zA-Z0-9_-]+)_(?:question|q)([0-9]+)'
            match1 = re.search(pattern1, filename_no_ext, re.IGNORECASE)
            if match1:
                return match1.group(1), int(match1.group(2))
            
            # 패턴 2: {user_id}_question{num} (user 접두사 없이)
            pattern2 = r'([a-zA-Z0-9_-]+)_(?:question|q)([0-9]+)'
            match2 = re.search(pattern2, filename_no_ext, re.IGNORECASE)
            if match2:
                return match2.group(1), int(match2.group(2))
            
            # 일반적인 디렉토리 구조에서 추출 시도
            if len(path_parts) >= 2:
                potential_user = path_parts[-2]
                potential_question = re.search(r'([0-9]+)', path_parts[-1])
                if potential_question and potential_user:
                    return potential_user, int(potential_question.group(1))
            
            logger.warning(f"경로에서 사용자 정보 추출 실패: {file_key}")
            return None, None
            
        except Exception as e:
            logger.debug(f"경로 파싱 오류: {file_key} - {str(e)}")
            return None, None

class KoreanAnalysisPipeline:
    """한국어 음성 분석 파이프라인 관리"""
    
    def __init__(self):
        self.service = KoreanAnalysisService()
        self.scanner = S3FileScanner()
        
    async def initialize(self):
        """파이프라인 초기화"""
        logger.info("한국어 음성 분석 파이프라인 초기화 중...")
        await self.service.initialize()
        logger.info("파이프라인 초기화 완료")
        
    async def cleanup(self):
        """파이프라인 정리"""
        await self.service.cleanup()
        logger.info("파이프라인 정리 완료")
        
    async def run_s3_scan_mode(self, bucket_name: str, prefix: str = "", gender: str = "female"):
        """S3 스캔 모드 실행"""
        try:
            # S3 파일 스캔
            analysis_targets = self.scanner.scan_audio_files(bucket_name, prefix)
            
            if not analysis_targets:
                logger.warning("분석할 파일이 없습니다.")
                return
            
            # 질문 8번, 9번 필터링 (1~7번만 분석)
            filtered_targets = [
                target for target in analysis_targets 
                if target['question_num'] <= 7
            ]
            
            excluded_count = len(analysis_targets) - len(filtered_targets)
            if excluded_count > 0:
                logger.info(f"질문 8번, 9번 파일 {excluded_count}개 제외됨 (1~7번만 분석)")
            
            if not filtered_targets:
                logger.warning("분석할 파일이 없습니다 (질문 1~7번만 분석 대상).")
                return
            
            logger.info(f"\n{'='*60}")
            logger.info(f"총 {len(filtered_targets)}개 파일 분석 시작 (질문 1~7번)")
            logger.info(f"{'='*60}")
            
            # 통계 변수
            success_count = 0
            error_count = 0
            total_score_sum = 0
            start_time = time.time()
            
            # 각 파일 분석 실행
            for i, target in enumerate(filtered_targets, 1):
                logger.info(f"\n[{i}/{len(filtered_targets)}] 분석 진행 중...")
                logger.info(f"사용자: {target['user_id']}")
                logger.info(f"질문: {target['question_num']}")
                logger.info(f"파일: {target['file_key']}")
                logger.info(f"크기: {target['file_size']:,} bytes")
                
                try:
                    result = await self.service.analyze_complete_workflow(
                        user_id=target['user_id'],
                        question_num=target['question_num'],
                        s3_audio_url=target['s3_url'],
                        gender=gender
                    )
                    
                    success_count += 1
                    total_score_sum += result['total_score']
                    
                    logger.info(f"[{i}/{len(filtered_targets)}] 분석 완료 - 점수: {result['total_score']}점")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"[{i}/{len(filtered_targets)}] 분석 실패: {str(e)}")
                    
                # 진행률 표시
                progress = (i / len(filtered_targets)) * 100
                logger.info(f"전체 진행률: {progress:.1f}% ({i}/{len(filtered_targets)})")
            
            # 최종 통계 출력
            await self._print_final_statistics(
                total_files=len(filtered_targets),
                success_count=success_count,
                error_count=error_count,
                total_score_sum=total_score_sum,
                elapsed_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"S3 스캔 모드 실행 실패: {str(e)}")
            raise
    
    async def run_single_file_mode(self, user_id: str, question_num: int, s3_url: str, gender: str = "female"):
        """단일 파일 분석 모드"""
        try:
            # 질문 8번, 9번 필터링
            if question_num > 7:
                logger.warning(f"질문 {question_num}번은 분석하지 않습니다 (1~7번만 분석 대상)")
                return
            
            logger.info(f"\n{'='*60}")
            logger.info(f"단일 파일 분석 시작")
            logger.info(f"사용자: {user_id}")
            logger.info(f"질문: {question_num}")
            logger.info(f"파일: {s3_url}")
            logger.info(f"{'='*60}")
            
            start_time = time.time()
            
            result = await self.service.analyze_complete_workflow(
                user_id=user_id,
                question_num=question_num,
                s3_audio_url=s3_url,
                gender=gender
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info(f"\n{'='*60}")
            logger.info(f"단일 파일 분석 완료!")
            logger.info(f"최종 점수: {result['total_score']}점/100점")
            logger.info(f"음성 점수: {result['voice_score']}점/40점")
            logger.info(f"텍스트 점수: {result['text_score']}점/60점")
            logger.info(f"소요 시간: {elapsed_time:.1f}초")
            logger.info(f"{'='*60}")
            
        except Exception as e:
            logger.error(f"단일 파일 분석 실패: {str(e)}")
            raise
    
    async def _print_final_statistics(self, total_files: int, success_count: int, error_count: int, 
                                    total_score_sum: float, elapsed_time: float):
        """최종 통계 정보 출력"""
        logger.info(f"\n{'='*20} 분석 완료 {'='*20}")
        logger.info(f"최종 통계:")
        logger.info(f"  총 파일 수: {total_files}개")
        logger.info(f"  성공: {success_count}개")
        logger.info(f"  실패: {error_count}개")
        logger.info(f"  성공률: {(success_count/total_files*100):.1f}%")
        
        if success_count > 0:
            avg_score = total_score_sum / success_count
            logger.info(f"  평균 점수: {avg_score:.1f}점/100점")
        
        logger.info(f"  총 소요 시간: {elapsed_time:.1f}초")
        logger.info(f"  파일당 평균 시간: {elapsed_time/total_files:.1f}초")
        logger.info(f"{'='*50}")

async def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="한국어 음성 분석 파이프라인")
    parser.add_argument('--mode', choices=['s3_scan', 'single_file'], default='s3_scan',
                       help="실행 모드: s3_scan (S3 버킷 전체 스캔) 또는 single_file (단일 파일) (기본값: s3_scan)")
    parser.add_argument('--bucket', default='skala25a', help="S3 버킷 이름 (기본값: skala25a)")
    parser.add_argument('--prefix', default='team12/interview_audio', help="S3 스캔 경로 prefix (기본값: team12/interview_audio)")
    parser.add_argument('--url', help="S3 파일 URL (single_file 모드용)")
    parser.add_argument('--user_id', default='e4983d22-be0d-47f4-8394-60eb2d5073bf', help="사용자 ID (기본값: e4983d22-be0d-47f4-8394-60eb2d5073bf)")
    parser.add_argument('--question_num', type=int, help="질문 번호 (single_file 모드용)")
    parser.add_argument('--gender', choices=['male', 'female'], default='female', help="성별 (기본값: female)")
    
    args = parser.parse_args()
    
    # 환경변수 확인
    required_env_vars = [
        'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
        'MONGODB_URI', 'MARIADB_HOST', 'MARIADB_USER', 'MARIADB_PASSWORD',
        'OPENAI_API_KEY'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"필수 환경변수가 없습니다: {', '.join(missing_vars)}")
        logger.error(".env 파일을 확인하거나 환경변수를 설정하세요.")
        return
    
    # 파이프라인 실행
    pipeline = KoreanAnalysisPipeline()
    
    try:
        await pipeline.initialize()
        
        if args.mode == 's3_scan':            
            await pipeline.run_s3_scan_mode(
                bucket_name=args.bucket,
                prefix=args.prefix,
                gender=args.gender
            )
            
        elif args.mode == 'single_file':
            if not all([args.url, args.user_id, args.question_num]):
                logger.error("single_file 모드에는 --url, --user_id, --question_num 옵션이 모두 필요합니다.")
                return
            
            await pipeline.run_single_file_mode(
                user_id=args.user_id,
                question_num=args.question_num,
                s3_url=args.url,
                gender=args.gender
            )
    
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"파이프라인 실행 중 오류: {str(e)}")
    finally:
        await pipeline.cleanup()

if __name__ == "__main__":
    # Python 3.7+ asyncio 호환성
    if sys.version_info >= (3, 7):
        asyncio.run(main())
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main()) 