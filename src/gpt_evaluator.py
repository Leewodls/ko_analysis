# ----------------------------------------------------------------------------------------------------
# 작성목적 : GPT 기반 텍스트 평가 서비스
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | GPT 기반 텍스트 평가 서비스 | 이재인
# ----------------------------------------------------------------------------------------------------

import os
import logging
from typing import Dict, Any, Optional
import openai
from openai import OpenAI
import json
import yaml
from datetime import datetime

logger = logging.getLogger(__name__)

class GPTEvaluator:
    """GPT 기반 언어적 표현 평가 서비스"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "gpt-4o-mini"
        self.prompts_dir = "prompts"
        
    async def evaluate_communication(self, text: str, audio_path: str = "", question_context: str = "") -> Dict[str, Any]:
        """
        의사소통 능력 종합 평가 (텍스트 분석 60점 + 모델 분석 40점 = 총 100점)
        
        Args:
            text: STT로 변환된 텍스트
            audio_path: 음성 파일 경로 (모델 분석용)
            question_context: 질문 맥락
            
        Returns:
            Dict: 의사소통 평가 결과
                - text_analysis_score: 텍스트 분석 점수 (0-60)
                - model_analysis_score: 모델 분석 점수 (0-40)
                - total_communication_score: 총 의사소통 점수 (0-100)
                - strengths: 강점 리스트
                - weaknesses: 약점 리스트
        """
        try:
            logger.info("의사소통 능력 종합 평가 시작")
            
            # 1. 텍스트 분석 (60점) - YAML 프롬프트 사용
            text_result = await self._evaluate_text_communication(text, question_context)
            
            # 2. 모델 분석 (40점) - main.py의 음성 분석 사용
            model_result = self._evaluate_audio_communication(audio_path) if audio_path else {'score': 0, 'details': {}}
            
            # 3. 결과 통합
            total_score = text_result['text_score'] + model_result['score']
            
            return {
                'text_analysis_score': text_result['text_score'],
                'model_analysis_score': model_result['score'],
                'total_communication_score': total_score,
                'text_details': text_result,
                'model_details': model_result,
                'strengths': text_result.get('strengths', []),
                'weaknesses': text_result.get('weaknesses', [])
            }
            
        except Exception as e:
            logger.error(f"의사소통 평가 중 오류: {e}")
            return self._get_default_communication_scores()

    async def _evaluate_text_communication(self, text: str, question_context: str = "") -> Dict[str, Any]:
        """텍스트 기반 의사소통 평가 (60점 만점)"""
        try:
            logger.info("텍스트 기반 의사소통 평가 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("communication.yaml")
            if not prompt_config:
                return self._get_default_text_scores()
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**질문 맥락:** {question_context}

**지원자 답변:**
{text}

위 답변을 평가 기준에 따라 분석하고, 지정된 출력 형식으로 결과를 제시해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '의사소통 능력 평가 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.info("텍스트 기반 의사소통 평가 완료")
            
            # 결과 파싱 (구조화된 피드백 형식)
            return self._parse_communication_feedback(result_text)
            
        except Exception as e:
            logger.error(f"텍스트 의사소통 평가 중 오류: {e}")
            return self._get_default_text_scores()

    def _evaluate_audio_communication(self, audio_path: str) -> Dict[str, Any]:
        """음성 기반 의사소통 평가 (40점 만점) - main.py의 로직 활용"""
        try:
            if not audio_path or not os.path.exists(audio_path):
                logger.warning("음성 파일이 없어 모델 분석을 건너뜁니다")
                return {'score': 0, 'details': {'error': '음성 파일 없음'}}
            
            # main.py의 comprehensive_audio_analysis 함수 호출
            from main import comprehensive_audio_analysis
            
            logger.info("음성 분석 시작")
            analysis_result = comprehensive_audio_analysis(
                audio_path=audio_path,
                gender='female',  # 기본값, 필요시 파라미터로 받을 수 있음
                chunk_sec=5,
                lang='ko'
            )
            
            # 40점 만점으로 점수 추출
            model_score = analysis_result['summary']['total_score']  # 이미 40점 만점
            
            logger.info(f"음성 분석 완료 - 점수: {model_score}/40")
            
            return {
                'score': model_score,
                'details': {
                    'pause_ratio': analysis_result['summary']['pause_ratio'],
                    'avg_speech_rate': analysis_result['summary']['avg_speech_rate'],
                    'pause_score': analysis_result['scores_result']['individual_scores']['pause_score'],
                    'speech_rate_score': analysis_result['scores_result']['individual_scores']['speech_rate_score']
                }
            }
            
        except Exception as e:
            logger.error(f"음성 의사소통 평가 중 오류: {e}")
            return {'score': 0, 'details': {'error': str(e)}}

    def _parse_communication_feedback(self, feedback_text: str) -> Dict[str, Any]:
        """구조화된 피드백 텍스트를 파싱하여 점수와 강점/약점 추출"""
        try:
            lines = feedback_text.strip().split('\n')
            score = 0
            strengths = []
            weaknesses = []
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 점수 추출
                if line.startswith('평가총점'):
                    try:
                        score = int(line.split(':')[-1].strip())
                    except:
                        score = 30  # 기본값
                
                # 섹션 구분
                elif line.startswith('강점'):
                    current_section = 'strengths'
                elif line.startswith('약점'):
                    current_section = 'weaknesses'
                elif current_section == 'strengths' and line:
                    strengths.append(line)
                elif current_section == 'weaknesses' and line:
                    weaknesses.append(line)
            
            return {
                'text_score': max(0, min(60, score)),  # 60점 만점으로 제한
                'strengths': strengths,
                'weaknesses': weaknesses,
                'raw_feedback': feedback_text
            }
            
        except Exception as e:
            logger.error(f"피드백 파싱 중 오류: {e}")
            return self._get_default_text_scores()

    def _get_default_communication_scores(self) -> Dict[str, Any]:
        """오류 시 기본 의사소통 점수 반환"""
        return {
            'text_analysis_score': 30,
            'model_analysis_score': 20,
            'total_communication_score': 50,
            'text_details': self._get_default_text_scores(),
            'model_details': {'score': 20, 'details': {}},
            'strengths': ['기본적인 의사소통 가능'],
            'weaknesses': ['평가 데이터 부족']
        }

    def _get_default_text_scores(self) -> Dict[str, Any]:
        """오류 시 기본 텍스트 점수 반환"""
        return {
            'text_score': 30,
            'strengths': ['기본적인 언어 표현'],
            'weaknesses': ['평가 데이터 부족'],
            'raw_feedback': '평가총점 : 0\n강점:\n기본적인 언어 표현\n약점:\n평가 데이터 부족'
        }
    
    def _load_prompt_from_yaml(self, filename: str) -> Dict[str, Any]:
        """YAML 파일에서 프롬프트 로드"""
        try:
            filepath = os.path.join(self.prompts_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"프롬프트 파일을 찾을 수 없습니다: {filename}")
            return {}
        except Exception as e:
            logger.error(f"프롬프트 파일 로드 중 오류: {e}")
            return {}
    
    def _get_default_scores(self) -> Dict[str, Any]:
        """오류 시 기본 점수 반환 (하위 호환성을 위해 유지)"""
        return {
            'content_composition_score': 10,
            'logic_score': 10,
            'vocabulary_score': 10,
            'total_text_score': 30,
            'detailed_scores': {}
        }

    # 기존 generate_final_comment 메서드는 제거됨
    # 새로운 3개의 메서드로 대체: generate_answer_summary, generate_answer_evaluation, generate_evaluation_summary

    async def prepare_analysis_data(
        self, 
        user_id: str, 
        question_num: int,
        total_score: float,
        ko_score: float, 
        text_score: float,
        ko_scores: Dict,
        text_scores: Dict,
        final_comment: str,
        stt_text: str = ""
    ) -> Dict:
        """통합 분석 결과 데이터 준비 (파일 저장 없이)"""
        try:
            # JSON 데이터 구성
            analysis_data = {
                "metadata": {
                    "user_id": user_id,
                    "question_num": question_num,
                    "analysis_timestamp": datetime.now().isoformat(),
                    "total_score": total_score,
                    "ko_score": ko_score,
                    "text_score": text_score
                },
                "stt_text": stt_text,
                "detailed_scores": {
                    "korean_analysis": {
                        "total_score": ko_score,
                        "pause_score": ko_scores['individual_scores'].get('pause_score', 0),
                        "speech_rate_score": ko_scores['individual_scores'].get('speech_rate_score', 0),
                        "details": ko_scores.get('details', {})
                    },
                    "text_analysis": {
                        "total_score": text_score,
                        "content_composition_score": text_scores.get('content_composition_score', 0),
                        "logic_score": text_scores.get('logic_score', 0),
                        "vocabulary_score": text_scores.get('vocabulary_score', 0),
                        "detailed_scores": text_scores.get('detailed_scores', {})
                    }
                },
                "integrated_comment": final_comment
            }
            
            logger.info("통합 분석 결과 데이터 준비 완료")
            return analysis_data
            
        except Exception as e:
            logger.error(f"분석 데이터 준비 중 오류: {str(e)}")
            raise

    async def generate_answer_summary(self, answer_text: str) -> str:
        """답변요약: 지원자의 답변을 요약"""
        try:
            logger.info("답변요약 생성 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("answer_summary.yaml")
            if not prompt_config:
                return "답변요약 생성 중 오류가 발생했습니다."
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**지원자 답변:**
{answer_text}

위 답변을 요약해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '답변요약 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info("답변요약 생성 완료")
            return summary
            
        except Exception as e:
            logger.error(f"답변요약 생성 중 오류: {e}")
            return "답변요약 생성 중 오류가 발생했습니다."

    async def generate_answer_evaluation(self, analysis_data: Dict) -> str:
        """답변평가: 분석 데이터를 바탕으로 답변을 종합 평가"""
        try:
            logger.info("답변평가 생성 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("answer_evaluation.yaml")
            if not prompt_config:
                return "답변평가 생성 중 오류가 발생했습니다."
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**분석 데이터:**
```json
{json.dumps(analysis_data, ensure_ascii=False, indent=2)}
```

위 분석 데이터를 바탕으로 면접자의 답변을 평가해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '답변평가 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            evaluation = response.choices[0].message.content.strip()
            logger.info("답변평가 생성 완료")
            return evaluation
            
        except Exception as e:
            logger.error(f"답변평가 생성 중 오류: {e}")
            return "답변평가 생성 중 오류가 발생했습니다."

    async def generate_evaluation_summary(self, all_evaluation_results: Dict) -> str:
        """평가요약: 모든 평가 결과를 종합하여 최종 요약"""
        try:
            logger.info("평가요약 생성 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("evaluation_summary.yaml")
            if not prompt_config:
                return "평가요약 생성 중 오류가 발생했습니다."
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**모든 평가 결과:**
```json
{json.dumps(all_evaluation_results, ensure_ascii=False, indent=2)}
```

위 모든 평가 결과를 종합하여 최종 평가 요약을 작성해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '평가요약 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info("평가요약 생성 완료")
            return summary
            
        except Exception as e:
            logger.error(f"평가요약 생성 중 오류: {e}")
            return "평가요약 생성 중 오류가 발생했습니다."

    async def evaluate_job_compatibility(self, text: str, question_context: str = "") -> Dict[str, Any]:
        """직무적합도 평가 (job_compatibility.yaml 사용)"""
        try:
            logger.info("직무적합도 평가 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("job_compatibility.yaml")
            if not prompt_config:
                return self._get_default_evaluation_scores("직무적합도")
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**질문 맥락:** {question_context}

**지원자 답변:**
{text}

위 답변을 평가 기준에 따라 분석하고, 지정된 출력 형식으로 결과를 제시해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '직무적합도 평가 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.info("직무적합도 평가 완료")
            
            return self._parse_evaluation_feedback(result_text, "직무적합도")
            
        except Exception as e:
            logger.error(f"직무적합도 평가 중 오류: {e}")
            return self._get_default_evaluation_scores("직무적합도")

    async def evaluate_org_fit(self, text: str, question_context: str = "") -> Dict[str, Any]:
        """조직적합도 평가 (org_fit.yaml 사용)"""
        try:
            logger.info("조직적합도 평가 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("org_fit.yaml")
            if not prompt_config:
                return self._get_default_evaluation_scores("조직적합도")
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**질문 맥락:** {question_context}

**지원자 답변:**
{text}

위 답변을 평가 기준에 따라 분석하고, 지정된 출력 형식으로 결과를 제시해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '조직적합도 평가 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.info("조직적합도 평가 완료")
            
            return self._parse_evaluation_feedback(result_text, "조직적합도")
            
        except Exception as e:
            logger.error(f"조직적합도 평가 중 오류: {e}")
            return self._get_default_evaluation_scores("조직적합도")

    async def evaluate_problem_solving(self, text: str, question_context: str = "") -> Dict[str, Any]:
        """문제해결력 평가 (problem_solving.yaml 사용)"""
        try:
            logger.info("문제해결력 평가 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("problem_solving.yaml")
            if not prompt_config:
                return self._get_default_evaluation_scores("문제해결력")
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**질문 맥락:** {question_context}

**지원자 답변:**
{text}

위 답변을 평가 기준에 따라 분석하고, 지정된 출력 형식으로 결과를 제시해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '문제해결력 평가 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.info("문제해결력 평가 완료")
            
            return self._parse_evaluation_feedback(result_text, "문제해결력")
            
        except Exception as e:
            logger.error(f"문제해결력 평가 중 오류: {e}")
            return self._get_default_evaluation_scores("문제해결력")

    async def evaluate_tech_stack(self, text: str, question_context: str = "") -> Dict[str, Any]:
        """보유역량 평가 (tech_stack.yaml 사용)"""
        try:
            logger.info("보유역량 평가 시작")
            
            # YAML 프롬프트 로드
            prompt_config = self._load_prompt_from_yaml("tech_stack.yaml")
            if not prompt_config:
                return self._get_default_evaluation_scores("보유역량")
            
            # 프롬프트 구성
            prompt = f"""
{prompt_config.get('evaluation_criteria', '')}

