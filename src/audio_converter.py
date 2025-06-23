"""
오디오 파일 변환 서비스
WebM, MP3, MP4 등을 WAV로 변환
"""

import os
import subprocess
import tempfile
import logging
from typing import Optional
import ffmpeg

logger = logging.getLogger(__name__)

class AudioConverter:
    """오디오 파일 변환 서비스"""
    
    def __init__(self):
        self.supported_formats = ['.webm', '.mp3', '.mp4', '.m4a', '.ogg', '.wav']
        self.target_sample_rate = 16000  # Whisper와 한국어 모델에 최적화
        self.target_channels = 1  # 모노
    
    async def convert_to_wav(self, input_path: str, output_dir: str) -> str:
        """
        입력 오디오 파일을 WAV로 변환
        
        Args:
            input_path: 입력 파일 경로
            output_dir: 출력 디렉토리
            
        Returns:
            str: 변환된 WAV 파일 경로
        """
        try:
            logger.info(f"오디오 변환 시작: {input_path}")
            
            # 입력 파일 확장자 확인
            input_ext = os.path.splitext(input_path)[1].lower()
            if input_ext not in self.supported_formats:
                raise ValueError(f"지원하지 않는 파일 형식: {input_ext}")
            
            # 이미 WAV 파일인 경우 샘플링 레이트와 채널 확인
            if input_ext == '.wav':
                return await self._process_wav_file(input_path, output_dir)
            
            # 출력 파일 경로 생성
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_converted.wav")
            
            # FFmpeg을 사용한 변환
            await self._convert_with_ffmpeg(input_path, output_path)
            
            logger.info(f"오디오 변환 완료: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"오디오 변환 실패: {str(e)}")
            raise
    
    async def _convert_with_ffmpeg(self, input_path: str, output_path: str):
        """FFmpeg을 사용하여 파일 변환"""
        try:
            # FFmpeg 변환 설정
            stream = ffmpeg.input(input_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='pcm_s16le',  # 16-bit PCM
                ac=self.target_channels,  # 모노
                ar=self.target_sample_rate,  # 16kHz
                y=None  # 덮어쓰기 확인
            )
            
            # 변환 실행
            ffmpeg.run(stream, quiet=True, overwrite_output=True)
            
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg 변환 오류: {str(e)}")
            # FFmpeg이 실패하면 subprocess로 시도
            await self._convert_with_subprocess(input_path, output_path)
    
    async def _convert_with_subprocess(self, input_path: str, output_path: str):
        """Subprocess를 사용한 변환 (FFmpeg 대안)"""
        try:
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-acodec', 'pcm_s16le',
                '-ac', str(self.target_channels),
                '-ar', str(self.target_sample_rate),
                '-y',  # 덮어쓰기
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            
            if result.returncode != 0:
                raise subprocess.SubprocessError(f"FFmpeg 오류: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg 변환 시간 초과")
            raise
        except FileNotFoundError:
            logger.error("FFmpeg이 설치되지 않았습니다.")
            raise
    
    async def _process_wav_file(self, input_path: str, output_dir: str) -> str:
        """기존 WAV 파일의 샘플링 레이트와 채널 확인 및 조정"""
        try:
            # FFprobe로 파일 정보 확인
            probe = ffmpeg.probe(input_path)
            audio_stream = next(
                (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
                None
            )
            
            if not audio_stream:
                raise ValueError("오디오 스트림을 찾을 수 없습니다.")
            
            current_sample_rate = int(audio_stream['sample_rate'])
            current_channels = int(audio_stream['channels'])
            
            # 이미 올바른 형식인 경우 그대로 반환
            if (current_sample_rate == self.target_sample_rate and 
                current_channels == self.target_channels):
                logger.info("WAV 파일이 이미 올바른 형식입니다.")
                return input_path
            
            # 변환 필요
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_processed.wav")
            
            await self._convert_with_ffmpeg(input_path, output_path)
            return output_path
            
        except Exception as e:
            logger.error(f"WAV 파일 처리 실패: {str(e)}")
            raise
    
    def get_audio_info(self, file_path: str) -> dict:
        """오디오 파일 정보 조회"""
        try:
            probe = ffmpeg.probe(file_path)
            audio_stream = next(
                (stream for stream in probe['streams'] if stream['codec_type'] == 'audio'),
                None
            )
            
            if not audio_stream:
                return {"error": "오디오 스트림을 찾을 수 없습니다."}
            
            return {
                "codec": audio_stream.get('codec_name'),
                "sample_rate": int(audio_stream.get('sample_rate', 0)),
                "channels": int(audio_stream.get('channels', 0)),
                "duration": float(audio_stream.get('duration', 0)),
                "bit_rate": audio_stream.get('bit_rate')
            }
            
        except Exception as e:
            logger.error(f"오디오 정보 조회 실패: {str(e)}")
            return {"error": str(e)}
    
    async def extract_audio_segment(
        self, 
        input_path: str, 
        output_path: str, 
        start_time: float, 
        duration: float
    ) -> str:
        """오디오에서 특정 구간 추출"""
        try:
            stream = ffmpeg.input(input_path, ss=start_time, t=duration)
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='pcm_s16le',
                ac=self.target_channels,
                ar=self.target_sample_rate
            )
            
            ffmpeg.run(stream, quiet=True, overwrite_output=True)
            return output_path
            
        except Exception as e:
            logger.error(f"오디오 구간 추출 실패: {str(e)}")
            raise 