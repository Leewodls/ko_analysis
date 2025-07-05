# ----------------------------------------------------------------------------------------------------
# 작성목적 : 카테고리별 개별 GPT 평가 서비스
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | 카테고리별 개별 GPT 평가 서비스 | 이재인
# ----------------------------------------------------------------------------------------------------

import os
import logging
from typing import Dict, Any, Optional, List, Tuple
import openai
from openai import OpenAI
import json
import yaml
from datetime import datetime

logger = logging.getLogger(__name__)

class CategoryEvaluator:
    """카테고리별 개별 GPT 평가 서비스"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "gpt-4o-mini"
        
        # 문제별 평가 항목 매핑
        self.question_categories = {
            1: ['COMMUNICATION', 'ORG_FIT', 'JOB_COMPATIBILITY', 'TECH_STACK'],
            2: ['COMMUNICATION', 'ORG_FIT', 'JOB_COMPATIBILITY', 'TECH_STACK'],
            3: ['COMMUNICATION', 'ORG_FIT', 'PROBLEM_SOLVING'],
            4: ['COMMUNICATION', 'ORG_FIT', 'JOB_COMPATIBILITY', 'TECH_STACK', 'PROBLEM_SOLVING'],
            5: ['COMMUNICATION', 'ORG_FIT', 'JOB_COMPATIBILITY', 'TECH_STACK', 'PROBLEM_SOLVING'],
            6: ['COMMUNICATION', 'ORG_FIT', 'JOB_COMPATIBILITY'],
            7: ['COMMUNICATION', 'PROBLEM_SOLVING']
        }
        
        # 카테고리별 YAML 파일 매핑
        self.category_file_mapping = {
            'COMMUNICATION': 'communication.yaml',  # 의사소통도 YAML로 관리
            'JOB_COMPATIBILITY': 'job_compatibility.yaml',
            'ORG_FIT': 'org_fit.yaml',
            'TECH_STACK': 'tech_stack.yaml',
            'PROBLEM_SOLVING': 'problem_solving.yaml'
        }
        
        # 카테고리별 프롬프트 템플릿 (YAML에서 로드)
        self.category_prompts = {}
        self.category_output_formats = {}  # 출력 형태 저장
        self._load_prompts_from_yaml()
    
    async def evaluate_categories_for_question(self, 
                                              stt_text: str, 
                                              question_num: int,
                                              communication_score: float) -> Dict[str, Dict[str, Any]]:
        """
        특정 질문에 대한 모든 카테고리 평가
        
        Args:
            stt_text: STT 변환된 텍스트
            question_num: 질문 번호 (1-7)
            communication_score: 기존 방식으로 계산된 의사소통 점수
            
        Returns:
            Dict: 카테고리별 평가 결과
        """
        try:
            results = {}
            categories = self.question_categories.get(question_num, [])
            
            logger.info(f"질문 {question_num}번에 대한 카테고리 평가 시작: {categories}")
            
            # 발화가 없는 경우 GPT에게 명시적으로 전달
            evaluation_text = stt_text.strip() if stt_text.strip() else "발화 없음"
            
            for category in categories:
                if category == 'COMMUNICATION':
                    # 의사소통 능력도 GPT로 평가하여 동적 키워드 생성
                    comm_result = await self._evaluate_single_category(evaluation_text, category, question_num)
                    
                    # 기존 점수는 유지하되, GPT 분석 결과의 키워드는 그대로 사용
                    results[category] = {
                        'score': communication_score,  # 기존 계산된 점수 사용
                        'strength_keyword': comm_result.get('strength_keyword', ''),
                        'weakness_keyword': comm_result.get('weakness_keyword', ''),
                        'detailed_feedback': comm_result.get('detailed_feedback', {}),
                        'total_text_score': comm_result.get('score', 60),  # GPT 평가 점수
                        'feedback': comm_result.get('detailed_feedback', {})
                    }
                else:
                    # 다른 카테고리들은 GPT로 평가
                    category_result = await self._evaluate_single_category(evaluation_text, category, question_num)
                    results[category] = category_result
                    
            logger.info(f"질문 {question_num}번 카테고리 평가 완료")
            return results
            
        except Exception as e:
            logger.error(f"카테고리 평가 중 오류: {e}")
            return {}
    
    async def _evaluate_single_category(self, 
                                       stt_text: str, 
                                       category: str, 
                                       question_num: int) -> Dict[str, Any]:
        """
        단일 카테고리에 대한 GPT 평가
        
        Args:
            stt_text: STT 변환된 텍스트
            category: 평가 카테고리 코드
            question_num: 질문 번호
            
        Returns:
            Dict: 평가 결과 (score, strength_keyword, weakness_keyword)
        """
        try:
            prompt = self._create_category_prompt(stt_text, category, question_num)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 전문 면접관으로서 지원자의 답변을 객관적이고 정확하게 평가하는 AI입니다. 각 카테고리에 대해 0-100점 척도로 점수를 매기고, 구체적인 강점과 약점 키워드를 제시해야 합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content
            
            # 직무적합도 카테고리인 경우 GPT 응답 로깅 및 파일 저장
            if category == 'JOB_COMPATIBILITY':
                logger.info(f"직무적합도 GPT 응답 길이: {len(result_text)}자")
                logger.info(f"직무적합도 GPT 응답:\n{result_text}")
                
                # 디버깅용 응답 저장
                try:
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                        f.write(f"=== 직무적합도 GPT 응답 ===\n")
                        f.write(result_text)
                        f.write(f"\n\n=== 응답 분석 ===\n")
                        f.write(f"길이: {len(result_text)}자\n")
                        f.write(f"'기술적 전문성' 포함: {'기술적 전문성' in result_text}\n")
                        f.write(f"'세부평가' 포함: {'세부평가' in result_text}\n")
                        logger.info(f"GPT 응답 저장됨: {f.name}")
                except Exception as e:
                    logger.error(f"GPT 응답 저장 실패: {e}")
            
            # 출력 형식에 따른 파싱
            output_format = self.category_output_formats.get(category, {})
            
            # structured_feedback 형식 처리
            if output_format.get('type') == 'structured_feedback':
                return self._parse_structured_feedback(result_text, category)
            
            # JSON 파싱 시도 (기본 형식)
            try:
                result = json.loads(result_text)
                
                # 의사소통 카테고리는 다른 구조 사용
                if category == 'COMMUNICATION':
                    return {
                        'total_text_score': max(0, min(60, result.get('total_text_score', 30))),
                        'detailed_scores': result.get('detailed_scores', {}),
                        'feedback': result.get('feedback', {}),
                        'score': max(0, min(60, result.get('total_text_score', 30))),  # 호환성을 위해 추가
                        'strength_keyword': result.get('strength_keyword', ''),
                        'weakness_keyword': result.get('weakness_keyword', '')
                    }
                else:
                    return {
                        'score': max(0, min(100, result.get('score', 50))),
                        'strength_keyword': result.get('strength_keyword', ''),
                        'weakness_keyword': result.get('weakness_keyword', ''),
                        'detailed_feedback': result.get('detailed_feedback', {})
                    }
                
            except json.JSONDecodeError:
                logger.error(f"{category} 카테고리 GPT 응답 JSON 파싱 실패")
                return self._get_default_category_result(category)
                
        except Exception as e:
            logger.error(f"{category} 카테고리 평가 중 오류: {e}")
            return self._get_default_category_result()
    
    def _create_category_prompt(self, stt_text: str, category: str, question_num: int) -> str:
        """
        카테고리별 평가 프롬프트 생성
        
        Args:
            stt_text: STT 변환된 텍스트
            category: 평가 카테고리 코드
            question_num: 질문 번호
            
        Returns:
            str: 생성된 프롬프트
        """
        
        # 출력 형태를 동적으로 생성
        output_format_text = self._generate_output_format_instruction(category)
        
        # 직무적합도의 경우 출력 형태 지시문 로깅
        if category == 'JOB_COMPATIBILITY':
            logger.info(f"직무적합도 출력 형태 지시문 길이: {len(output_format_text)}자")
            # 새로운 형식과 구형 형식 모두 체크
            has_new_format = ('기술적전문성_' in output_format_text or 'detailed_scores' in output_format_text)
            has_old_format = '기술적 전문성' in output_format_text
            
            if has_new_format:
                logger.info("출력 형태 지시문에 '세부 항목별 평가' 형식 포함됨")
            elif has_old_format:
                logger.info("출력 형태 지시문에 '기술적 전문성' (구형) 포함됨")
            else:
                logger.warning("출력 형태 지시문에 '세부 항목별 평가' 형식 누락됨")
        
        # 발화 없음 처리 지침
        no_speech_instruction = ""
        if stt_text.strip() == "발화 없음" or not stt_text.strip():
            no_speech_instruction = """
