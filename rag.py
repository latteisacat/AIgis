# rag.py
import os
import glob
import time
from typing import List, Optional
from config import client, MODEL_RESPONSES

DATA_DIR = "Data"
VSTORE_NAME = "my_pdfs_vector_store"
VS_ID_CACHE = ".vector_store_id"
MODEL = MODEL_RESPONSES
PROMPT_PATH = "prompts/security_rag_baseline.txt"  # 기본 프롬프트 파일 경로


# ===== Baseline Prompt Loader =====
def load_baseline_prompt(path: str = PROMPT_PATH) -> str:
    """보안 전문가용 baseline 프롬프트 파일을 읽어서 문자열 반환"""
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
    time.sleep(timeout_s)  # 데모용 간단 대기


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


# ===== RAG Query =====
def rag_query(query: str, top_k: int = 5, use_baseline: bool = True) -> str:
    vs_id = ensure_vector_store()
    sys_prompt = load_baseline_prompt() if use_baseline else ""
    print(f"[DEBUG] RAG request: model={MODEL_RESPONSES}, query={query}, VS={vs_id}")
    resp = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": query}
        ],
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vs_id],
            "max_num_results": top_k
        }],
    )
    print(f"[DEBUG] RAG response: id={resp.id}, tokens={resp.usage}, text={resp.output_text[:200]}...")
    return resp.output_text
