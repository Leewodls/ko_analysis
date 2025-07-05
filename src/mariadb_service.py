# ----------------------------------------------------------------------------------------------------
# 작성목적 : MariaDB 연동 서비스
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 알수없음 | 최초 구현 | MariaDB 연동 서비스 | 이재인
# ----------------------------------------------------------------------------------------------------

import os
import logging
from typing import Dict, Any, Optional, List
import aiomysql
from aiomysql import DictCursor
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class MariaDBService:
    """MariaDB 연동 서비스"""
    
    def __init__(self):
        self.pool = None
        
        # 환경변수에서 MariaDB 설정 가져오기
        self.host = os.getenv('MARIADB_HOST', 'localhost')
        self.port = int(os.getenv('MARIADB_PORT', '3306'))
        self.database = os.getenv('MARIADB_DATABASE', 'communication_db')
        self.user = os.getenv('MARIADB_USER', 'root')
        self.password = os.getenv('MARIADB_PASSWORD', '')
        
    async def connect(self):
        """MariaDB 연결 풀 생성"""
        try:
            logger.info("MariaDB 연결 풀 생성 시도...")
            
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                minsize=1,
                maxsize=10,
                autocommit=False,  # 트랜잭션 관리를 위해 False로 변경
                charset='utf8mb4'
            )
            
            # 테이블 생성
            await self._create_tables()
            
            logger.info("MariaDB 연결 풀 생성 완료")
            
        except Exception as e:
            logger.error(f"MariaDB 연결 실패: {e}")
            raise
    
    async def disconnect(self):
        """MariaDB 연결 풀 해제"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("MariaDB 연결 풀 해제됨")
    
    async def _create_tables(self):
        """필요한 테이블 생성 - 테이블이 존재하면 컬럼만 추가, 없으면 새로 생성"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 외래키 체크 비활성화
                    await cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                    
                    # interview_answer 테이블 처리 (참조 테이블이므로 먼저 생성)
                    await self._create_or_update_interview_answer_table(cursor)
                    
                    # answer_score 테이블 처리
                    await self._create_or_update_answer_score_table(cursor)
                    
                    # answer_category_result 테이블 처리  
                    await self._create_or_update_category_result_table(cursor)
                    
                    # 외래키 체크 재활성화
                    await cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                    
                    await conn.commit()
                    logger.info("모든 테이블 처리 완료")
                    
        except Exception as e:
            logger.error(f"테이블 처리 중 오류: {e}")
            raise

    async def _table_exists(self, cursor, table_name: str) -> bool:
        """테이블 존재 여부 확인"""
        try:
            await cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            result = await cursor.fetchone()
            return result is not None
        except Exception:
            return False

    async def _column_exists(self, cursor, table_name: str, column_name: str) -> bool:
        """컬럼 존재 여부 확인"""
        try:
            await cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{column_name}'")
            result = await cursor.fetchone()
            return result is not None
        except Exception:
            return False

    async def _foreign_key_exists(self, cursor, table_name: str, constraint_name: str) -> bool:
        """외래키 제약조건 존재 여부 확인"""
        try:
            # INFORMATION_SCHEMA를 사용하여 외래키 확인
            check_sql = """
            SELECT COUNT(*) as cnt
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = %s 
            AND CONSTRAINT_NAME = %s 
            AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """
            await cursor.execute(check_sql, (table_name, constraint_name))
            result = await cursor.fetchone()
            return result and result[0] > 0
        except Exception as e:
            logger.warning(f"외래키 존재 확인 중 오류: {e}")
            return False

    async def _ensure_foreign_key_exists(self, cursor, table_name: str):
        """외래키 제약조건 확인 및 추가"""
        constraint_name = "fk_answer_category_result_ans_score_id"
        
        try:
            # 외래키가 이미 존재하는지 확인
            if await self._foreign_key_exists(cursor, table_name, constraint_name):
                logger.info(f"  외래키 제약조건 '{constraint_name}'이 이미 존재합니다.")
                return
            
            logger.info(f"  외래키 제약조건 '{constraint_name}' 추가 중...")
            
            # 외래키 추가
            alter_sql = f"""
            ALTER TABLE {table_name} 
            ADD CONSTRAINT {constraint_name}
            FOREIGN KEY (ANS_SCORE_ID) REFERENCES answer_score(ANS_SCORE_ID)
            ON DELETE CASCADE ON UPDATE CASCADE
            """
            await cursor.execute(alter_sql)
            logger.info(f"  외래키 제약조건 '{constraint_name}' 추가 완료")
            
        except Exception as e:
            error_message = str(e)
            # 외래키가 이미 존재하는 경우 무시
            if "Duplicate key name" in error_message or "already exists" in error_message:
                logger.info(f"  외래키 제약조건 '{constraint_name}'이 이미 존재합니다.")
            else:
                logger.warning(f"  외래키 제약조건 추가 중 오류: {error_message}")
                # 외래키 추가 실패해도 계속 진행 (데이터 무결성은 애플리케이션 레벨에서 관리)

    async def _create_or_update_answer_score_table(self, cursor):
        """answer_score 테이블 생성 또는 컬럼 추가"""
        table_name = "answer_score"
        
        if not await self._table_exists(cursor, table_name):
            # 테이블이 없으면 새로 생성 (외래키 제약조건 포함)
            logger.info(f"{table_name} 테이블이 존재하지 않아 새로 생성합니다.")
            create_sql = """
            CREATE TABLE answer_score (
                ANS_SCORE_ID BIGINT NOT NULL COMMENT '답변 평가 ID',
                INTV_ANS_ID BIGINT NOT NULL COMMENT '면접 답변 ID',
                ANS_SUMMARY TEXT NULL COMMENT '답변 요약',
                EVAL_SUMMARY TEXT NULL COMMENT '전체 평가 요약',
                INCOMPLETE_ANSWER BOOLEAN NULL DEFAULT FALSE COMMENT '미완료 여부',
                INSUFFICIENT_CONTENT BOOLEAN NULL DEFAULT FALSE COMMENT '내용 부족 여부',
                SUSPECTED_COPYING BOOLEAN NULL DEFAULT FALSE COMMENT '커닝 의심 여부',
                SUSPECTED_IMPERSONATION BOOLEAN NULL DEFAULT FALSE COMMENT '대리 시험 의심 여부',
                RGS_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록 일시',
                UPD_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 일시',
                PRIMARY KEY (ANS_SCORE_ID),
                INDEX idx_intv_ans_id (INTV_ANS_ID)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='답변 평가'
            """
            await cursor.execute(create_sql)
            logger.info(f"{table_name} 테이블 생성 완료")
            
            # 외래키 제약조건 추가 (interview_answer 테이블이 존재하는 경우)
            await self._add_foreign_key_if_possible(cursor, table_name)
        else:
            # 테이블이 있으면 필요한 컬럼만 추가
            logger.info(f"{table_name} 테이블이 존재합니다. 필요한 컬럼을 확인합니다.")
            
            # 필요한 컬럼들 정의
            required_columns = {
                'ANS_SCORE_ID': "BIGINT NOT NULL COMMENT '답변 평가 ID'",
                'INTV_ANS_ID': "BIGINT NOT NULL COMMENT '면접 답변 ID'", 
                'ANS_SUMMARY': "TEXT NULL COMMENT '답변 요약'",
                'EVAL_SUMMARY': "TEXT NULL COMMENT '전체 평가 요약'",
                'INCOMPLETE_ANSWER': "BOOLEAN NULL DEFAULT FALSE COMMENT '미완료 여부'",
                'INSUFFICIENT_CONTENT': "BOOLEAN NULL DEFAULT FALSE COMMENT '내용 부족 여부'",
                'SUSPECTED_COPYING': "BOOLEAN NULL DEFAULT FALSE COMMENT '커닝 의심 여부'",
                'SUSPECTED_IMPERSONATION': "BOOLEAN NULL DEFAULT FALSE COMMENT '대리 시험 의심 여부'",
                'RGS_DTM': "TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록 일시'",
                'UPD_DTM': "TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 일시'"
            }
            
            # 없는 컬럼들 추가
            for column_name, column_definition in required_columns.items():
                if not await self._column_exists(cursor, table_name, column_name):
                    logger.info(f"  컬럼 {column_name} 추가 중...")
                    try:
                        await cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
                        logger.info(f"  컬럼 {column_name} 추가 완료")
                    except Exception as e:
                        logger.warning(f"  컬럼 {column_name} 추가 실패: {e}")

    async def _add_foreign_key_if_possible(self, cursor, table_name: str):
        """interview_answer 테이블이 존재하면 외래키 제약조건 추가"""
        try:
            # interview_answer 테이블 존재 확인
            if await self._table_exists(cursor, "interview_answer"):
                constraint_name = "answer_score_ibfk_1"
                if not await self._foreign_key_exists(cursor, table_name, constraint_name):
                    logger.info(f"  외래키 제약조건 '{constraint_name}' 추가 중...")
                    await cursor.execute(f"""
                        ALTER TABLE {table_name} 
                        ADD CONSTRAINT {constraint_name}
                        FOREIGN KEY (INTV_ANS_ID) REFERENCES interview_answer(INTV_ANS_ID)
                        ON DELETE CASCADE ON UPDATE CASCADE
                    """)
                    logger.info(f"  외래키 제약조건 '{constraint_name}' 추가 완료")
                else:
                    logger.info(f"  외래키 제약조건 '{constraint_name}'이 이미 존재합니다.")
            else:
                logger.info("  interview_answer 테이블이 존재하지 않아 외래키 제약조건을 추가하지 않습니다.")
        except Exception as e:
            logger.warning(f"  외래키 제약조건 추가 중 오류 (무시하고 계속): {e}")

    async def _create_or_update_interview_answer_table(self, cursor):
        """interview_answer 테이블이 존재하지 않을 때만 생성"""
        table_name = "interview_answer"
        
        if not await self._table_exists(cursor, table_name):
            # 테이블이 없으면 기존 구조에 맞춰 새로 생성 (외래키 제약조건 제외)
            logger.info(f"{table_name} 테이블이 존재하지 않아 새로 생성합니다.")
            create_sql = """
            CREATE TABLE interview_answer (
                INTV_ANS_ID BIGINT NOT NULL AUTO_INCREMENT,
                INTV_Q_ASSIGN_ID BIGINT NOT NULL,
                ANS_TXT TEXT DEFAULT NULL,
                RGS_DTM TIMESTAMP NULL DEFAULT NULL,
                USER_ID VARCHAR(100) DEFAULT NULL COMMENT '사용자 ID',
                QUESTION_NUM INT DEFAULT NULL COMMENT '질문 번호',
                ANSWER_TEXT TEXT DEFAULT NULL COMMENT '답변 내용',
                UPD_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 일시',
                PRIMARY KEY (INTV_ANS_ID),
                KEY INTV_Q_ASSIGN_ID (INTV_Q_ASSIGN_ID)
            ) ENGINE=InnoDB AUTO_INCREMENT=10010 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
            """
            await cursor.execute(create_sql)
            logger.info(f"{table_name} 테이블 생성 완료 (외래키 제약조건 제외)")
        else:
            # 테이블이 존재하면 아무것도 하지 않음
            logger.info(f"{table_name} 테이블이 이미 존재합니다. 수정하지 않습니다.")

    async def _ensure_interview_answer_exists(self, cursor, intv_ans_id: int, user_id: str, question_num: int):
        """interview_answer 테이블에 레코드가 존재하는지 확인하고 없으면 생성"""
        try:
            # interview_answer 테이블이 존재하는지 확인
            if not await self._table_exists(cursor, "interview_answer"):
                logger.warning("interview_answer 테이블이 존재하지 않습니다.")
                return False
            
            # 레코드 존재 확인
            await cursor.execute("SELECT COUNT(*) FROM interview_answer WHERE INTV_ANS_ID = %s", (intv_ans_id,))
            result = await cursor.fetchone()
            
            if result and result[0] > 0:
                logger.info(f"interview_answer 레코드가 이미 존재합니다: INTV_ANS_ID={intv_ans_id}")
                return True
            
            # 레코드가 없으면 기존 테이블 구조에 맞춰 생성
            logger.info(f"interview_answer 레코드 생성 중: INTV_ANS_ID={intv_ans_id}")
            
            # 기존 테이블 구조에 맞춰 최소한의 필수 값으로 레코드 생성
            # INTV_Q_ASSIGN_ID는 필수이므로 임시값 사용 (1)
            insert_sql = """
            INSERT INTO interview_answer (INTV_ANS_ID, INTV_Q_ASSIGN_ID, USER_ID, QUESTION_NUM, RGS_DTM) 
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE UPD_DTM = NOW()
            """
            await cursor.execute(insert_sql, (intv_ans_id, 1, user_id, question_num))
            
            logger.info(f"interview_answer 레코드 생성 완료: INTV_ANS_ID={intv_ans_id}")
            return True
            
        except Exception as e:
            logger.error(f"interview_answer 레코드 생성 중 오류: {e}")
            return False

    async def _remove_foreign_key_constraint(self, cursor, table_name: str, constraint_name: str):
        """외래키 제약조건 제거"""
        try:
            # 외래키 제약조건이 존재하는지 확인
            if await self._foreign_key_exists(cursor, table_name, constraint_name):
                logger.info(f"  외래키 제약조건 '{constraint_name}' 제거 중...")
                await cursor.execute(f"ALTER TABLE {table_name} DROP FOREIGN KEY {constraint_name}")
                logger.info(f"  외래키 제약조건 '{constraint_name}' 제거 완료")
            else:
                logger.info(f"  외래키 제약조건 '{constraint_name}'이 존재하지 않습니다.")
        except Exception as e:
            logger.warning(f"  외래키 제약조건 제거 중 오류 (무시하고 계속): {e}")

    async def _create_or_update_category_result_table(self, cursor):
        """answer_category_result 테이블 생성 또는 컬럼 추가"""
        table_name = "answer_category_result"
        
        if not await self._table_exists(cursor, table_name):
            # 테이블이 없으면 새로 생성 (외래키 포함)
            logger.info(f"{table_name} 테이블이 존재하지 않아 새로 생성합니다.")
            create_sql = """
            CREATE TABLE answer_category_result (
                ANS_CAT_RESULT_ID BIGINT NOT NULL COMMENT '답변 항목별 평가 ID',
                EVAL_CAT_CD VARCHAR(20) NOT NULL COMMENT '평가 항목 코드',
                ANS_SCORE_ID BIGINT NOT NULL COMMENT '답변 평가 ID',
                ANS_CAT_SCORE DOUBLE NULL COMMENT '항목별 점수',
                STRENGTH_KEYWORD TEXT NULL COMMENT '강점 키워드',
                WEAKNESS_KEYWORD TEXT NULL COMMENT '약점 키워드',
                RGS_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록 일시',
                UPD_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 일시',
                PRIMARY KEY (ANS_CAT_RESULT_ID),
                INDEX idx_ans_score_id (ANS_SCORE_ID),
                INDEX idx_eval_cat_cd (EVAL_CAT_CD),
                CONSTRAINT fk_answer_category_result_ans_score_id 
                    FOREIGN KEY (ANS_SCORE_ID) REFERENCES answer_score(ANS_SCORE_ID)
                    ON DELETE CASCADE ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='답변 항목별 평가 결과'
            """
            await cursor.execute(create_sql)
            logger.info(f"{table_name} 테이블 생성 완료 (외래키 포함)")
        else:
            # 테이블이 있으면 필요한 컬럼만 추가
            logger.info(f"{table_name} 테이블이 존재합니다. 필요한 컬럼을 확인합니다.")
            
            # 필요한 컬럼들 정의
            required_columns = {
                'ANS_CAT_RESULT_ID': "BIGINT NOT NULL COMMENT '답변 항목별 평가 ID'",
                'EVAL_CAT_CD': "VARCHAR(20) NOT NULL COMMENT '평가 항목 코드'",
                'ANS_SCORE_ID': "BIGINT NOT NULL COMMENT '답변 평가 ID'",
                'ANS_CAT_SCORE': "DOUBLE NULL COMMENT '항목별 점수'",
                'STRENGTH_KEYWORD': "TEXT NULL COMMENT '강점 키워드'",
                'WEAKNESS_KEYWORD': "TEXT NULL COMMENT '약점 키워드'",
                'RGS_DTM': "TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록 일시'",
                'UPD_DTM': "TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 일시'"
            }
            
            # 없는 컬럼들 추가
            for column_name, column_definition in required_columns.items():
                if not await self._column_exists(cursor, table_name, column_name):
                    logger.info(f"  {column_name} 컬럼 추가 중...")
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                    await cursor.execute(alter_sql)
                    logger.info(f"  {column_name} 컬럼 추가 완료")
            
            # 외래키 제약조건 확인 및 추가
            await self._ensure_foreign_key_exists(cursor, table_name)

    def _generate_safe_id(self, user_id: str, question_num: int, suffix: str = "") -> int:
        """안전한 ID 생성 (user_id + 0 + question_num 형식)"""
        try:
            # user_id가 숫자인 경우 그대로 사용
            if user_id.isdigit():
                user_id_num = int(user_id)
            else:
                # 문자열인 경우 해시 사용하되 적당한 크기로 제한
                user_id_num = abs(hash(user_id)) % 999 + 1
            
            # question_num이 너무 크면 제한
            if question_num > 99:
                question_num = question_num % 99 + 1
            
            # ID 형식: {user_id}0{question_num}{suffix}
            # 예: user_id=2, question_num=3 -> 203
            # 예: user_id=2, question_num=3, suffix="1" -> 2031
            id_str = f"{user_id_num}0{question_num}{suffix}"
            generated_id = int(id_str)
            
            logger.info(f"ID 생성: user_id={user_id} -> {user_id_num}, question_num={question_num}, suffix='{suffix}' -> ANS_SCORE_ID={generated_id}")
            
            # MySQL BIGINT 범위 확인 (최대 9223372036854775807)
            if generated_id > 9223372036854775807:
                # 너무 큰 경우 해시 사용
                generated_id = abs(hash(f"{user_id}_{question_num}_{suffix}")) % (10**10)
                logger.warning(f"ID가 너무 커서 해시로 변경: {generated_id}")
            
            return generated_id
            
        except (ValueError, OverflowError) as e:
            # 모든 실패 시 해시 사용
            fallback_id = abs(hash(f"{user_id}_{question_num}_{suffix}")) % (10**10)
            logger.error(f"ID 생성 실패, 해시 사용: {e} -> {fallback_id}")
            return fallback_id

    async def get_user_evaluations(self, user_id: str) -> List[Dict[str, Any]]:
        """사용자별 평가 결과 조회"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(DictCursor) as cursor:
                    # answer_score와 category_result 조인 조회
                    select_sql = """
                    SELECT 
                        a.ANS_SCORE_ID,
                        a.INTV_ANS_ID,
                        a.ANS_SUMMARY,
                        a.RGS_DTM,
                        c.EVAL_CAT_CD,
                        c.ANS_CAT_SCORE,
                        c.STRENGTH_KEYWORD,
                        c.WEAKNESS_KEYWORD
                    FROM answer_score a
                    LEFT JOIN answer_category_result c ON a.ANS_SCORE_ID = c.ANS_SCORE_ID
                    WHERE a.INTV_ANS_ID LIKE %s
                    ORDER BY a.ANS_SCORE_ID, c.EVAL_CAT_CD
                    """
                    
                    # user_id를 안전한 형태로 변환하여 검색 패턴 생성
                    if user_id.isdigit():
                        user_id_num = int(user_id)
                        if user_id_num > 99999:
                            user_id_num = user_id_num % 99999 + 1
                    else:
                        user_id_num = abs(hash(user_id)) % 99999 + 1
                    
                    search_pattern = f"{user_id_num}0%"
                    
                    await cursor.execute(select_sql, (search_pattern,))
                    results = await cursor.fetchall()
                    
                    # 결과를 답변별로 그룹화
                    evaluations = {}
                    for row in results:
                        ans_score_id = row['ANS_SCORE_ID']
                        
                        if ans_score_id not in evaluations:
                            evaluations[ans_score_id] = {
                                'ANS_SCORE_ID': row['ANS_SCORE_ID'],
                                'INTV_ANS_ID': row['INTV_ANS_ID'],
                                'ANS_SUMMARY': row['ANS_SUMMARY'],
                                'RGS_DTM': row['RGS_DTM'],
                                'categories': []
                            }
                        
                        if row['EVAL_CAT_CD']:
                            evaluations[ans_score_id]['categories'].append({
                                'EVAL_CAT_CD': row['EVAL_CAT_CD'],
                                'ANS_CAT_SCORE': row['ANS_CAT_SCORE'],
                                'STRENGTH_KEYWORD': row['STRENGTH_KEYWORD'],
                                'WEAKNESS_KEYWORD': row['WEAKNESS_KEYWORD']
                            })
                    
                    result_list = list(evaluations.values())
                    logger.info(f"사용자 평가 목록 조회 성공: user_id={user_id}, 건수={len(result_list)}")
                    return result_list
                    
        except Exception as e:
            logger.error(f"사용자 평가 목록 조회 중 오류: {e}")
            return []

    async def save_answer_evaluation(self, user_id: str, question_num: int, 
                                   answer_summary: str,
                                   category_results: Dict[str, Dict[str, Any]]) -> bool:
        """답변 평가 결과를 MariaDB에 저장"""
        max_retry = 2
        
        for attempt in range(max_retry):
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        # 안전한 ID 생성
                        ans_score_id = self._generate_safe_id(user_id, question_num)
                        intv_ans_id = ans_score_id  # 같은 ID 사용
                        
                        logger.info(f"답변 평가 저장 시작: user_id={user_id}, question_num={question_num} (시도 {attempt + 1}/{max_retry})")
                        logger.info(f"생성된 ID: ANS_SCORE_ID={ans_score_id}, INTV_ANS_ID={intv_ans_id}")
                        
                        # 트랜잭션 시작
                        await conn.begin()
                        
                        try:
                            # interview_answer 테이블에 레코드 생성
                            if not await self._ensure_interview_answer_exists(cursor, intv_ans_id, user_id, question_num):
                                logger.warning(f"interview_answer 레코드가 생성되지 않아 평가를 저장할 수 없습니다. INTV_ANS_ID={intv_ans_id}")
                                await conn.rollback()
                                return False

                            # answer_score 테이블에 기본 평가 정보 저장
                            insert_answer_score_sql = """
                            INSERT INTO answer_score (
                                ANS_SCORE_ID, INTV_ANS_ID, ANS_SUMMARY, INCOMPLETE_ANSWER, INSUFFICIENT_CONTENT, SUSPECTED_COPYING, SUSPECTED_IMPERSONATION
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                ANS_SUMMARY = VALUES(ANS_SUMMARY),
                                INCOMPLETE_ANSWER = VALUES(INCOMPLETE_ANSWER),
                                INSUFFICIENT_CONTENT = VALUES(INSUFFICIENT_CONTENT),
                                SUSPECTED_COPYING = VALUES(SUSPECTED_COPYING),
                                SUSPECTED_IMPERSONATION = VALUES(SUSPECTED_IMPERSONATION),
                                UPD_DTM = CURRENT_TIMESTAMP
                            """
                            
                            await cursor.execute(insert_answer_score_sql, (
                                ans_score_id, intv_ans_id, answer_summary, False, False, False, False
                            ))
                            logger.info(f"answer_score 저장 완료")
                            
                            # 기존 카테고리 결과 삭제
                            await cursor.execute("DELETE FROM answer_category_result WHERE ANS_SCORE_ID = %s", (ans_score_id,))
                            
                            # answer_category_result 테이블에 카테고리별 결과 저장
                            if category_results:
                                logger.info(f"카테고리 결과 저장 시작: {len(category_results)}개")
                                
                                for i, (category, result) in enumerate(category_results.items(), 1):
                                    # 카테고리별 고유 ID 생성
                                    ans_cat_result_id = self._generate_safe_id(user_id, question_num, str(i))
                                    
                                    insert_category_sql = """
                                    INSERT INTO answer_category_result (
                                        ANS_CAT_RESULT_ID, EVAL_CAT_CD, ANS_SCORE_ID, ANS_CAT_SCORE, 
                                        STRENGTH_KEYWORD, WEAKNESS_KEYWORD
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                    """
                                    
                                    score = result.get('score', 0)
                                    strength = result.get('strength_keyword', '')
                                    weakness = result.get('weakness_keyword', '')
                                    
                                    logger.info(f"카테고리 {category} 저장 중: ID={ans_cat_result_id}, score={score}")
                                    await cursor.execute(insert_category_sql, (
                                        ans_cat_result_id, category, ans_score_id, score, strength, weakness
                                    ))
                            
                            # 트랜잭션 커밋
                            await conn.commit()
                            logger.info(f"답변 평가 저장 완료: user_id={user_id}, question_num={question_num}")
                            return True
                            
                        except Exception as e:
                            # 트랜잭션 롤백
                            await conn.rollback()
                            raise e
                        
            except Exception as e:
                error_message = str(e)
                logger.error(f"답변 평가 저장 중 오류 (시도 {attempt + 1}): {error_message}")
                
                # 테이블이나 컬럼 관련 오류인 경우 테이블 재생성
                if ("Unknown column" in error_message or 
                    "Table" in error_message and "doesn't exist" in error_message or
                    "Unknown table" in error_message) and attempt < max_retry - 1:
                    
                    logger.warning("테이블 또는 컬럼 관련 오류 감지. 테이블 구조를 업데이트합니다...")
                    try:
                        await self._create_tables()  # _recreate_tables 대신 _create_tables 사용
                        continue  # 다시 시도
                    except Exception as update_error:
                        logger.error(f"테이블 구조 업데이트 중 오류: {update_error}")
                
                if attempt == max_retry - 1:
                    logger.error(f"MariaDB 저장 최종 실패: user_id={user_id}, question_num={question_num}")
                    return False
        
        return False
    
    async def _recreate_tables(self):
        """테이블 재생성 - 더 이상 사용하지 않음 (컬럼 추가 방식으로 변경됨)"""
        # 테이블을 삭제하고 재생성하는 것보다 컬럼만 추가하는 방식으로 변경됨
        # 이 메서드는 호환성을 위해 남겨두지만 더 이상 사용하지 않음
        logger.warning("_recreate_tables는 더 이상 사용되지 않습니다. _create_tables를 사용하세요.")
        await self._create_tables()
        
        # try:
        #     async with self.pool.acquire() as conn:
        #         async with conn.cursor() as cursor:
        #             # 외래키 체크 비활성화
        #             await cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        #             
        #             # 테이블 삭제 (순서 중요: 자식 테이블부터)
        #             await cursor.execute("DROP TABLE IF EXISTS answer_category_result")
        #             await cursor.execute("DROP TABLE IF EXISTS answer_score")
        #             logger.info("기존 테이블 삭제 완료")
        #             
        #             # 테이블 재생성
        #             await self._create_tables()
        #             
        #             # 외래키 체크 재활성화
        #             await cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        #             
        #             await conn.commit()
        #             logger.info("테이블 재생성 완료")
        #             
        # except Exception as e:
        #     logger.error(f"테이블 재생성 중 오류: {e}")
        #     raise 