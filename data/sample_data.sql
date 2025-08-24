-- 초기 샘플 데이터 SQL
-- Open API 데이터 구조 기반 샘플 데이터

-- 직종 분류 데이터
INSERT INTO job_categories (jobs_code, jobs_name) VALUES 
('01D', '금융·보험 사무 및 영업'),
('02A', '소프트웨어 개발'),
('03B', '게임 개발'),
('04C', '마케팅·광고·홍보'),
('05D', '디자인')
ON CONFLICT (jobs_code) DO NOTHING;

-- 기업 정보 샘플 데이터
INSERT INTO companies (
    emp_co_no, company_name, business_number, company_classification,
    map_coord_x, map_coord_y, logo_url, homepage,
    intro_summary, intro_detail, main_business
) VALUES 
(
    'E000023944',
    '일일일퍼센트',
    '1368700241',
    NULL,
    127.036508620542,
    37.5000242405515,
    'http://example.com/111percent_logo.png',
    'https://111percent.net/',
    '게임개발 회사',
    '111퍼센트는 재미라는 본질에 집중하며, 게임이 아닌 장르를 만듭니다. 재미는 심플하고, 참신한 룰에서 나옵니다.',
    '모바일 게임 개발 및 퍼블리싱'
),
(
    'E000024001',
    '테크스타트업',
    '1234567890',
    '중견기업',
    126.978652,
    37.566536,
    'http://example.com/techstartup_logo.png',
    'https://techstartup.co.kr/',
    'AI 기술 기반 스타트업',
    '인공지능과 머신러닝 기술을 활용한 혁신적인 솔루션을 개발하는 기업입니다.',
    'AI/ML 솔루션 개발'
),
(
    'E000024002',
    '우리은행',
    '2148142951',
    '대기업',
    126.981611,
    37.568477,
    'http://example.com/wooribank_logo.png',
    'https://www.wooribank.com/',
    '종합 금융 서비스',
    '1899년 설립된 대한민국의 대표적인 시중은행으로, 다양한 금융 서비스를 제공합니다.',
    '은행업, 금융 서비스'
)
ON CONFLICT (emp_co_no) DO NOTHING;

-- 복리후생 정보 (일일일퍼센트)
INSERT INTO company_welfare (company_id, category_name, welfare_content) 
SELECT c.id, unnest(ARRAY['휴무/휴가/행사', '보장/보상/지원', '생활편의/사내시설', '기타']),
       unnest(ARRAY[
           '전사 겨울 방학',
           '경조사 지원/명절 선물/생일 선물/종합검진/야근시 저녁 식대, 택시비 지원',
           '식대 지원/사내 카페/스낵바/안마의자',
           '시차 출퇴근제/웰컴키트/최고급 장비 지원'
       ])
FROM companies c WHERE c.emp_co_no = 'E000023944';

-- 복리후생 정보 (우리은행)
INSERT INTO company_welfare (company_id, category_name, welfare_content)
SELECT c.id, unnest(ARRAY['보장/보상/지원', '휴무/휴가/행사', '교육/자기계발']),
       unnest(ARRAY[
           '4대보험/퇴직금/장기근속 포상/우량 보험상품 할인 혜택',
           '연차/반차/경조휴가/출산휴가/육아휴직',
           '교육비 지원/어학 교육/전문 자격증 취득 지원'
       ])
FROM companies c WHERE c.emp_co_no = 'E000024002';

-- 연혁 정보 (일일일퍼센트)
INSERT INTO company_history (company_id, history_year, history_month, history_content)
SELECT c.id, unnest(ARRAY['2025', '2025', '2024', '2024', '2023']),
       unnest(ARRAY['04', '03', '12', '09', '12']),
       unnest(ARRAY[
           '[운빨존많겜] 하남 / 고양 / 안성 스타필드 팝업스토어 운빨초등학교 진행',
           '청강문화산업대학교 MOU 체결',
           '[운빨존많겜] 구글 플레이 선정, 올해를 빛낸 캐주얼 게임 최우수상 수상',
           '[운빨존많겜] Apple App Store 매출 1위',
           '[랜덤다이스: GO] 구글플레이 선정 올해를 빛낸 인디 게임 우수상 수상'
       ])
