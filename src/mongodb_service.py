"""
MongoDB 연동 서비스
음성 분석 결과 저장 및 조회
"""

import os
import logging
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class MongoDBService:
    """MongoDB 연동 서비스"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        
        # 환경변수에서 MongoDB 설정 가져오기
        self.mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.db_name = os.getenv('MONGODB_DB_NAME', 'audio_analysis')
        
    async def connect(self):
        """MongoDB 연결"""
        try:
            logger.info("MongoDB 연결 시도...")
            self.client = AsyncIOMotorClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            
            # 연결 테스트
            await self.client.admin.command('ping')
            
            # 데이터베이스 설정
            self.db = self.client[self.db_name]
            
            # audio.video_analysis.ko_analysis 컬렉션 설정
            self.collection = self.db['audio_video_analysis_ko_analysis']
            
            # 인덱스 생성 (userId, question_num 조합으로)
            await self.collection.create_index([("userId", 1), ("question_num", 1)], unique=True)
            
            logger.info("MongoDB 연결 성공")
            
        except ConnectionFailure as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB 초기화 중 오류: {e}")
            raise
    
    async def disconnect(self):
        """MongoDB 연결 해제"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 연결 해제됨")
    
    async def save_korean_analysis_result(self, 
                                          user_id: str, 
                                          question_num: int,
                                          voice_score: int,
                                          text_score: int,
                                          total_score: int,
                                          voice_details: Dict[str, Any],
                                          text_details: Dict[str, Any],
                                          category_results: Dict[str, Any],
                                          stt_text: str,
                                          answer_summary: str) -> bool:
        """
        한국어 분석 결과를 MongoDB에 저장
        
        Args:
            user_id: 사용자 ID
            question_num: 질문 번호
            voice_score: 음성 점수
            text_score: 텍스트 점수
            total_score: 총 점수
            voice_details: 음성 분석 상세 결과
            text_details: 텍스트 분석 상세 결과
            category_results: 카테고리 평가 결과
            stt_text: STT 변환 텍스트
            answer_summary: 답변 요약
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 요구사항에 맞는 필드 구성
            document = {
                "userId": user_id,
                "question_num": question_num,
                "voice_score": voice_score,
                "text_score": text_score,
                "total_score": total_score,
                "voice_details": voice_details,
                "text_details": text_details,
                "category_results": category_results,
                "stt_text": stt_text,
                "answer_summary": answer_summary,
                "analysis_timestamp": datetime.utcnow()
            }
            
            # upsert를 사용하여 기존 데이터 업데이트 또는 새로 생성
            result = await self.collection.replace_one(
                {"userId": user_id, "question_num": question_num},
                document,
                upsert=True
            )
            
            if result.acknowledged:
                logger.info(f"한국어 분석 결과 저장 성공: userId={user_id}, question_num={question_num}")
                return True
            else:
                logger.error("한국어 분석 결과 저장 실패: 응답이 승인되지 않음")
                return False
                
        except Exception as e:
            logger.error(f"한국어 분석 결과 저장 중 오류: {e}")
            return False
    
    async def get_korean_analysis_result(self, user_id: str, question_num: int) -> Optional[Dict[str, Any]]:
        """
        한국어 분석 결과 조회
        
        Args:
            user_id: 사용자 ID
            question_num: 질문 번호
            
        Returns:
            Optional[Dict]: 분석 결과 또는 None
        """
        try:
            result = await self.collection.find_one(
                {"userId": user_id, "question_num": question_num}
            )
            
            if result:
                # ObjectId 제거
                result.pop('_id', None)
                logger.info(f"한국어 분석 결과 조회 성공: userId={user_id}, question_num={question_num}")
                return result
            else:
                logger.info(f"한국어 분석 결과 없음: userId={user_id}, question_num={question_num}")
                return None
                
        except Exception as e:
            logger.error(f"한국어 분석 결과 조회 중 오류: {e}")
            return None
    
    async def get_user_analysis_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        사용자의 모든 분석 기록 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            List[Dict]: 분석 기록 리스트
        """
        try:
            cursor = self.collection.find(
                {"userId": user_id}
            ).sort("question_num", 1)
            
            results = []
            async for document in cursor:
                document.pop('_id', None)
                results.append(document)
                
            logger.info(f"사용자 분석 기록 조회 성공: userId={user_id}, 건수={len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"사용자 분석 기록 조회 중 오류: {e}")
            return []
    
    async def delete_analysis_result(self, user_id: str, question_num: int) -> bool:
        """
        분석 결과 삭제
        
        Args:
            user_id: 사용자 ID
            question_num: 질문 번호
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            result = await self.collection.delete_one(
                {"userId": user_id, "question_num": question_num}
            )
            
            if result.deleted_count > 0:
                logger.info(f"분석 결과 삭제 성공: userId={user_id}, question_num={question_num}")
                return True
            else:
                logger.warning(f"삭제할 분석 결과 없음: userId={user_id}, question_num={question_num}")
                return False
                
        except Exception as e:
            logger.error(f"분석 결과 삭제 중 오류: {e}")
            return False
    
    async def get_analysis_stats(self) -> Dict[str, Any]:
        """
        분석 통계 조회
        
        Returns:
            Dict: 통계 정보
        """
        try:
            total_count = await self.collection.count_documents({})
            
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "avg_ko_score": {"$avg": "$ko_score"},
                        "avg_pause_score": {"$avg": "$pause_score"},
                        "avg_speech_rate_score": {"$avg": "$speech_rate_score"}
                    }
                }
            ]
            
            avg_cursor = self.collection.aggregate(pipeline)
            avg_result = await avg_cursor.to_list(length=1)
            
            stats = {
                "total_analyses": total_count,
                "average_scores": avg_result[0] if avg_result else {}
            }
            
            logger.info("분석 통계 조회 성공")
            return stats
            
        except Exception as e:
            logger.error(f"분석 통계 조회 중 오류: {e}")
            return {"total_analyses": 0, "average_scores": {}}

    async def save_analysis_scores(self, score_data: Dict[str, Any]) -> bool:
        """
        종합 분석 점수를 MongoDB에 저장 (새로운 워크플로우용)
        
        Args:
            score_data: 점수 데이터 딕셔너리
                - user_id: 사용자 ID
                - question_num: 질문 번호
                - total_score: 총점
                - ko_score: 한국어 분석 점수
                - text_score: 텍스트 분석 점수
                - stt_text: 변환된 STT 텍스트
                - ko_details: 한국어 분석 세부사항
                - text_scores: 텍스트 분석 세부사항
                
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 점수 컬렉션 설정 (기존과 구분)
            scores_collection = self.db['analysis_comprehensive_scores']
            
            # STT 텍스트 길이 확인
            stt_text = score_data.get("stt_text", "")
            logger.info(f"MongoDB 저장 - STT 텍스트 길이: {len(stt_text)}자")
            logger.info(f"MongoDB 저장 - 전체 STT 텍스트: {stt_text}")
            
            # 구조화된 문서 생성
            document = {
                "user_id": score_data.get("user_id"),
                "question_num": score_data.get("question_num"),
                "analysis_timestamp": datetime.utcnow(),
                "total_score": score_data.get("total_score", 0),
                "stt_text": stt_text,  # STT 텍스트
                "korean_analysis": {
                    "total_score": score_data.get("ko_score", 0),
                    "individual_scores": score_data.get("ko_individual_scores", {}),
                    "details": score_data.get("ko_details", {})
                },
                "text_analysis": {
                    "total_score": score_data.get("text_score", 0),
                    "individual_scores": score_data.get("text_scores", {}),
                    "feedbacks": {
                        "content_feedback": score_data.get("text_scores", {}).get("content_feedback", ""),
                        "logic_feedback": score_data.get("text_scores", {}).get("logic_feedback", ""),
                        "vocabulary_feedback": score_data.get("text_scores", {}).get("vocabulary_feedback", ""),
                        "detailed_feedback": score_data.get("text_scores", {}).get("detailed_feedback", "")
                    }
                },
                "file_info": {
                    "original_file_path": score_data.get("file_path", ""),
                    "analysis_duration": score_data.get("analysis_duration", 0)
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # upsert를 사용하여 기존 데이터 업데이트 또는 새로 생성
            result = await scores_collection.replace_one(
                {"user_id": score_data["user_id"], "question_num": score_data["question_num"]},
                document,
                upsert=True
            )
            
            if result.acknowledged:
                logger.info(f"종합 점수 저장 성공: user_id={score_data['user_id']}, question_num={score_data['question_num']}")
                return True
            else:
                logger.error("종합 점수 저장 실패: 응답이 승인되지 않음")
                return False
                
        except Exception as e:
            logger.error(f"종합 점수 저장 중 오류: {e}")
            return False 