**중요: 이 답변은 발화가 없거나 무응답입니다.**
- 모든 점수는 0점으로 평가해주세요
- 강점 키워드: 발화 없음
- 약점 키워드: 발화 없음
- 평가 코멘트: 발화가 없어 평가할 수 없음을 명시

"""
        
        base_prompt = f"""
다음 면접 답변을 {self._get_category_name(category)} 관점에서 평가해주세요.

질문 번호: {question_num}
답변 내용:
"{stt_text}"

{no_speech_instruction}

{self._get_category_evaluation_criteria(category)}

{output_format_text}
"""
        
        return base_prompt
    
    def _generate_output_format_instruction(self, category: str) -> str:
        """
        카테고리별 출력 형태 지시문 생성
        
        Args:
            category: 평가 카테고리 코드
            
        Returns:
            str: 출력 형태 지시문
        """
        output_format = self.category_output_formats.get(category, {})
        
        # YAML에서 정의된 출력 형태가 있는 경우 (structured_feedback 포함)
        if output_format and 'structure' in output_format:
            structure = output_format.get('structure', {})
            style_guide = output_format.get('style_guide', '')
            
            # structured_feedback 타입에 대한 특별한 처리
            if output_format.get('type') == 'structured_feedback':
                return self._build_structured_feedback_format(structure, style_guide)
            else:
                # 기존 JSON 구조 처리
                return self._build_json_format_from_structure(structure)
        
        # 기본 JSON 형태 (YAML 정의가 없는 경우)
        if category == 'COMMUNICATION':
            return """