FROM companies c WHERE c.emp_co_no = 'E000023944';

-- 인재상 정보
INSERT INTO company_talent_criteria (company_id, keyword, description)
SELECT c.id, '창의성, 도전정신, 팀워크', '새로운 게임 장르를 만들어나가는 창의적인 인재를 찾습니다.'
FROM companies c WHERE c.emp_co_no = 'E000023944';

INSERT INTO company_talent_criteria (company_id, keyword, description)
SELECT c.id, '전문성, 소통능력, 고객중심', '금융 전문성을 바탕으로 고객에게 최고의 서비스를 제공하는 인재'
FROM companies c WHERE c.emp_co_no = 'E000024002';

-- 채용공고 정보
INSERT INTO job_postings (
    emp_seq_no, title, company_id, job_category_id,
    start_date, end_date, employment_type,
    company_homepage, detail_url,
    summary_content, common_content, submit_documents,
    application_method, inquiry_content, other_content
) VALUES 
(
    '999999',
    '게임 개발자 모집 (Unity/C#)',
    (SELECT id FROM companies WHERE emp_co_no = 'E000023944'),
    (SELECT id FROM job_categories WHERE jobs_code = '03B'),
    '2025-08-20',
    '2025-09-20',
    '정규직',
    'https://111percent.net/',
    'https://111percent.net/careers',
    '창의적이고 실력 있는 게임 개발자를 모집합니다.',
    '적극적이고 창의적인 개발자를 찾습니다.',
    '이력서, 포트폴리오',
    '온라인 지원 (careers@111percent.net)',
    'hr@111percent.net으로 문의바랍니다.',
    '지원서류는 반환되지 않으며, 허위 기재시 불이익이 있을 수 있습니다.'
),
(
    '999998',
    '2025년 사무지원직군 신입행원 모집',
    (SELECT id FROM companies WHERE emp_co_no = 'E000024002'),
    (SELECT id FROM job_categories WHERE jobs_code = '01D'),
    '2025-08-18',
    '2025-08-28',
    '정규직',
    'https://www.wooribank.com/',
    'https://wooribank.careerlink.kr/jobs',
    '우리은행과 함께 성장할 신입행원을 모집합니다.',
    '자세한 사항은 채용 홈페이지 참조 바랍니다.',
    '지원서, 성적증명서, 어학성적표',
    '우리은행 채용 사이트를 통한 온라인 접수',
    '우리은행 채용 사이트 1:1 문의 활용',
    '청탁 등 부정행위 확인시 합격 또는 채용이 취소될 수 있습니다.'
);

-- 전형 단계 정보
INSERT INTO job_posting_steps (job_posting_id, step_name, step_order, step_content, memo_content)
SELECT jp.id, unnest(ARRAY['서류전형', '1차면접', '최종면접', '합격자발표']),
       unnest(ARRAY[1, 2, 3, 4]),
       unnest(ARRAY['포트폴리오 및 이력서 검토', '기술 면접', '임원 면접', '개별 연락']),
       unnest(ARRAY[NULL, '기술 역량 중심 평가', '인성 및 조직 적합성 평가', '합격자에게만 개별 연락'])
FROM job_postings jp WHERE jp.emp_seq_no = '999999';

INSERT INTO job_posting_steps (job_posting_id, step_name, step_order, step_content)
SELECT jp.id, unnest(ARRAY['서류전형', '1차면접', '최종면접', '합격자 발표', '건강검진']),
       unnest(ARRAY[1, 2, 3, 4, 5]),
       unnest(ARRAY['지원서류 검토', '실무진 면접', '임원 면접', '합격자 발표', '입사 전 건강검진'])
