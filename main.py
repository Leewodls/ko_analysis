# ----------------------------------------------------------------------------------------------------
# 작성목적 : 한국어 음성 분석 메인 서비스
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | 한국어 음성 분석 메인 서비스 | 이재인
# ----------------------------------------------------------------------------------------------------

import os
import json
import pandas as pd
import numpy as np
import librosa
import soundfile as sf
from scipy import signal
import warnings
import parselmouth
from parselmouth.praat import call
warnings.filterwarnings('ignore')

# voice_analysis 함수들이 아래에 직접 구현됨

def load_korean_data(korean_data_path):
    """한국어 사전 데이터 로드 (현재 사용 안함)"""
    with open(korean_data_path, 'r', encoding='utf-8') as f:
        korean_data = json.load(f)
    
    emotion_grouped_data = {}
    for item in korean_data['individual_results']:
        emotion = item['emotion']
        if emotion not in emotion_grouped_data:
            emotion_grouped_data[emotion] = []
        emotion_grouped_data[emotion].append(item)
    
    return emotion_grouped_data

def get_gender_params(gender):
    """성별에 따른 F0 파라미터 반환"""
    if gender.lower() == 'male':
        return 75, 300
    else:
        return 100, 500

def extract_syllables_per_second(segment, sr):
    """발화 속도 추출 (syllables_per_second)"""
    try:
        # librosa onset detection 사용 (사전 데이터와 동일한 방식)
        onset_env = librosa.onset.onset_strength(y=segment, sr=sr)
        syllables = len(librosa.onset.onset_detect(onset_envelope=onset_env))
        duration = len(segment) / sr
        return syllables / duration if duration > 0 else np.nan
    except:
        return np.nan

def analyze_pause_ratio(audio_file_path):
    """오디오 파일의 휴지 비율을 분석하여 전달력을 평가하는 함수"""
    # 오디오 파일 로드 (원본 샘플링 레이트 유지)
    audio_data, sr = librosa.load(audio_file_path, sr=None, mono=True)
    total_duration = len(audio_data) / sr
        
    # 휴지 탐지 임계값 설정 (한국어 기준)
    min_pause_duration = 0.5    # 실제 휴지로 인정할 최소 길이
    energy_threshold = 0.01     # RMS 에너지 임계값 (1%)
    hop_length = 512           # 프레임 간격
    frame_length = 2048        # 프레임 크기
    
    # RMS 에너지 계산
    rms = librosa.feature.rms(y=audio_data, 
                             frame_length=frame_length, 
                             hop_length=hop_length)[0]
    
    # 시간축 변환
    times = librosa.frames_to_time(np.arange(len(rms)), 
                                  sr=sr, 
                                  hop_length=hop_length)
    
    # 휴지 구간 탐지
    pause_frames = rms < energy_threshold
        
    # 연속된 휴지 구간 찾기
    pause_segments = []
    start_time = None
    
    for i, is_pause in enumerate(pause_frames):
        if is_pause and start_time is None:
            start_time = times[i]
        elif not is_pause and start_time is not None:
            duration = times[i] - start_time
            if duration >= min_pause_duration:  # 500ms 이상만 휴지로 인정
                pause_segments.append(duration)
            start_time = None
    
    # 마지막 구간 처리
    if start_time is not None:
        duration = times[-1] - start_time
        if duration >= min_pause_duration:
            pause_segments.append(duration)
    
    # 휴지 비율 계산
    total_pause_duration = sum(pause_segments)
    pause_ratio = (total_pause_duration / total_duration) * 100
    
    # 전달력 평가 (논문 기준 적용)
    if pause_ratio <= 17:
        grade = "우수"
        description = "전달력이 높음 (논문 기준: 14.8%~15.9%)"
    elif pause_ratio < 25:
        grade = "보통"
        description = "전달력 무난"
    else:
        grade = "미흡"
        description = "전달력이 낮음 (논문 기준: 25.7%~28.0%)"
        
    return {
        'total_duration': total_duration,
        'pause_duration': total_pause_duration,
        'pause_ratio': pause_ratio,
        'pause_count': len(pause_segments),
        'grade': grade,
        'description': description,
        'pause_segments': pause_segments
    }

def extract_features_segmented(audio_path, segment_duration, gender='male'):
    """오디오 파일을 분할하여 각 구간의 모든 특성을 추출"""
    try:
        y, sr = librosa.load(audio_path, sr=None)
        total_duration = librosa.get_duration(y=y, sr=sr)
        
        n_segments = int(np.ceil(total_duration / segment_duration))
        
        features_list = []
        
        for i in range(n_segments):
            start_sample = int(i * segment_duration * sr)
            end_sample = int(min((i + 1) * segment_duration * sr, len(y)))
            segment = y[start_sample:end_sample]
            
            seg_dur = (end_sample - start_sample) / sr
            if seg_dur <= 0.1:
                continue

            # parselmouth Sound 객체 생성
            try:
                snd = parselmouth.Sound(segment, sampling_frequency=sr)
            except Exception as e:
                return {"error": f"Sound 객체 생성 오류: {e}"}
            
            # 사전 데이터와 동일한 방식으로 특성 추출
            if snd is not None:
                syllables_per_second = extract_syllables_per_second(segment, sr)
            else:
                syllables_per_second = np.nan
            
            start_time = float(format(i * segment_duration, ".1f"))
            end_time = float(format(min((i + 1) * segment_duration, total_duration), ".1f"))

            # 사전 데이터와 특성명 통일
            features = {
                'syllables_per_second': syllables_per_second,
                'start_time': start_time,
                'end_time': end_time,
            }
            
            features_list.append(features)
        
        return features_list
        
    except Exception as e:
        print(f"오디오 파일 처리 오류: {e}")
        return []

