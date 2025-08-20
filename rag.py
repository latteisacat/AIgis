# rag.py (최종 분석 결과를 Markdown 섹션으로 정리)
import os
import glob
import time
import requests
import json
from typing import List, Optional, Dict, Any
from config import client, MODEL_RESPONSES

DATA_DIR = "Data"
VSTORE_NAME = "my_pdfs_vector_store"
VS_ID_CACHE = ".vector_store_id"
MODEL = MODEL_RESPONSES
PROMPT_PATH = "prompts/security_rag_baseline.txt"

MCP_URL = "http://localhost:8931/sse"   # Playwright MCP 서버 (SSE 지원)


# ===== Baseline Prompt Loader =====
def load_baseline_prompt(path: str = PROMPT_PATH) -> str:
    if not os.path.exists(path):
        return (
            "You are a helpful RAG assistant with a security specialist persona. "
            "Use only the provided context to answer."
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ===== Vector Store 관리 =====
def _load_cached_vs_id() -> Optional[str]:
    if os.path.exists(VS_ID_CACHE):
        return open(VS_ID_CACHE, "r", encoding="utf-8").read().strip() or None
    return None

def _save_cached_vs_id(vs_id: str) -> None:
    with open(VS_ID_CACHE, "w", encoding="utf-8") as f:
        f.write(vs_id)

def _create_vector_store() -> str:
    vs = client.vector_stores.create(name=VSTORE_NAME)
    _save_cached_vs_id(vs.id)
    return vs.id

def _upload_pdfs_to_files_api(pdf_paths: List[str]) -> List[str]:
    file_ids = []
    for p in pdf_paths:
        with open(p, "rb") as f:
            up = client.files.create(file=f, purpose="assistants")
            file_ids.append(up.id)
    return file_ids

def _attach_files_to_vector_store(vs_id: str, file_ids: List[str]) -> None:
    for fid in file_ids:
        client.vector_stores.files.create(vector_store_id=vs_id, file_id=fid)

def _wait_ingestion(vs_id: str, timeout_s: int = 3) -> None:
    time.sleep(timeout_s)


def ensure_vector_store() -> str:
    vs_id = _load_cached_vs_id()
    if vs_id:
        return vs_id

    vs_id = _create_vector_store()
    pdfs = sorted(glob.glob(os.path.join(DATA_DIR, "**/*.pdf"), recursive=True))
    if not pdfs:
        raise RuntimeError(f"Data/ 폴더에 PDF가 없습니다: {os.path.abspath(DATA_DIR)}")

    file_ids = _upload_pdfs_to_files_api(pdfs)
    _attach_files_to_vector_store(vs_id, file_ids)
    _wait_ingestion(vs_id)
    return vs_id


# ===== RAG Query (정적/동적 결과 통합) =====
def rag_query(url: str, query: str, mcp_results: Optional[Dict[str, Any]] = None, top_k: int = 5) -> str:
    """
    url: 분석 대상 URL
    query: 사용자 Prompt
    mcp_results: mcp_llm.py에서 수집된 정적/동적 분석 결과
    """
    vs_id = ensure_vector_store()
    sys_prompt = load_baseline_prompt()

    # 1. RAG 단계
    rag_resp = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"대상 URL: {url}\n사용자 요청: {query}\n\n"
                                        f"이 요청을 분석하기 위해 필요한 취약점 점검 방법을 문서에서 찾아라."}
        ],
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vs_id],
            "max_num_results": top_k
        }],
    )
    rag_answer = rag_resp.output_text

    # 2. MCP 결과 요약 섹션 만들기
    static_summary = "정적 분석 결과 없음"
    dynamic_summary = "동적 분석 결과 없음"

    if mcp_results:
        if "urls_sample" in mcp_results or "sites" in mcp_results:
            static_summary = json.dumps({k: mcp_results[k] for k in mcp_results if k in ("sites", "urls_sample")}, 
                                        ensure_ascii=False, indent=2)
        if "alerts" in mcp_results:
            dynamic_summary = json.dumps({"alerts": mcp_results["alerts"]}, ensure_ascii=False, indent=2)

    # 3. 최종 요청 메시지
    final_input = f"""
# 🔎 최종 보안 분석 보고서

## 1. 사용자 요청
{query}

## 2. 정적 분석 결과 (Spider 기반)
{static_summary}

## 3. 동적 분석 결과 (Active Scan 기반)
{dynamic_summary}

## 4. RAG 기반 취약점 가이드
{rag_answer}

---

위 내용을 종합하여:
- 대상 URL의 취약 여부를 평가하고
- 발견된 취약점이 있으면 공격 시나리오를 설명하며
- 구체적이고 실무적인 패치 방법을 제시하고
- 우선순위 기반의 보안 권고안을 작성하라.
"""

    final_resp = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": final_input}
        ]
    )

    print("\n=== ✅ 최종 통합 분석 결과 ===")
    return final_resp.output_text
