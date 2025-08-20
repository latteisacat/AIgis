# scanner.py
"""
MCP 서버(nuclei-mcp 등)를 호출하여 취약점 스캔을 수행합니다.
실제 구현은 mcp_client.py를 통해 서버와 통신하세요.
"""
from typing import Dict, Any, Optional
from mcp_client import call_mcp_action

def run_scan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    plan(JSON)을 MCP 서버 호출 파라미터로 변환하여 스캔 실행.
    Returns: findings JSON
    TODO:
    - nuclei-mcp 기준: action="scan", params={target_url, templates, rate_limit, ...}
    - 안전 모드/화이트리스트/승인 토큰 등 가드레일 포함
    """
    params = {
        "target_url": plan["scope"]["targets"][0],
        "templates": plan.get("templates", []),
        "rate_limit": plan.get("scope", {}).get("rate_limit", 5),
        "severity_filter": ["high", "critical"],
    }
    result = call_mcp_action(action="scan", params=params)
    return result or {"status": "skipped", "findings": [], "summary": {}}