def calculate_comprehensive_score(pause_analysis_result, features_df):
    """
    휴지 비율과 발화 속도를 종합하여 점수를 산정합니다.

    점수 기준:
    1. 휴지 비율:
        - 20점: 17% 미만 (우수)
        - 10점: 17% ~ 25% (보통)
        - 0점: 25% 이상 (미흡)
    2. 발화 속도:
        - 20점: 5.22~5.76 음절/초 (최고 호감)
        - 15점: 4.68~5.22, 5.76~6.12 음절/초 (중간 호감)
        - 10점: 4.50~4.68, 6.12~6.48 음절/초 (낮은 호감)
        - 5점: 4.13~4.50, 6.48~6.88 음절/초 (최저 호감)
        - 0점: 그 외 (극단적 속도)
    """
    scores = {}

    # 1. 휴지 비율 점수 산정
    pause_ratio = pause_analysis_result.get('pause_ratio', 100)
    if pause_ratio < 17:
        scores['pause_score'] = 20
    elif 17 <= pause_ratio < 25:
        scores['pause_score'] = 10
    else:
        scores['pause_score'] = 0
        
    # 2. 발화 속도 점수 산정
    avg_speech_rate = features_df['syllables_per_second'].mean(skipna=True)
    if pd.isna(avg_speech_rate):
        avg_speech_rate = 0
        
    # 새로운 발화속도 점수 체계
    if 5.22 <= avg_speech_rate <= 5.76:
        scores['speech_rate_score'] = 20  # 최고 호감
    elif (4.68 <= avg_speech_rate < 5.22) or (5.76 < avg_speech_rate <= 6.12):
        scores['speech_rate_score'] = 15  # 중간 호감
    elif (4.50 <= avg_speech_rate < 4.68) or (6.12 < avg_speech_rate <= 6.48):
        scores['speech_rate_score'] = 10  # 낮은 호감
    elif (4.13 <= avg_speech_rate < 4.50) or (6.48 < avg_speech_rate <= 6.88):
        scores['speech_rate_score'] = 5   # 최저 호감
    else:
        scores['speech_rate_score'] = 0   # 극단적 속도
        
    return {
        'total_score': scores['pause_score'] + scores['speech_rate_score'],
        'individual_scores': scores,
        'details': {
            'pause_ratio': round(pause_ratio, 2),
            'avg_speech_rate': round(avg_speech_rate, 2),
        }
    }

def comprehensive_audio_analysis(audio_path, gender='female', chunk_sec=5, lang='ko'):
    """종합적인 음성 분석"""
    
    # 음성 특성 추출
    speech_rate_result = extract_features_segmented(audio_path, chunk_sec, gender)
    
    # 휴지 비율 추출
    pause_analysis_result = analyze_pause_ratio(audio_path)
    
    # 특성 데이터프레임 생성
    features_df = pd.DataFrame(speech_rate_result).dropna().reset_index(drop=True)
    
    # 종합 점수 계산
    scores_result = calculate_comprehensive_score(pause_analysis_result, features_df)
    
    # 요약 정보 계산
    avg_speech_rate = features_df['syllables_per_second'].mean(skipna=True) if not features_df.empty else 0
    
    comprehensive_result = {
        'scores_result': scores_result,
        'speech_rate_result': speech_rate_result,
        'pause_analysis_result': pause_analysis_result,
        'summary': {
            'total_segments': len(features_df),
            'avg_speech_rate': round(avg_speech_rate, 2) if not pd.isna(avg_speech_rate) else 0,
            'pause_ratio': round(pause_analysis_result['pause_ratio'], 2),
            'total_score': scores_result['total_score']
        }
    }
    
    # 결과 저장
    os.makedirs("output/json", exist_ok=True)
    with open("output/json/voice_analysis_result.json", "w", encoding="utf-8") as f:
        json.dump(comprehensive_result, f, ensure_ascii=False, indent=4, default=str)

    return comprehensive_result

# 사용 예시
if __name__ == "__main__":
    input_audio = '/Users/ijaein/Downloads/동기부여 공부자극 전한길 쓴소리 모음.wav'
    gender = 'female'
    chunk_sec = 5
    lang = 'ko'

    result = comprehensive_audio_analysis(
        audio_path=input_audio,
        gender=gender,
        chunk_sec=chunk_sec,
        lang=lang
    )
    
    print(f"평균 발화속도: {result['summary']['avg_speech_rate']} 음절/초")
    print(f"휴지 비율: {result['summary']['pause_ratio']}%")
    print(f"총점: {result['summary']['total_score']}점")