FROM job_postings jp WHERE jp.emp_seq_no = '999998';

-- 모집 부문 정보
INSERT INTO job_posting_positions (
    job_posting_id, position_name, job_description, work_region,
    career_requirement, education_requirement, other_requirements,
    recruitment_count, memo_content
) VALUES 
(
    (SELECT id FROM job_postings WHERE emp_seq_no = '999999'),
    'Unity 게임 개발자',
    '모바일 게임 개발 및 유지보수
- Unity를 활용한 게임 클라이언트 개발
- C# 기반 게임 로직 구현
- 게임 최적화 및 성능 튜닝',
    '서울',
    '신입/경력',
    '학력무관',
    '- Unity 엔진 활용 경험
- C# 프로그래밍 능력
- 게임 개발에 대한 열정
- Git 사용 경험 우대',
    '2',
    '포트폴리오 필수 제출'
),
(
    (SELECT id FROM job_postings WHERE emp_seq_no = '999998'),
    '사무지원직군',
    '- 영업지원 업무를 담당하는 집중화센터 등 근무
- 본부부서 사무보조
- 구청 영업점 공금영업지원 등',
    '서울',
    '신입',
    '학력무관',
    '- 학력/연령/성별 : 제한 없음
- 남성의 경우, 병역필 또는 면제자
- 해외여행에 결격사유가 없는 자
- 당행 내규상 채용에 결격사유가 없는 자',
    '00',
    '정확한 모집인원은 추후 공지'
);

-- 자기소개서 질문
INSERT INTO job_posting_self_intro (job_posting_id, question_content, question_order)
VALUES 
(
    (SELECT id FROM job_postings WHERE emp_seq_no = '999999'),
    '게임 개발에 대한 본인만의 철학과 경험을 자유롭게 서술해 주세요.',
    1
),
(
    (SELECT id FROM job_postings WHERE emp_seq_no = '999998'),
    '우리은행에 지원한 동기와 입사 후 포부를 구체적으로 작성해 주세요.',
    1
);

-- 샘플 템플릿 데이터
INSERT INTO job_posting_templates (
    source_job_posting_id, company_id, title, content, template_data,
    generation_status, generation_metadata
) VALUES 
(
    (SELECT id FROM job_postings WHERE emp_seq_no = '999999'),
    (SELECT id FROM companies WHERE emp_co_no = 'E000023944'),
    '[111%] Unity 게임 개발자 채용 - 함께 새로운 게임 장르를 만들어가요!',
    '## 📱 모바일 게임의 새로운 패러다임을 만드는 111%에서 함께할 Unity 개발자를 찾습니다!

### 🎮 이런 일을 하게 됩니다
- Unity를 활용한 혁신적인 모바일 게임 개발
- 전세계 1억 명 이상이 플레이하는 게임의 핵심 로직 구현
- 심플하면서도 참신한 게임 룰 시스템 개발
- 최적화를 통한 완벽한 게임 경험 제공

### 🔍 이런 분과 함께 하고 싶어요
- Unity 엔진과 C# 에 능숙한 분
- 창의적 사고와 도전정신을 가진 분
- 게임 개발에 진정한 열정을 가진 분
- 팀워크를 중시하는 분

### 🏢 111%는 이런 회사입니다
- 구글 플레이 선정 "올해를 빛낸 캐주얼 게임" 최우수상 수상
- Apple App Store 매출 1위 달성
- "Move Fast, Change Everytime!" - 다른데, 빠르다!',
    '{"sections": ["company_intro", "job_description", "requirements", "benefits"], "tone": "friendly", "target_audience": "game_developers"}',
    'draft',
    '{"model": "gpt-4", "prompt_version": "v1.0", "generated_at": "2025-01-01T00:00:00Z"}'
);

-- 인덱스 생성 확인 쿼리
-- SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;
