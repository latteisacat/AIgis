# planner.py
"""
사용자 자유 질의 + 타깃 URL을 바탕으로
'보안 테스트 플랜(JSON)'을 생성하는 모듈.

- OpenAI Responses API + File Search 사용(guide_vs + url_vs 동시 연결)
- system 프롬프트: rag.load_baseline_prompt() (보안 전문가 페르소나)
- 출력: 엄격 JSON (objective/scope/attacks/templates/payloads/detection/controls 등)
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
import re

from config import client, MODEL_RESPONSES
from rag import load_baseline_prompt


# --- JSON 스키마(목표 구조) ---
# 필요한 필드를 상황에 맞게 확장 가능
PLAN_JSON_INSTRUCTIONS = """\
아래 JSON 스키마에 '정확히' 맞춰 결과만 출력하세요 (추가 텍스트 금지).
{
  "objective": "string (사용자 의도를 한 줄로 요약)",
  "scope": {
    "targets": ["string"],            // 테스트 대상 URL/경로
    "allow": ["string"],              // 허용 도메인/경로
    "forbid": ["string"],             // 금지 메서드/경로/행위
    "rate_limit": 5                   // 초당 요청 제한(정수)
  },
  "attacks": ["string"],              // 예: "sqli_boolean", "sqli_time_based", "xss_reflected"
  "templates": ["string"],            // nuclei 등 도구 템플릿 키워드/ID
  "payloads": ["string"],             // 안전/비파괴 우선 페이로드 샘플
  "detection": {
    "signals": ["string"]             // 성공/실패 판단 신호(예: "db_error", "timing_delta>3s")
  },
  "controls": {
    "guide_refs": ["string"]          // 가이드 문서 근거 (예: "가이드.pdf p.42")
  }
}
"""


def _coerce_json_from_text(text: str) -> Dict[str, Any]:
    """
    모델 출력에서 JSON만 추출/파싱.
    - 최선: 순수 JSON이 오면 그대로 loads
    - 보정: ```json ... ``` 블록 또는 {} 가장 큰 블록 추출 시도
    실패하면 기본 뼈대 반환
    """
    text = text.strip()
    # 1) 순수 JSON 시도
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) ```json ... ``` 블록 추출
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 3) 가장 큰 {} 블록
    m2 = re.search(r"(\{.*\})", text, re.DOTALL)
    if m2:
        snippet = m2.group(1)
        # 가끔 끝에 쉼표/누락된 대괄호 등 있을 수 있어 최소 보정 없이 시도
        try:
            return json.loads(snippet)
        except Exception:
            pass

    # 실패 시 기본 뼈대
    return {
        "objective": "",
        "scope": {"targets": [], "allow": [], "forbid": [], "rate_limit": 5},
        "attacks": [],
        "templates": [],
        "payloads": [],
        "detection": {"signals": []},
        "controls": {"guide_refs": []}
    }


def make_test_plan(
    user_query: str,
    target_url: str,
    guide_vs_id: str,
    url_vs_id: str,
    top_k: int = 5,
    extra_constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    File Search(guide_vs + url_vs)를 기반으로 사용자 질의를
    '구조화된 보안 테스트 플랜(JSON)'으로 변환합니다.

    Args:
        user_query: 사용자의 목적/분석 포커스 (예: "SQL Injection 가능성 점검")
        target_url: 테스트 대상 URL
        guide_vs_id: 가이드 문서 벡터스토어 ID (영구)
        url_vs_id: 수집된 URL 텍스트 벡터스토어 ID (임시)
        top_k: File Search에서 참조할 컨텍스트 개수
        extra_constraints: 플랜에 강제로 반영할 제약(예: {"rate_limit": 3})

    Returns:
        Dict(JSON): 위 스키마에 맞는 보안 테스트 플랜
    """
    system_prompt = load_baseline_prompt()
    # 사용자 메시지: 목적/대상/제약 명시 + JSON으로만 출력 지시
    user_prompt = f"""\
[목표]
- 사용자의 분석 목적: "{user_query}"
- 테스트 대상 URL: {target_url}

[지침]
- 반드시 '제공된 컨텍스트(RAG: 가이드 + URL 스냅샷)'를 근거로 작성
- 법적/윤리적 가드레일 준수: 비파괴/저부하/허용 범위 내
- 방어가능한 체크리스트(근거: 가이드 문서)로 구성
- 출력은 '오직 JSON'으로만, 아래 스키마를 엄격히 따를 것

[출력 스키마]
{PLAN_JSON_INSTRUCTIONS}
"""

    # 디버깅 로그
    print(f"[DEBUG][planner] request model={MODEL_RESPONSES}, top_k={top_k}, VS=[{guide_vs_id}, {url_vs_id}]")
    # Responses 호출 (File Search 두 스토어 동시 연결)
    resp = client.responses.create(
        model=MODEL_RESPONSES,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[{
            "type": "file_search",
            "vector_store_ids": [guide_vs_id, url_vs_id],
            "max_num_results": top_k
        }],
        # 필요 시: tool_choice="auto" (기본값), include 옵션 등
    )

    text = resp.output_text or ""
    print(f"[DEBUG][planner] response id={getattr(resp, 'id', None)}")
    # 필요시 tokens 사용량:
    try:
        print(f"[DEBUG][planner] usage={resp.usage}")
    except Exception:
        pass
    print(f"[DEBUG][planner] preview={text[:400]}...")

    plan = _coerce_json_from_text(text)

    # extra_constraints 반영
    if extra_constraints:
        # rate_limit/allow/forbid 등 플랫 키 몇 개만 예시 반영 (상황 맞게 확장 가능)
        scope = plan.get("scope", {}) or {}
        if "rate_limit" in extra_constraints:
            scope["rate_limit"] = extra_constraints["rate_limit"]
        if "allow" in extra_constraints:
            scope["allow"] = list(extra_constraints["allow"])
        if "forbid" in extra_constraints:
            scope["forbid"] = list(extra_constraints["forbid"])
        plan["scope"] = scope

    # 누락 필드 보정(최소)
    plan.setdefault("objective", f"Assess: {user_query}")
    plan.setdefault("scope", {"targets": [target_url], "allow": [target_url], "forbid": [], "rate_limit": 5})
    if not plan.get("scope", {}).get("targets"):
        plan["scope"]["targets"] = [target_url]
    plan.setdefault("attacks", [])
    plan.setdefault("templates", [])
    plan.setdefault("payloads", [])
    plan.setdefault("detection", {"signals": []})
    plan.setdefault("controls", {"guide_refs": []})

    return plan
