# reporter.py
"""
최종 리포트를 Markdown 또는 JSON 포맷으로 생성합니다.
"""
from typing import Dict, Any
import json

def render_markdown_report(plan: Dict[str, Any],
                           findings: Dict[str, Any] | None,
                           assessment: Dict[str, Any]) -> str:
    """
    Markdown 보고서 생성.
    """
    md = []
    md.append("## ✅ 요약")
    md.append(f"- 목적: {plan.get('objective')}")
    md.append(f"- 판단: {assessment.get('verdict')}\n")

    md.append("## 📄 세부 분석")
    if findings:
        md.append(f"- 스캔 상태: {findings.get('status')}")
        md.append(f"- 탐지 요약: {findings.get('summary')}")
    md.append(f"- 설명: {assessment.get('explanation')}\n")

    md.append("## 🔐 보안적 시사점 / 권고")
    for m in assessment.get("mitigations", []):
        md.append(f"- {m}")
    md.append("")

    md.append("## 📂 출처")
    for c in assessment.get("citations", []):
        if c.get("page"):
            md.append(f"- {c['source']} / p.{c['page']}")
        elif c.get("path"):
            md.append(f"- {c['source']} {c['path']}")
        else:
            md.append(f"- {c['source']}")
    return "\n".join(md)

def render_json_report(plan: Dict[str, Any],
                       findings: Dict[str, Any] | None,
                       assessment: Dict[str, Any]) -> str:
    """
    JSON 보고서 생성(문자열).
    """
    payload = {
        "plan": plan,
        "findings": findings,
        "assessment": assessment
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
