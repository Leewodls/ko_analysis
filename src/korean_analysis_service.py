"""
한국어 음성 분석 메인 서비스
S3 → 변환 → 분석 → STT → GPT → DB 저장 전체 워크플로우 관리
"""

import os
import json
import tempfile
import logging
from typing import Dict, Any, Optional
import asyncio

from .s3_service import S3Service
from .audio_converter import AudioConverter
from .whisper_service import WhisperService
from .gpt_evaluator import GPTEvaluator
from .mongodb_service import MongoDBService
from .mariadb_service import MariaDBService
from .category_evaluator import CategoryEvaluator
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import comprehensive_audio_analysis

logger = logging.getLogger(__name__)

class KoreanAnalysisService:
    """한국어 음성 분석 메인 서비스"""
    
    def __init__(self):
        self.s3_service = S3Service()
        self.audio_converter = AudioConverter()
        self.whisper_service = WhisperService()
        self.gpt_evaluator = GPTEvaluator()
        self.mongodb_service = MongoDBService()
        self.mariadb_service = MariaDBService()
        self.category_evaluator = CategoryEvaluator()  # 새로운 카테고리 평가자 추가
        self.temp_dir = None
        
    async def initialize(self):
        """서비스 초기화"""
        try:
            logger.info("서비스 초기화 시작...")
            
            # MongoDB 연결
            await self.mongodb_service.connect()
            
            # MariaDB 연결  
            await self.mariadb_service.connect()
            
            # 임시 디렉토리 생성
            self.temp_dir = tempfile.mkdtemp(prefix="korean_analysis_")
            
            logger.info("서비스 초기화 완료")
            
        except Exception as e:
            logger.error(f"서비스 초기화 실패: {str(e)}")
            raise

    async def cleanup(self):
        """리소스 정리"""
        try:
            # MongoDB 연결 해제
            await self.mongodb_service.disconnect()
            
            # MariaDB 연결 해제
            await self.mariadb_service.disconnect()
            
            # 임시 디렉토리 정리
            if self.temp_dir and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
                
            logger.info("리소스 정리 완료")
            
        except Exception as e:
            logger.error(f"리소스 정리 중 오류: {str(e)}")

    async def analyze_complete_workflow(
        self,
        user_id: str,
        question_num: int,
        s3_audio_url: str,
        gender: str = "female"
    ) -> Dict[str, Any]:
        """
        전체 분석 워크플로우 실행 (새로운 카테고리별 평가 포함)
        S3 → 변환 → 음성분석 → STT → 카테고리별 GPT평가 → DB저장
        """
        logger.info(f"전체 워크플로우 시작: {user_id}, 질문{question_num}")
        
        original_file_path = None
        wav_file_path = None
        
        try:
            # 1. S3에서 음성 파일 다운로드
            logger.info("\n1단계: S3에서 음성 파일 다운로드 중...")
            original_file_path = await self.s3_service.download_file(
                s3_audio_url, 
                self.temp_dir
            )
            logger.info(f"  S3 다운로드 완료: {os.path.basename(original_file_path)}")
            
            # 2. WebM → WAV 변환
            logger.info("\n2단계: 음성 파일 변환 중 (webm → wav)...")
            wav_file_path = await self.audio_converter.convert_to_wav(
                original_file_path,
                self.temp_dir
            )
            logger.info(f"  음성 변환 완료: {os.path.basename(wav_file_path)}")
            
            # 3. 한국어 음성 분석 (휴지, 속도)
            logger.info("\n3단계: 한국어 음성 분석 중 (휴지/속도)...")
            ko_analysis_result = await self._analyze_korean_voice(
                wav_file_path, 
                gender
            )
            ko_score = ko_analysis_result['scores_result']['total_score']
            
            # 세부 점수 정보 출력
            scores = ko_analysis_result['scores_result']
            individual_scores = scores.get('individual_scores', {})
            logger.info(f"  한국어 음성 분석 완료: {ko_score:.1f}점/40점")
            logger.info(f"    세부 점수:")
            logger.info(f"      - 휴지 점수: {individual_scores.get('pause_score', 0):.1f}점/20점")
            logger.info(f"      - 속도 점수: {individual_scores.get('speech_rate_score', 0):.1f}점/20점")
            logger.info(f"    세부 데이터:")
            logger.info(f"      - 휴지 비율: {ko_analysis_result['pause_analysis_result']['pause_ratio']:.2f}%")
            logger.info(f"      - 평균 발화속도: {ko_analysis_result['summary']['avg_speech_rate']:.2f} 음절/초")
            
            # 4. Whisper STT 변환
            logger.info("\n4단계: Whisper STT 변환 중...")
            transcript = self.whisper_service.transcribe(wav_file_path)
            logger.info(f"  STT 변환 완료: {len(transcript)}자 텍스트 생성")
            if len(transcript) > 50:
                logger.info(f"  변환된 텍스트 미리보기: {transcript[:50]}...")
            else:
                logger.info(f"  변환된 텍스트: {transcript}")
            
            # 5. 의사소통 능력 점수 계산 (YAML 프롬프트 사용)
            logger.info("\n5단계: 의사소통 능력 점수 계산 중...")
            # 새로운 카테고리 평가자로 의사소통 능력 평가
            communication_result = await self.category_evaluator._evaluate_single_category(
                transcript, 'COMMUNICATION', question_num
            )
            text_communication_score = communication_result.get('total_text_score', 
                                                               communication_result.get('score', 60) * 0.6)  # 기본값 처리
            
            # 최종 의사소통 능력 점수 = 음성 점수(40) + 텍스트 점수(60) = 100점 만점으로 스케일링
            communication_score = ko_score + text_communication_score  # 100점 만점
            logger.info(f"  의사소통 능력 계산 완료: {communication_score:.1f}점/100점")
            logger.info(f"    - 음성 분석: {ko_score:.1f}점/40점")
            logger.info(f"    - 텍스트 분석: {text_communication_score}점/60점")
            
            # 6. 카테고리별 평가 (새로운 방식)
            logger.info(f"\n6단계: 질문 {question_num}번 카테고리별 평가 중...")
            category_results = await self.category_evaluator.evaluate_categories_for_question(
                stt_text=transcript,
                question_num=question_num,
                communication_score=communication_score
            )
            
            # 카테고리별 결과 출력
            for category, result in category_results.items():
                category_name = self.category_evaluator._get_category_name(category)
                logger.info(f"    - {category_name}: {result['score']:.1f}점")
                logger.info(f"      강점: {result['strength_keyword']}")
                logger.info(f"      약점: {result['weakness_keyword']}")
            
            # 7. 기존 방식으로 의사소통 점수에 텍스트 점수 반영
            logger.info("\n7단계: 의사소통 최종 점수 계산 중...")
            total_voice_score = ko_score
            total_text_score = text_communication_score
            communication_score = total_voice_score + total_text_score
            
            # 8. MongoDB에 기존 방식대로 저장 (속도, 휴지, 의사소통능력 점수)
            logger.info("\n8단계: MongoDB에 한국어 분석 결과 저장 중...")
            
            # text_scores를 communication_result에서 가져오기
            text_scores = {
                'total_text_score': text_communication_score,
                'detailed_scores': communication_result.get('detailed_scores', {}),
                'feedback': communication_result.get('feedback', {})
            }
            
            await self._save_scores_to_mongodb(
                user_id=user_id, 
                question_num=question_num, 
                total_score=communication_score,  # 의사소통 능력 점수만 저장
                ko_score=ko_score,
                text_score=text_communication_score,
                ko_scores=ko_analysis_result['scores_result'],
                text_scores=text_scores,
                stt_text=transcript,
                file_path=s3_audio_url
            )
            logger.info("  MongoDB 저장 완료")
            
            # 9. 새로운 테이블에 카테고리별 평가 저장
            logger.info("\n9단계: MariaDB에 카테고리별 평가 저장 중...")
            
            # 답변 요약 생성
            answer_summary = await self.category_evaluator.generate_answer_summary(transcript)
            
            success = await self.mariadb_service.save_answer_evaluation(
                user_id=user_id,
                question_num=question_num,
                answer_summary=answer_summary,
                category_results=category_results
            )
            
            if success:
                logger.info("  MariaDB 카테고리별 평가 저장 완료")
            else:
                logger.error("  MariaDB 저장 실패")
            
            # 9.1. 직무적합도 카테고리에서 전체 11개 세부 항목 추출 및 저장
            logger.info("\n9.1단계: 직무적합도 세부 항목 점수 저장 중...")
            try:
                job_compatibility_result = category_results.get('JOB_COMPATIBILITY', {})
                detailed_scores = job_compatibility_result.get('detailed_scores', {})
                
                if detailed_scores:
                    # 새로운 메소드로 전체 세부 항목 저장
                    detailed_success = await self.mongodb_service.save_job_compatibility_detailed_scores(
                        user_id=user_id,
                        question_num=question_num,
                        detailed_scores=detailed_scores,
                        stt_text=transcript
                    )
                    
                    if detailed_success:
                        total_calculated = detailed_scores.get('calculated_total', 0)
                        logger.info(f"  직무적합도 세부 항목 저장 성공: {len([k for k in detailed_scores.keys() if k != 'calculated_total'])}개 항목, 총점 {total_calculated}점")
                        
                        # 카테고리별 점수 출력
                        tech_count = sum(1 for k in detailed_scores.keys() if k.startswith('technical_'))
                        exp_count = sum(1 for k in detailed_scores.keys() if k.startswith('experience_'))
                        app_count = sum(1 for k in detailed_scores.keys() if k.startswith('application_'))
                        logger.info(f"    - 기술적 전문성: {tech_count}개 항목")
                        logger.info(f"    - 실무경험: {exp_count}개 항목")
                        logger.info(f"    - 적용능력: {app_count}개 항목")
                    else:
                        logger.error("  직무적합도 세부 항목 저장 실패")
                        
                    # 하위 호환성을 위해 기술적 전문성만 따로도 저장
                    technical_expertise_details = {k: v for k, v in detailed_scores.items() 
                                                  if k.startswith('technical_')}
                    if technical_expertise_details:
                        tech_success = await self.mongodb_service.save_technical_expertise_details(
                            user_id=user_id,
                            question_num=question_num,
                            technical_details=technical_expertise_details,
                            stt_text=transcript
                        )
                        if tech_success:
                            logger.info(f"  기술적 전문성 (하위 호환) 저장 성공: {len(technical_expertise_details)}개 항목")
                else:
                    logger.info("  직무적합도 세부 항목 없음 (평가 결과에서 추출되지 않음)")
                    
            except Exception as e:
                logger.error(f"직무적합도 세부 항목 저장 중 오류: {e}")
            
            # 10. MongoDB에 한국어 분석 결과 저장 (기존 방식)
            mongo_success = await self.mongodb_service.save_korean_analysis_result(
                user_id=user_id,
                question_num=question_num,
                voice_score=ko_score,
                text_score=text_communication_score,
                total_score=communication_score,
                voice_details=ko_analysis_result['scores_result'],
                text_details=text_scores,
                category_results=category_results,
                stt_text=transcript,
                answer_summary=answer_summary
            )
            
            if mongo_success:
                logger.info(f"종합 점수 저장 성공: user_id={user_id}, question_num={question_num}")
                logger.info(f"  MongoDB 저장 완료")
            else:
                logger.error(f"종합 점수 저장 실패: user_id={user_id}, question_num={question_num}")
            
            return {
                'success': mongo_success,
                'total_score': communication_score,
                'voice_score': ko_score,
                'text_score': text_communication_score,
                'voice_details': ko_analysis_result['scores_result'],
                'text_details': text_scores,
                'category_results': category_results,
                'stt_text': transcript,
                'answer_summary': answer_summary
            }
            
        except Exception as e:
            logger.error(f"전체 워크플로우 실행 중 오류: {str(e)}")
            raise
            
        finally:
            # 임시 파일 정리
            if original_file_path and os.path.exists(original_file_path):
                os.remove(original_file_path)
            if wav_file_path and os.path.exists(wav_file_path):
                os.remove(wav_file_path)

    async def analyze_voice_only(
        self,
        user_id: str,
        question_num: int,
        s3_audio_url: str,
        gender: str = "female"
    ) -> Dict[str, Any]:
        """음성 분석만 수행 (텍스트 분석 제외) - 기존 방식 유지"""
        logger.info(f"음성 분석 워크플로우 시작: {user_id}, 질문{question_num}")
        
        original_file_path = None
        wav_file_path = None
        
        try:
            # 1. S3에서 음성 파일 다운로드
            logger.info("1단계: S3에서 음성 파일 다운로드 중...")
            original_file_path = await self.s3_service.download_file(
                s3_audio_url, 
                self.temp_dir
            )
            logger.info(f"  S3 다운로드 완료: {os.path.basename(original_file_path)}")
            
            # 2. WebM → WAV 변환
            logger.info("2단계: 음성 파일 변환 중 (webm → wav)...")
            wav_file_path = await self.audio_converter.convert_to_wav(
                original_file_path,
                self.temp_dir
            )
            logger.info(f"  음성 변환 완료: {os.path.basename(wav_file_path)}")
            
            # 3. 한국어 음성 분석 (휴지, 속도)
            logger.info("3단계: 한국어 음성 분석 중 (휴지/속도)...")
            ko_analysis_result = await self._analyze_korean_voice(
                wav_file_path, 
                gender
            )
            ko_score = ko_analysis_result['scores_result']['total_score']
            logger.info(f"  한국어 음성 분석 완료: {ko_score:.1f}점/40점")
            
            # 4. MongoDB에 저장
            logger.info("4단계: MongoDB에 음성 분석 결과 저장 중...")
            await self._save_to_mongodb(
                user_id=user_id,
                question_num=question_num,
                ko_analysis_result=ko_analysis_result
            )
            logger.info("  MongoDB 저장 완료")
            
            return {
                "success": True,
                "ko_score": ko_score,
                "ko_analysis_result": ko_analysis_result
            }
            
        except Exception as e:
            logger.error(f"음성 분석 워크플로우 실행 중 오류: {str(e)}")
            raise
            
        finally:
            # 임시 파일 정리
            await self._cleanup_temp_files([original_file_path, wav_file_path])

    async def _analyze_korean_voice(self, wav_file_path: str, gender: str) -> Dict[str, Any]:
        """한국어 음성 분석 실행"""
        try:
            # main.py의 comprehensive_audio_analysis 함수 호출
            result = comprehensive_audio_analysis(
                audio_path=wav_file_path,
                gender=gender,
                chunk_sec=1,
                lang='ko'
            )
            return result
            
        except Exception as e:
            logger.error(f"한국어 음성 분석 중 오류: {str(e)}")
            raise

    async def _save_scores_to_mongodb(
        self, 
        user_id: str, 
        question_num: int,
        total_score: float,
        ko_score: float,
        text_score: float,
        ko_scores: Dict[str, Any],
        text_scores: Dict[str, Any],
        stt_text: str,
        file_path: str
    ):
        """MongoDB에 총점과 개별 점수 저장 (JSON 형식, STT 텍스트 포함)"""
        try:
            # MongoDB에 저장할 점수 데이터 구성
            score_data = {
                "user_id": user_id,
                "question_num": question_num,
                "total_score": total_score,
                "ko_score": ko_score,
                "text_score": text_score,
                "stt_text": stt_text,  # STT 텍스트 추가
                "file_path": file_path,
                "ko_individual_scores": ko_scores.get('individual_scores', {}),
                "ko_details": ko_scores.get('details', {}),
                "text_scores": text_scores,
                "analysis_duration": 0  # 필요시 추가
            }
            
            # MongoDB에 점수 정보 저장
            await self.mongodb_service.save_analysis_scores(score_data)
            
        except Exception as e:
            logger.error(f"MongoDB 점수 저장 중 오류: {str(e)}")
            raise

    async def _save_to_mongodb(
        self, 
        user_id: str, 
        question_num: int, 
        ko_analysis_result: Dict[str, Any]
    ):
        """MongoDB에 한국어 분석 결과 저장 (감정 항목 제거) - 기존 호환성 유지"""
        try:
            scores = ko_analysis_result['scores_result']
            
            # MongoDB 요구사항에 맞는 문서 구조 (감정 필드 제거)
            await self.mongodb_service.save_korean_analysis_result(
                user_id=user_id,
                question_num=question_num,
                ko_score=scores['total_score'],
                pause_score=scores['individual_scores']['pause_score'],
                speech_rate_score=scores['individual_scores']['speech_rate_score']
            )
            
        except Exception as e:
            logger.error(f"MongoDB 저장 중 오류: {str(e)}")
            raise

    async def _cleanup_temp_files(self, file_paths: list):
        """임시 파일들 정리"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.debug(f"임시 파일 삭제: {file_path}")
                except Exception as e:
                    logger.warning(f"임시 파일 삭제 실패 {file_path}: {str(e)}") 