{prompt_config.get('additional_instructions', '')}

**질문 맥락:** {question_context}

**지원자 답변:**
{text}

위 답변을 평가 기준에 따라 분석하고, 지정된 출력 형식으로 결과를 제시해주세요.
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": f"당신은 {prompt_config.get('description', '보유역량 평가 전문가')}입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content.strip()
            logger.info("보유역량 평가 완료")
            
            return self._parse_evaluation_feedback(result_text, "보유역량")
            
        except Exception as e:
            logger.error(f"보유역량 평가 중 오류: {e}")
            return self._get_default_evaluation_scores("보유역량")

    def _parse_evaluation_feedback(self, feedback_text: str, category: str) -> Dict[str, Any]:
        """일반적인 평가 피드백 텍스트를 파싱하여 점수와 강점/약점 추출"""
        try:
            lines = feedback_text.strip().split('\n')
            score = 0
            strengths = []
            weaknesses = []
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 점수 추출
                if line.startswith('평가총점'):
                    try:
                        score = int(line.split(':')[-1].strip())
                    except:
                        score = 0  # 기본값을 0으로 변경
                
                # 섹션 구분
                elif line.startswith('강점'):
                    current_section = 'strengths'
                elif line.startswith('약점'):
                    current_section = 'weaknesses'
                elif current_section == 'strengths' and line:
                    strengths.append(line)
                elif current_section == 'weaknesses' and line:
                    weaknesses.append(line)
            
            return {
                'score': max(0, min(100, score)),  # 100점 만점으로 제한
                'category': category,
                'strengths': strengths,
                'weaknesses': weaknesses,
                'strength_keyword': '\n'.join(strengths) if strengths else '',  # MariaDB용 문자열 형태 추가
                'weakness_keyword': '\n'.join(weaknesses) if weaknesses else '',  # MariaDB용 문자열 형태 추가
                'raw_feedback': feedback_text
            }
            
        except Exception as e:
            logger.error(f"{category} 피드백 파싱 중 오류: {e}")
            return self._get_default_evaluation_scores(category)

    def _get_default_evaluation_scores(self, category: str) -> Dict[str, Any]:
        """오류 시 기본 평가 점수 반환"""
        return {
            'score': 0,  # 기본값을 0으로 변경
            'category': category,
            'strengths': [f'기본적인 {category} 능력'],
            'weaknesses': ['평가 데이터 부족'],
            'strength_keyword': '발화 없음',  # MariaDB용 문자열 형태 추가
            'weakness_keyword': '발화 없음',  # MariaDB용 문자열 형태 추가
            'raw_feedback': f'평가총점 : 0\n강점:\n기본적인 {category} 능력\n약점:\n평가 데이터 부족'
        } 