# ----------------------------------------------------------------------------------------------------
# 작성목적 : Whisper STT 변환 서비스
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | Whisper STT 변환 서비스 | 이재인
# ----------------------------------------------------------------------------------------------------

import os
import logging
import whisper
from typing import Optional, Dict, Any
import torch
import openai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

class WhisperService:
    """Whisper STT 변환 서비스"""
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        self.client = openai.OpenAI(api_key=self.api_key)

    def transcribe(self, audio_path: str, prompt: str = ""):
        try:
            logger.info(f"Whisper API STT 변환 시작: {audio_path}")
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    prompt=prompt,
                    response_format="verbose_json",
                    language="ko"
                )
            transcript = response.text
            logger.info(f"Whisper API STT 변환 완료: {len(transcript)}자")
            logger.debug(f"전체 STT 텍스트: {transcript}")
            return transcript
        except Exception as e:
            logger.error(f"Whisper API STT 변환 실패: {e}")
            return None
    
    async def transcribe_with_segments(self, audio_path: str, language: str = "ko") -> Dict[str, Any]:
        """
        음성 파일을 세그먼트별로 변환
        
        Args:
            audio_path: 음성 파일 경로
            language: 언어 코드
            
        Returns:
            Dict: 전체 텍스트와 세그먼트 정보
        """
        try:
            if not self.model:
                raise RuntimeError("Whisper 모델이 로드되지 않았습니다.")
            
            logger.info(f"세그먼트별 STT 변환 시작: {audio_path}")
            
            result = self.model.transcribe(
                audio_path,
                language=language,
                task="transcribe",
                verbose=False
            )
            
            segments = []
            for segment in result["segments"]:
                segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip()
                })
            
            return {
                "text": result["text"].strip(),
                "segments": segments,
                "language": result.get("language", language)
            }
            
        except Exception as e:
            logger.error(f"세그먼트별 STT 변환 실패: {str(e)}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "loaded": self.model is not None
        } 