# vectorstore.py
"""
RAG용 벡터 스토어를 관리합니다.
- 영구 스토어: 가이드 문서 (rag.ensure_vector_store() 재사용)
- 임시 스토어: URL 스냅샷 등 요청 단위 자료
"""
import os
from typing import Optional
from openai import OpenAI
from config import client
from rag import ensure_vector_store as _ensure_persistent  # 기존 함수 재사용:contentReference[oaicite:3]{index=3}

def ensure_persistent_store() -> str:
    """
    가이드 문서용 영구 벡터스토어 ID 반환.
    기존 rag.ensure_vector_store()를 래핑.
    """
    return _ensure_persistent()

def ensure_ephemeral_store(name: str = "url_ephemeral") -> str:
    """
    요청 단위 임시 벡터 스토어 생성 후 id 반환.
    TODO: 수명주기(삭제 등) 정책 고려.
    """
    vs = client.vector_stores.create(name=name)
    print(f"[DEBUG] VectorStore created: id={vs.id}, name={name}")
    return vs.id

def upload_text_to_store(vs_id: str, text: str, filename: str = "snippet.txt") -> str:
    """
    텍스트를 임시 파일로 저장 → Files API 업로드 → 해당 VS에 attach.
    Returns: file_id
    """
    tmp_path = f".tmp_{filename}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    with open(tmp_path, "rb") as f:
        up = client.files.create(file=f, purpose="assistants")
        print(f"[DEBUG] File uploaded: id={up.id}, name={filename}, size={len(text)} chars")
    os.remove(tmp_path)
    client.vector_stores.files.create(vector_store_id=vs_id, file_id=up.id)
    print(f"[DEBUG] File attached to VS: vs_id={vs_id}, file_id={up.id}")
    return up.id