응답은 반드시 다음 JSON 형식으로 작성해주세요:
{
    "total_text_score": [0-60 점수],
    "detailed_scores": {
        "clarity_score": [0-15 점수],
        "logic_score": [0-15 점수],
        "expression_score": [0-15 점수],
        "appropriateness_score": [0-15 점수]
    },
    "feedback": {
        "strengths": ["강점1", "강점2"],
        "improvements": ["개선점1", "개선점2"]
    },
    "strength_keyword": "강점키워드1\\n강점키워드2\\n강점키워드3",
    "weakness_keyword": "약점키워드1\\n약점키워드2\\n약점키워드3"
}

주의사항:
- strength_keyword와 weakness_keyword는 각 키워드를 개행문자(\\n)로 구분해주세요
- 무응답인 경우 weakness_keyword에 발화 없음 형태로 작성해주세요
"""
        else:
            return """
응답은 반드시 다음 JSON 형식으로 작성해주세요:
{
    "score": [0-100 점수],
    "strength_keyword": "강점키워드1\\n강점키워드2\\n강점키워드3",
    "weakness_keyword": "약점키워드1\\n약점키워드2\\n약점키워드3"
}

주의사항:
- strength_keyword와 weakness_keyword는 각 키워드를 개행문자(\\n)로 구분해주세요
- 무응답인 경우 weakness_keyword에 발화 없음 형태로 작성해주세요
"""
    
    def _build_structured_feedback_format(self, structure: dict, style_guide: str) -> str:
        """
        structured_feedback 타입에 대한 출력 형태 지시문 생성
        
        Args:
            structure: YAML에서 정의된 구조
            style_guide: 스타일 가이드
            
        Returns:
            str: 출력 형태 지시문
        """
        output_instruction = "응답은 반드시 다음 형식으로 작성해주세요:\n\n"
        
        for key, value in structure.items():
            if key == 'detailed_scores':
                # 새로운 detailed_scores 섹션 처리 - 최우선
                output_instruction += value.get('format', 
                    "**반드시 아래 형식 그대로 출력하세요:**\n\n세부항목별 평가점수:\n\n기술적전문성_머신러닝딥러닝알고리즘이해도: [0-10점 중 정확한 숫자]\n기술적전문성_머신러닝딥러닝알고리즘설명: [해당 항목에 대한 구체적 평가 설명]\n기술적전문성_데이터처리분석기술: [0-10점 중 정확한 숫자]\n기술적전문성_데이터처리분석기술설명: [해당 항목에 대한 구체적 평가 설명]\n기술적전문성_프레임워크툴활용도: [0-10점 중 정확한 숫자]\n기술적전문성_프레임워크툴활용도설명: [해당 항목에 대한 구체적 평가 설명]\n기술적전문성_최신기술트렌드이해: [0-10점 중 정확한 숫자]\n기술적전문성_최신기술트렌드이해설명: [해당 항목에 대한 구체적 평가 설명]\n\n실무경험_프로젝트규모복잡도: [0-10점 중 정확한 숫자]\n실무경험_프로젝트규모복잡도설명: [해당 항목에 대한 구체적 평가 설명]\n실무경험_데이터처리분석경험: [0-10점 중 정확한 숫자]\n실무경험_데이터처리분석경험설명: [해당 항목에 대한 구체적 평가 설명]\n실무경험_모델배포서비스화경험: [0-8점 중 정확한 숫자]\n실무경험_모델배포서비스화경험설명: [해당 항목에 대한 구체적 평가 설명]\n실무경험_비즈니스임팩트문제해결: [0-7점 중 정확한 숫자]\n실무경험_비즈니스임팩트문제해결설명: [해당 항목에 대한 구체적 평가 설명]\n\n적용능력_비즈니스문제해결능력: [0-10점 중 정확한 숫자]\n적용능력_비즈니스문제해결능력설명: [해당 항목에 대한 구체적 평가 설명]\n적용능력_기술학습적응능력: [0-8점 중 정확한 숫자]\n적용능력_기술학습적응능력설명: [해당 항목에 대한 구체적 평가 설명]\n적용능력_협업커뮤니케이션: [0-7점 중 정확한 숫자]\n적용능력_협업커뮤니케이션설명: [해당 항목에 대한 구체적 평가 설명]\n") + "\n\n"
            elif key == 'total_score':
                output_instruction += f"{value.get('format', '평가총점 : [위 세부 항목 점수를 모두 더한 합계] (예: 세부점수 합이 48점이면 총점도 48점)')}\n\n"
            elif key == 'technical_expertise_details':
                # 구형 호환용 - 하위 호환성 유지
                output_instruction += value.get('format', 
                    "기술적 전문성 세부평가:\n머신러닝딥러닝알고리즘이해도: [0-10점]\n머신러닝딥러닝알고리즘설명: [해당 항목에 대한 구체적 평가 설명]\n데이터처리분석기술: [0-10점]\n데이터처리분석기술설명: [해당 항목에 대한 구체적 평가 설명]\n프레임워크툴활용도: [0-10점]\n프레임워크툴활용도설명: [해당 항목에 대한 구체적 평가 설명]\n최신기술트렌드이해: [0-10점]\n최신기술트렌드이해설명: [해당 항목에 대한 구체적 평가 설명]\n") + "\n\n"
            elif key == 'strengths':
                output_instruction += value.get('format', 
                    "강점:\n[각 줄은 한 줄씩 줄바꿈해줘]\n[답변 내용에서 드러난 구체적 경험이나 특징을 포함한 키워드로 작성해줘]\n") + "\n\n"
            elif key == 'weaknesses':
                output_instruction += value.get('format', 
                    "약점:\n[강점과 동일한 형식]\n[답변에서 부족한 부분이나 개선점을 구체적 맥락과 함께 키워드화]\n") + "\n\n"
        
        if style_guide:
            output_instruction += f"스타일 가이드:\n{style_guide}\n"
        
        return output_instruction
    
    def _parse_structured_feedback(self, result_text: str, category: str) -> Dict[str, Any]:
        """
        structured_feedback 형식의 GPT 응답을 파싱
        
        Args:
            result_text: GPT 응답 텍스트
            category: 카테고리명
            
        Returns:
            Dict[str, Any]: 파싱된 결과
        """
        try:
            import re
            
            # 점수 추출
            score_pattern = r'평가총점\s*[:：]\s*(\d+)'
            score_match = re.search(score_pattern, result_text)
            score = int(score_match.group(1)) if score_match else 0
            
            # 강점 추출
            strengths = []
            strengths_pattern = r'강점:\s*((?:\n.*?)*?)(?=약점:|$)'
            strengths_match = re.search(strengths_pattern, result_text, re.DOTALL)
            if strengths_match:
                strengths_text = strengths_match.group(1).strip()
                # 각 줄을 분리하여 빈 줄과 불필요한 텍스트 제거
                for line in strengths_text.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('[') and not line.startswith('각'):
                        # 앞의 불릿 포인트나 숫자 제거
                        line = re.sub(r'^[-*•\d\.\)\s]+', '', line).strip()
                        if line:
                            strengths.append(line)
            
            # 약점 추출
            weaknesses = []
            weaknesses_pattern = r'약점:\s*((?:\n.*?)*?)(?=$)'
            weaknesses_match = re.search(weaknesses_pattern, result_text, re.DOTALL)
            if weaknesses_match:
                weaknesses_text = weaknesses_match.group(1).strip()
                # 각 줄을 분리하여 빈 줄과 불필요한 텍스트 제거
                for line in weaknesses_text.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('[') and not line.startswith('강점'):
                        # 앞의 불릿 포인트나 숫자 제거
                        line = re.sub(r'^[-*•\d\.\)\s]+', '', line).strip()
                        if line:
                            weaknesses.append(line)
            
            # 직무적합도 카테고리인 경우 전체 세부 항목 추출
            detailed_scores = {}
            final_score = score
            if category == 'JOB_COMPATIBILITY':
                detailed_scores = self._parse_all_detailed_scores(result_text)
                # 세부 항목 점수 합계를 실제 총점으로 사용 (강제 덮어쓰기)
                calculated_total = detailed_scores.get('calculated_total', 0)
                if calculated_total >= 0:  # 0점 이상이면 모두 적용
                    logger.info(f"🔧 직무적합도 총점 강제 수정: GPT 총점 {score} -> 세부 항목 합계 {calculated_total}")
                    final_score = calculated_total  # 세부 항목 합계로 강제 덮어쓰기
                else:
                    logger.warning(f"세부 항목 파싱 실패, GPT 총점 {score} 유지")
            
            result = {
                'score': max(0, min(100, final_score)),
                'strength_keyword': '\n'.join(strengths) if strengths else '',
                'weakness_keyword': '\n'.join(weaknesses) if weaknesses else '',
                'detailed_feedback': {
                    'strengths': strengths,
                    'weaknesses': weaknesses,
                    'total_score': final_score
                }
            }
            
            # 전체 세부 항목이 있는 경우 추가
            if detailed_scores:
                result['detailed_scores'] = detailed_scores
            
            return result
            
        except Exception as e:
            logger.error(f"{category} structured_feedback 파싱 중 오류: {e}")
            return self._get_default_category_result(category)
    
    def _parse_all_detailed_scores(self, result_text: str) -> Dict[str, Any]:
        """
        모든 11개 세부 항목 점수와 설명을 파싱
        
        Args:
            result_text: GPT 응답 텍스트
            
        Returns:
            Dict[str, Any]: 파싱된 전체 세부 항목들
        """
        try:
            import re
            
            detailed_scores = {}
            
            logger.info(f"전체 세부 항목 파싱 시작...")
            
            # 세부항목별 평가점수 섹션 찾기 (정확한 형식 매칭)
            score_section_patterns = [
                r'세부항목별 평가점수:\s*((?:\n.*?)*?)(?=강점:|약점:|평가총점|$)',
                r'세부항목별\s*평가점수\s*[:：]\s*((?:\n.*?)*?)(?=강점:|약점:|평가총점|$)',
                r'세부.*?평가.*?점수.*?[:：]\s*((?:\n.*?)*?)(?=강점:|약점:|평가총점|$)',
                r'\*\*반드시.*?형식.*?\*\*\s*((?:\n.*?)*?)(?=강점:|약점:|평가총점|$)'
            ]
            
            score_section_text = None
            for pattern in score_section_patterns:
                score_section_match = re.search(pattern, result_text, re.DOTALL)
                if score_section_match:
                    score_section_text = score_section_match.group(1).strip()
                    logger.info(f"세부항목별 평가점수 섹션 발견")
                    break
            
            # 11개 세부 항목 정의 (공통 사용)
            detailed_patterns = {
                # 기술적 전문성 (40점)
                'technical_ml_algorithm': {
                    'score_keywords': ['기술적전문성_머신러닝딥러닝알고리즘이해도'],
                    'desc_keywords': ['기술적전문성_머신러닝딥러닝알고리즘설명'],
                    'name': '기술적전문성_머신러닝딥러닝알고리즘이해도',
                    'max_score': 10
                },
                'technical_data_processing': {
                    'score_keywords': ['기술적전문성_데이터처리분석기술'],
                    'desc_keywords': ['기술적전문성_데이터처리분석기술설명'],
                    'name': '기술적전문성_데이터처리분석기술',
                    'max_score': 10
                },
                'technical_framework_tool': {
                    'score_keywords': ['기술적전문성_프레임워크툴활용도'],
                    'desc_keywords': ['기술적전문성_프레임워크툴활용도설명'],
                    'name': '기술적전문성_프레임워크툴활용도',
                    'max_score': 10
                },
                'technical_latest_tech': {
                    'score_keywords': ['기술적전문성_최신기술트렌드이해'],
                    'desc_keywords': ['기술적전문성_최신기술트렌드이해설명'],
                    'name': '기술적전문성_최신기술트렌드이해',
                    'max_score': 10
                },
                
                # 실무경험 (35점)
                'experience_project_scale': {
                    'score_keywords': ['실무경험_프로젝트규모복잡도'],
                    'desc_keywords': ['실무경험_프로젝트규모복잡도설명'],
                    'name': '실무경험_프로젝트규모복잡도',
                    'max_score': 10
                },
                'experience_data_processing': {
                    'score_keywords': ['실무경험_데이터처리분석경험'],
                    'desc_keywords': ['실무경험_데이터처리분석경험설명'],
                    'name': '실무경험_데이터처리분석경험',
                    'max_score': 10
                },
                'experience_model_deployment': {
                    'score_keywords': ['실무경험_모델배포서비스화경험'],
                    'desc_keywords': ['실무경험_모델배포서비스화경험설명'],
                    'name': '실무경험_모델배포서비스화경험',
                    'max_score': 8
                },
                'experience_business_impact': {
                    'score_keywords': ['실무경험_비즈니스임팩트문제해결'],
                    'desc_keywords': ['실무경험_비즈니스임팩트문제해결설명'],
                    'name': '실무경험_비즈니스임팩트문제해결',
                    'max_score': 7
                },
                
                # 적용능력 (25점)
                'application_business_problem': {
                    'score_keywords': ['적용능력_비즈니스문제해결능력'],
                    'desc_keywords': ['적용능력_비즈니스문제해결능력설명'],
                    'name': '적용능력_비즈니스문제해결능력',
                    'max_score': 10
                },
                'application_tech_learning': {
                    'score_keywords': ['적용능력_기술학습적응능력'],
                    'desc_keywords': ['적용능력_기술학습적응능력설명'],
                    'name': '적용능력_기술학습적응능력',
                    'max_score': 8
                },
                'application_collaboration': {
                    'score_keywords': ['적용능력_협업커뮤니케이션'],
                    'desc_keywords': ['적용능력_협업커뮤니케이션설명'],
                    'name': '적용능력_협업커뮤니케이션',
                    'max_score': 7
                }
            }
            
            if score_section_text:
                # 각 항목별 점수와 설명 추출
                for key, patterns_info in detailed_patterns.items():
                    score = 0
                    description = ""
                    
                    # 점수 추출 - 정확한 키:값 매칭 방식
                    for score_keyword in patterns_info['score_keywords']:
                        # 정확한 키:값 패턴 매칭
                        score_pattern = rf'{re.escape(score_keyword)}\s*[:：]\s*(\d+)점?'
                        score_match = re.search(score_pattern, score_section_text)
                        if score_match:
                            potential_score = int(score_match.group(1))
                            max_score = patterns_info['max_score']
                            if 0 <= potential_score <= max_score:
                                score = potential_score
                                logger.info(f"    {key} 점수 추출: {score}점")
                                break
                        
                        # 백업: 라인별 검색
                        lines = score_section_text.split('\n')
                        for line in lines:
                            if score_keyword in line and ':' in line:
                                parts = line.split(':', 1)
                                if len(parts) > 1:
                                    numbers = re.findall(r'\d+', parts[1])
                                    if numbers:
                                        potential_score = int(numbers[0])
                                        max_score = patterns_info['max_score']
                                        if 0 <= potential_score <= max_score:
                                            score = potential_score
                                            logger.info(f"    {key} 점수 추출 (백업): {score}점")
                                            break
                        if score > 0:
                            break
                    
                    # 설명 추출 - 정확한 키:값 매칭 방식  
                    for desc_keyword in patterns_info['desc_keywords']:
                        # 정확한 키:값 패턴 매칭
                        desc_pattern = rf'{re.escape(desc_keyword)}\s*[:：]\s*(.+?)(?=\n|$)'
                        desc_match = re.search(desc_pattern, score_section_text)
                        if desc_match:
                            description = desc_match.group(1).strip()
                            if description:
                                logger.info(f"    {key} 설명 추출됨")
                                break
                        
                        # 백업: 라인별 검색
                        lines = score_section_text.split('\n')
                        for line in lines:
                            if desc_keyword in line:
                                parts = line.split(':', 1)
                                if len(parts) > 1:
                                    description = parts[1].strip()
                                elif '：' in line:
                                    parts = line.split('：', 1)
                                    if len(parts) > 1:
                                        description = parts[1].strip()
                                
                                if description:
                                    logger.info(f"    {key} 설명 추출됨 (백업)")
                                    break
                        if description:
                            break
                    
                    # 결과 저장
                    if score > 0 or description:
                        detailed_scores[key] = {
                            'score': max(0, min(patterns_info['max_score'], score)),
                            'description': description,
                            'name': patterns_info['name'],
                            'max_score': patterns_info['max_score']
                        }
                    else:
                        # 점수와 설명을 찾지 못한 경우 기본값
                        detailed_scores[key] = {
                            'score': 0,
                            'description': "평가 정보 없음",
                            'name': patterns_info['name'],
                            'max_score': patterns_info['max_score']
                        }
                
                logger.info(f"전체 세부 항목 파싱 완료: {len(detailed_scores)}개 항목")
                
                # 총점 계산
                total_calculated = sum(item['score'] for item in detailed_scores.values())
                detailed_scores['calculated_total'] = total_calculated
                logger.info(f"계산된 총점: {total_calculated}점")
                
            else:
                logger.warning("세부항목별 평가점수 섹션을 찾을 수 없음 - 대안 파싱 시도")
                # 대안: 전체 텍스트에서 세부 점수 추출 시도
                detailed_scores = self._parse_from_weaknesses_fallback(result_text, detailed_patterns)
            
            return detailed_scores
            
        except Exception as e:
            logger.error(f"전체 세부 항목 파싱 중 오류: {e}")
            return {}
    
    def _parse_technical_expertise_details(self, result_text: str) -> Dict[str, Any]:
        """
        기술적 전문성 세부 항목들을 파싱 (하위 호환성 유지)
        
        Args:
            result_text: GPT 응답 텍스트
            
        Returns:
            Dict[str, Any]: 파싱된 기술적 전문성 세부 항목들
        """
        # 새로운 파싱 메소드 사용
        all_scores = self._parse_all_detailed_scores(result_text)
        
        # 기술적 전문성 항목만 추출
        technical_details = {}
        technical_keys = [
            'technical_ml_algorithm',
            'technical_data_processing', 
            'technical_framework_tool',
            'technical_latest_tech'
        ]
        
        for key in technical_keys:
            if key in all_scores:
                technical_details[key] = all_scores[key]
        
        return technical_details
    
    def _parse_from_weaknesses_fallback(self, result_text: str, detailed_patterns: dict) -> Dict[str, Any]:
        """
        전체 텍스트에서 세부 항목 점수를 추출하는 대안 파싱 메소드
        
        Args:
            result_text: GPT 응답 텍스트
            detailed_patterns: 세부 항목 패턴 정의
            
        Returns:
            Dict[str, Any]: 파싱된 세부 항목들
        """
        try:
            import re
            
            detailed_scores = {}
            logger.info("전체 응답에서 세부 점수 추출 시도...")
            
            # GPT 실제 출력 형식에 맞춘 강력한 패턴들
            # 예: "1. **머신러닝/딥러닝 알고리즘 이해도 (10점)**: 0점 - 관련 언급 없음"
            score_patterns = [
                # 머신러닝/딥러닝 알고리즘 이해도
                (r'\d+\.\s*\*\*머신러닝.{0,30}딥러닝.{0,30}알고리즘.{0,30}이해도.*?\*\*.*?[:：]\s*(\d+)점', 'technical_ml_algorithm', 10),
                # 데이터 처리/분석 기술  
                (r'\d+\.\s*\*\*데이터.{0,30}처리.{0,30}분석.{0,30}기술.*?\*\*.*?[:：]\s*(\d+)점', 'technical_data_processing', 10),
                # 프레임워크/툴 활용도
                (r'\d+\.\s*\*\*프레임워크.{0,30}툴.{0,30}활용도.*?\*\*.*?[:：]\s*(\d+)점', 'technical_framework_tool', 10),
                # 최신 기술 트렌드 이해
                (r'\d+\.\s*\*\*최신.{0,30}기술.{0,30}트렌드.{0,30}이해.*?\*\*.*?[:：]\s*(\d+)점', 'technical_latest_tech', 10),
                # 프로젝트 규모/복잡도
                (r'\d+\.\s*\*\*프로젝트.{0,30}규모.{0,30}복잡도.*?\*\*.*?[:：]\s*(\d+)점', 'experience_project_scale', 10),
                # 데이터 처리/분석 경험
                (r'\d+\.\s*\*\*데이터.{0,30}처리.{0,30}분석.{0,30}경험.*?\*\*.*?[:：]\s*(\d+)점', 'experience_data_processing', 10),
                # 모델 배포/서비스화 경험  
                (r'\d+\.\s*\*\*모델.{0,30}배포.{0,30}서비스화.{0,30}경험.*?\*\*.*?[:：]\s*(\d+)점', 'experience_model_deployment', 8),
                # 비즈니스 임팩트/문제 해결
                (r'\d+\.\s*\*\*비즈니스.{0,30}임팩트.{0,30}문제.{0,30}해결.*?\*\*.*?[:：]\s*(\d+)점', 'experience_business_impact', 7),
                # 비즈니스 문제 해결 능력
                (r'\d+\.\s*\*\*비즈니스.{0,30}문제.{0,30}해결.{0,30}능력.*?\*\*.*?[:：]\s*(\d+)점', 'application_business_problem', 10),
                # 기술 학습/적응 능력
                (r'\d+\.\s*\*\*기술.{0,30}학습.{0,30}적응.{0,30}능력.*?\*\*.*?[:：]\s*(\d+)점', 'application_tech_learning', 8),
                # 협업/커뮤니케이션
                (r'\d+\.\s*\*\*협업.{0,30}커뮤니케이션.*?\*\*.*?[:：]\s*(\d+)점', 'application_collaboration', 7)
            ]
            
            # 전체 텍스트에서 패턴 매칭
            for pattern, key, max_score in score_patterns:
                matches = re.finditer(pattern, result_text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    score = int(match.group(1))
                    if 0 <= score <= max_score and key not in detailed_scores:
                        detailed_scores[key] = {
                            'score': score,
                            'description': f"GPT 응답에서 추출된 점수 ({match.group(0).strip()[:50]}...)",
                            'name': detailed_patterns.get(key, {}).get('name', key),
                            'max_score': max_score
                        }
                        logger.info(f"  대안 파싱: {key} -> {score}점")
                        break
            
            # 기본 패턴으로 충분히 잘 작동하므로 백업 패턴 비활성화
            # 누락된 항목이 있으면 0점으로 처리
            if len(detailed_scores) < 11:
                logger.info(f"누락된 항목들을 0점으로 처리... (현재: {len(detailed_scores)}/11개)")
                
                all_keys = [
                    'technical_ml_algorithm', 'technical_data_processing', 'technical_framework_tool', 'technical_latest_tech',
                    'experience_project_scale', 'experience_data_processing', 'experience_model_deployment', 'experience_business_impact',
                    'application_business_problem', 'application_tech_learning', 'application_collaboration'
                ]
                
                for key in all_keys:
                    if key not in detailed_scores:
                        max_score = detailed_patterns.get(key, {}).get('max_score', 10)
                        detailed_scores[key] = {
                            'score': 0,
                            'description': f"파싱되지 않은 항목",
                            'name': detailed_patterns.get(key, {}).get('name', key),
                            'max_score': max_score
                        }
                        logger.info(f"  누락 항목: {key} -> 0점")
            
            if detailed_scores:
                # 총점 계산
                total_calculated = sum(item['score'] for item in detailed_scores.values())
                detailed_scores['calculated_total'] = total_calculated
                logger.info(f"대안 파싱 완료: {len(detailed_scores)}개 항목, 총점 {total_calculated}점")
                
                # 각 항목별 점수 로깅
                for key, item in detailed_scores.items():
                    if key != 'calculated_total':
                        logger.info(f"    {key}: {item['score']}/{item['max_score']}점")
            else:
                logger.warning("대안 파싱에서도 세부 점수를 찾을 수 없음")
            
            return detailed_scores
            
        except Exception as e:
            logger.error(f"대안 파싱 중 오류: {e}")
            return {}
    
    def _build_json_format_from_structure(self, structure: dict, indent: int = 0) -> str:
        """
        YAML 구조에서 JSON 형태 지시문 생성
        
        Args:
            structure: YAML에서 정의된 구조
            indent: 들여쓰기 레벨
            
        Returns:
            str: JSON 형태 지시문
        """
        indent_str = "  " * indent
        json_lines = []
        
        json_lines.append(f"{indent_str}{{")
        
        for key, value in structure.items():
            if isinstance(value, dict):
                if 'type' in value:
                    # 단일 필드
                    field_type = value['type']
                    range_info = value.get('range', '')
                    description = value.get('description', '')
                    
                    if field_type == 'number' and range_info:
                        json_lines.append(f'{indent_str}  "{key}": [{range_info[0]}-{range_info[1]} 점수], // {description}')
                    elif field_type == 'array':
                        json_lines.append(f'{indent_str}  "{key}": ["항목1", "항목2"], // {description}')
                    else:
                        json_lines.append(f'{indent_str}  "{key}": "{field_type} 값", // {description}')
                else:
                    # 중첩 객체
                    json_lines.append(f'{indent_str}  "{key}": {{')
                    nested_lines = self._build_json_format_from_structure(value, indent + 2)
                    json_lines.extend(nested_lines.split('\n')[1:-1])  # 중괄호 제외
                    json_lines.append(f'{indent_str}  }}')
        
        json_lines.append(f"{indent_str}}}")
        
        if indent == 0:
            return "응답은 반드시 다음 JSON 형식으로 작성해주세요:\n" + "\n".join(json_lines)
        else:
            return "\n".join(json_lines)
    
    def _get_category_name(self, category: str) -> str:
        """카테고리 코드를 한국어 이름으로 변환"""
        category_names = {
            'COMMUNICATION': '의사소통 능력',
            'JOB_COMPATIBILITY': '직무적합도',
            'ORG_FIT': '조직적합도',
            'TECH_STACK': '보유역량',
            'PROBLEM_SOLVING': '문제해결력'
        }
        return category_names.get(category, category)
    
    def _load_prompts_from_yaml(self):
        """YAML 파일에서 카테고리별 프롬프트 로드"""
        try:
            # prompts 디렉토리 경로 설정
            current_dir = os.path.dirname(os.path.dirname(__file__))  # src의 상위 디렉토리
            prompts_dir = os.path.join(current_dir, 'prompts')
            
            # 각 카테고리별 YAML 파일 로드 (의사소통 포함)
            for category, filename in self.category_file_mapping.items():
                yaml_path = os.path.join(prompts_dir, filename)
                
                try:
                    with open(yaml_path, 'r', encoding='utf-8') as f:
                        yaml_data = yaml.safe_load(f)
                        
                    # YAML 데이터에서 전체 프롬프트 구성
                    evaluation_criteria = yaml_data.get('evaluation_criteria', '')
                    scoring_guide = yaml_data.get('scoring_guide', '')
                    additional_instructions = yaml_data.get('additional_instructions', '')
                    output_format = yaml_data.get('output_format', {})
                    
                    # 전체 프롬프트 조합
                    full_prompt = f"{evaluation_criteria}\n\n{scoring_guide}"
                    if additional_instructions:
                        full_prompt += f"\n\n{additional_instructions}"
                        
                    self.category_prompts[category] = full_prompt
                    self.category_output_formats[category] = output_format  # 출력 형태 저장
                    logger.info(f"{category} 카테고리 프롬프트 로드 완료: {filename}")
                    
                    # 직무적합도의 경우 출력 형식 상세 로깅
                    if category == 'JOB_COMPATIBILITY':
                        structure_keys = list(output_format.get('structure', {}).keys()) if output_format else []
                        logger.info(f"직무적합도 출력 형식 구조: {structure_keys}")
                        has_technical = 'technical_expertise_details' in structure_keys
                        logger.info(f"기술적 전문성 세부항목 포함: {has_technical}")
                    
                except FileNotFoundError:
                    logger.warning(f"프롬프트 파일을 찾을 수 없습니다: {yaml_path}")
                    self.category_prompts[category] = self._get_default_prompt(category)
                except yaml.YAMLError as e:
                    logger.error(f"YAML 파싱 오류: {yaml_path} - {e}")
                    self.category_prompts[category] = self._get_default_prompt(category)
                except Exception as e:
                    logger.error(f"프롬프트 로드 오류: {yaml_path} - {e}")
                    self.category_prompts[category] = self._get_default_prompt(category)
                    
        except Exception as e:
            logger.error(f"프롬프트 초기화 중 오류: {e}")
            # 기본 프롬프트로 설정
            for category in self.category_file_mapping.keys():
                self.category_prompts[category] = self._get_default_prompt(category)
    
    def _get_default_prompt(self, category: str) -> str:
        """기본 프롬프트 반환 (YAML 로드 실패 시)"""
        default_prompts = {
            'COMMUNICATION': "의사소통 능력을 평가해주세요. 명확성, 논리성, 표현력을 중심으로 0-60점으로 평가하세요.",
            'JOB_COMPATIBILITY': "직무적합도를 평가해주세요. 직무 관련 경험, 기술, 이해도를 중심으로 0-100점으로 평가하세요.",
            'ORG_FIT': "조직적합도를 평가해주세요. 팀워크, 협업 능력, 조직 문화 적응력을 중심으로 0-100점으로 평가하세요.",
            'TECH_STACK': "보유역량을 평가해주세요. 기술적 지식, 경험, 학습 능력을 중심으로 0-100점으로 평가하세요.",
            'PROBLEM_SOLVING': "문제해결력을 평가해주세요. 분석 능력, 창의적 사고, 해결 경험을 중심으로 0-100점으로 평가하세요."
        }
        return default_prompts.get(category, "해당 카테고리를 0-100점으로 평가해주세요.")
    
    def _get_category_evaluation_criteria(self, category: str) -> str:
        """카테고리별 평가 기준 (YAML에서 로드된 프롬프트 반환)"""
        return self.category_prompts.get(category, "")
    
    def _get_default_category_result(self, category: str = '') -> Dict[str, Any]:
        """GPT 평가 실패 시 최소한의 결과 반환 (정적 키워드 없음)"""
        if category == 'COMMUNICATION':
            return {
                'total_text_score': 0,
                'detailed_scores': {
                    'clarity_score': 0,
                    'logic_score': 0,
                    'expression_score': 0,
                    'appropriateness_score': 0
                },
                'feedback': {
                    'strengths': [],
                    'improvements': []
                },
                'score': 0,
                'strength_keyword': '발화 없음',
                'weakness_keyword': '발화 없음'
            }
        else:
            return {
                'score': 0,
                'strength_keyword': '발화 없음',
                'weakness_keyword': '발화 없음',
                'detailed_feedback': {}
            }
    
    async def generate_answer_summary(self, stt_text: str) -> str:
        """
        답변 요약 생성 (GPT 활용)
        
        Args:
            stt_text: STT 변환된 텍스트
            
        Returns:
            str: 답변 요약
        """
        try:
            # 발화 없음 처리
            evaluation_text = stt_text.strip() if stt_text.strip() else "발화 없음"
            no_speech_note = ""
            if evaluation_text == "발화 없음":
                no_speech_note = "\n\n**주의: 발화가 없는 경우이므로 발화 없음으로 답변해주세요.**"
            
            prompt = f"""
다음 면접 답변을 간결하게 요약해주세요 (2-3문장):

답변 내용:
"{evaluation_text}"{no_speech_note}

요약 지침:
- 핵심 내용만 간단명료하게
- 지원자의 주요 강점이나 경험 중심으로
- 객관적이고 중립적인 톤으로 작성
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 면접 답변을 요약하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"답변 요약 생성 중 오류: {e}")
            return ""