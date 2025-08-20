# evaluator.py
"""
스캔 결과(JSON) + URL 텍스트를 가이드 기반 RAG로 재검증/분석합니다.
결과: 오탐/미탐, 심각도, 완화책, 근거(가이드 p.x / URL 경로) 등 구조화.
"""
from typing import Dict, Any, Optional
from config import client, MODEL_RESPONSES

MODEL = MODEL_RESPONSES

def assess_findings(findings: Optional[Dict[str, Any]], url_text: str,
                    guide_vs_id: str, url_vs_id: str, top_k: int = 5) -> Dict[str, Any]:
    """
    TODO:
    - tools=[{"type":"file_search","vector_store_ids":[guide_vs_id, url_vs_id], "max_num_results": top_k}]
    - system: 보안 전문가 baseline prompt (rag.load_baseline_prompt 재사용해도 됨)
    - user: findings(JSON)와 url_text 요약을 함께 투입, 가이드 근거로 진위/심각도/대응책 생성
    """
    # 최소 스텁
    return {
        "verdict": "potential_sqli",
        "explanation": "응답 내 DB 에러 패턴과 타임 딜레이가 관찰됨.",
        "mitigations": [
            "ORM 사용 및 모든 입력 값 파라미터 바인딩",
            "DB 에러 메시지 노출 차단",
            "WAF 시그니처 업데이트"
        ],
        "citations": [
            {"source": "가이드.pdf", "page": 42},
            {"source": "url", "path": "/login"}
        ]
    }
