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
            7: ['COMMUNICATION', 'ORG_FIT', 'PROBLEM_SOLVING']
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
            evaluation_text = stt_text.strip() if stt_text.strip() else "발화 없음 (무응답)"
            
            for category in categories:
                if category == 'COMMUNICATION':
                    # 의사소통 능력도 GPT로 평가하여 동적 키워드 생성
                    comm_result = await self._evaluate_single_category(evaluation_text, category, question_num)
                    
                    # 기존 점수는 유지하되, GPT 분석 결과의 키워드만 사용
                    feedback = comm_result.get('feedback', {})
                    strengths = feedback.get('strengths', [])
                    improvements = feedback.get('improvements', [])
                    
                    results[category] = {
                        'score': communication_score,
                        'strength_keyword': ', '.join(strengths) if strengths else '',
                        'weakness_keyword': ', '.join(improvements) if improvements else '',
                        'detailed_feedback': comm_result.get('detailed_feedback', {}),
                        'total_text_score': comm_result.get('total_text_score', 60),
                        'feedback': feedback
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
            
            # JSON 파싱 시도
            try:
                result = json.loads(result_text)
                
                # 의사소통 카테고리는 다른 구조 사용
                if category == 'COMMUNICATION':
                    return {
                        'total_text_score': max(0, min(60, result.get('total_text_score', 30))),
                        'detailed_scores': result.get('detailed_scores', {}),
                        'feedback': result.get('feedback', {}),
                        'score': max(0, min(60, result.get('total_text_score', 30)))  # 호환성을 위해 추가
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
        
        # 발화 없음 처리 지침
        no_speech_instruction = ""
        if stt_text.strip() == "발화 없음 (무응답)" or not stt_text.strip():
            no_speech_instruction = """
**중요: 이 답변은 발화가 없거나 무응답입니다.**
- 모든 점수는 0점으로 평가해주세요
- 강점 키워드: 빈 문자열 또는 빈 배열
- 약점 키워드: "발화 없음", "무응답", "답변 부재" 등 무응답 관련 키워드
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
        
        if not output_format or output_format.get('type') != 'json':
            # 기본 JSON 형태
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
    }
}
"""
            else:
                return """
응답은 반드시 다음 JSON 형식으로 작성해주세요:
{
    "score": [0-100 점수],
    "strength_keyword": "[강점을 나타내는 키워드나 문구]",
    "weakness_keyword": "[약점을 나타내는 키워드나 문구]"
}
"""
        
        # YAML에서 정의된 출력 형태 사용
        structure = output_format.get('structure', {})
        return self._build_json_format_from_structure(structure)
    
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
                'score': 0
            }
        else:
            return {
                'score': 0,
                'strength_keyword': '',
                'weakness_keyword': '',
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
            evaluation_text = stt_text.strip() if stt_text.strip() else "발화 없음 (무응답)"
            no_speech_note = ""
            if evaluation_text == "발화 없음 (무응답)":
                no_speech_note = "\n\n**주의: 발화가 없는 경우이므로 '답변 없음' 또는 '무응답'으로 요약해주세요.**"
            
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