# mcp.py
"""
오케스트레이터: URL + 사용자 쿼리를 입력받아
1) URL 수집 → 2) 임시 벡터스토어 업로드 → 3) 구조화 플랜 생성 →
4) (옵션) MCP 서버 스캔 → 5) RAG 재검증/분석 → 6) 리포트 생성
까지를 순서대로 수행합니다.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import argparse
import json

from vectorstore import ensure_persistent_store, ensure_ephemeral_store, upload_text_to_store
from fetcher import fetch_url
from planner import make_test_plan
from scanner import run_scan  # MCP 연동 (nuclei-mcp 등)
from evaluator import assess_findings
from reporter import render_markdown_report, render_json_report


@dataclass
class MCPRunConfig:
    url: str
    query: str
    mode: str = "dry-run"  # "dry-run" | "scan"
    top_k: int = 5         # File Search 상위 컨텍스트 개수
    output: str = "md"     # "md" | "json"

def run_mcp_pipeline(cfg: MCPRunConfig) -> str:
    """
    메인 파이프라인 실행.
    Returns:
        str: 최종 리포트(마크다운 or JSON 문자열)
    """
    # 1) URL 수집
    fetched = fetch_url(cfg.url)
    # fetched = {"text": str, "raw_html": str, "url": str, "meta": {...}}

    # 2) 벡터 스토어 구성
    guide_vs_id = ensure_persistent_store()  # 기존 가이드 VS (rag.ensure_vector_store() 래핑)
    url_vs_id = ensure_ephemeral_store(name="url_ephemeral")
    upload_text_to_store(url_vs_id, fetched["text"], filename="url_snapshot.txt")

    # 3) 구조화 플랜 생성 (RAG + 보안 전문가 퍼소나)
    plan = make_test_plan(
        user_query=cfg.query,
        target_url=cfg.url,
        guide_vs_id=guide_vs_id,
        url_vs_id=url_vs_id,
        top_k=cfg.top_k,
    )
    # plan: Dict(JSON) – scope, attacks, templates, rate_limit, detection, controls ...

    findings: Optional[Dict[str, Any]] = None

    # 4) (옵션) MCP 서버 스캔 실행
    if cfg.mode == "scan":
        findings = run_scan(plan)  # nuclei-mcp 등 MCP 서버 호출 → JSON 결과
        # findings 예: {"status":"completed", "findings":[...], "summary": {...}}

    # 5) RAG 재검증/분석
    assessment = assess_findings(
        findings=findings,
        url_text=fetched["text"],
        guide_vs_id=guide_vs_id,
        url_vs_id=url_vs_id,
        top_k=cfg.top_k,
    )
    # assessment: Dict(JSON) – 오탐/미탐·심각도·대응책·출처(가이드/URL)

    # 6) 리포트 생성
    if cfg.output == "json":
        return render_json_report(plan=plan, findings=findings, assessment=assessment)
    else:
        return render_markdown_report(plan=plan, findings=findings, assessment=assessment)


def main():
    parser = argparse.ArgumentParser(description="MCP Orchestrator")
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--query", required=True, help="User query (분석 포커스)")
    parser.add_argument("--mode", choices=["dry-run", "scan"], default="dry-run")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", choices=["md", "json"], default="md")
    args = parser.parse_args()

    cfg = MCPRunConfig(url=args.url, query=args.query, mode=args.mode, top_k=args.top_k, output=args.output)
    report = run_mcp_pipeline(cfg)
    print(report)


if __name__ == "__main__":
    main()
