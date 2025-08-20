# planner.py
"""
사용자 자유 질의를 보안 테스트 플랜(JSON)으로 구조화합니다.
RAG(File Search)를 활용해 '가이드 + URL 스냅샷'에 근거한 체크리스트를 생성.
"""
from typing import Dict
from config import client, MODEL_RESPONSES
from rag import load_baseline_prompt  # 보안 전문가 페르소나/출력 형식 유지:contentReference[oaicite:4]{index=4}

MODEL = MODEL_RESPONSES  # rag.py와 통일 권장:contentReference[oaicite:5]{index=5}

def make_test_plan(user_query: str, target_url: str, guide_vs_id: str, url_vs_id: str, top_k: int = 5) -> Dict:
    """
    Returns: 계획 JSON (objective/scope/attacks/templates/payloads/detection/controls...)
    TODO:
    - system: 보안 전문가 baseline prompt
    - tools: file_search with [guide_vs_id, url_vs_id]
    - user: user_query + target_url로 목적/범위/금지/레이트리밋/우선 취약점/템플릿 생성 요구
    """
    sys = load_baseline_prompt()
    # 최소 스텁(실제는 Responses 호출하여 JSON 포맷을 강제 출력)
    plan = {
        "objective": f"Assess: {user_query}",
        "scope": {
            "targets": [target_url],
            "allow": [target_url],
            "forbid": [],
            "rate_limit": 5
        },
        "attacks": ["sqli_boolean", "sqli_time_based"],
        "templates": ["generic/sqli"],
        "payloads": ["' OR '1'='1", "'; WAITFOR DELAY '0:0:5'--"],
        "detection": {"signals": ["db_error", "timing_delta>3s"]},
        "controls": {"guide_refs": ["가이드.pdf p.42, p.77"]}
    }
    return plan
