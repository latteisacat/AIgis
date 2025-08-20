# vectorstore.py
"""
RAG용 Vector Store 관리 유틸리티.
- 영구 스토어: 가이드 문서 (rag.ensure_vector_store 래핑)
- 임시 스토어: URL 스냅샷 등 요청 단위 자료. 컨텍스트 매니저로 자동 정리 지원.

기능:
- ensure_persistent_store() : 가이드 VS 재사용
- ensure_ephemeral_store()  : 임시 VS 생성
- upload_text_to_store()    : 텍스트 업로드 → VS에 attach
- upload_file_to_store()    : 파일 경로 업로드 → VS에 attach
- wait_ingestion_complete() : 간단 폴링로 인덱싱 대기
- list_store_files()        : VS에 연결된 파일 조회
- delete_store_files()      : VS에 연결된 파일 모두 제거
- delete_store()            : VS 자체 삭제
- EphemeralVectorStore      : with 문으로 생성/정리 자동화
"""

from __future__ import annotations
import os
import time
from typing import Optional, List, Dict, Any, Iterable

from config import client
from rag import ensure_vector_store as _ensure_persistent  # 영구 스토어 래핑


# ===== 영구 스토어 (가이드) =====
def ensure_persistent_store() -> str:
    """
    가이드 문서용 영구 벡터스토어 ID 반환.
    내부적으로 rag.ensure_vector_store() 재사용.
    """
    vs_id = _ensure_persistent()
    print(f"[VS] persistent store ready: {vs_id}")
    return vs_id


# ===== 임시 스토어 =====
def ensure_ephemeral_store(name: str = "url_ephemeral") -> str:
    """
    요청 단위 임시 벡터스토어 생성 후 id 반환.
    """
    vs = client.vector_stores.create(name=name)
    print(f"[VS] ephemeral store created: id={vs.id}, name={name}")
    return vs.id


# ===== 파일 업로드 & 연결 =====
def upload_text_to_store(vs_id: str, text: str, filename: str = "snippet.txt") -> str:
    """
    텍스트를 임시 파일로 저장 → Files API 업로드 → 해당 VS에 attach.
    Returns: file_id
    """
    tmp_path = f".tmp_{filename}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        return upload_file_to_store(vs_id, tmp_path, delete_local=True)
    finally:
        # upload_file_to_store가 예외로 끝나도 로컬 임시 파일은 제거
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def upload_file_to_store(vs_id: str, file_path: str, delete_local: bool = False) -> str:
    """
    로컬 파일 경로를 Files API로 업로드 후 VS에 attach.
    Returns: file_id
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    with open(file_path, "rb") as f:
        up = client.files.create(file=f, purpose="assistants")
    client.vector_stores.files.create(vector_store_id=vs_id, file_id=up.id)
    print(f"[VS] file attached: vs_id={vs_id}, file_id={up.id}, name={os.path.basename(file_path)}")

    if delete_local:
        try:
            os.remove(file_path)
        except Exception:
            pass

    return up.id


# ===== 인덱싱 대기(간단 폴링) =====
def wait_ingestion_complete(vs_id: str, timeout_sec: int = 30, poll_interval: float = 1.5) -> None:
    """
    단순 폴링으로 인덱싱 완료까지 잠시 대기.
    - OpenAI File Search는 비동기로 청킹/임베딩/색인을 수행하므로
      대량 업로드 직후 바로 검색하면 누락될 수 있음.
    - 공식 상태 API가 안정화되면 그에 맞춰 변경 권장.
    """
    # 현재는 보수적으로 time.sleep 반복
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        # (선택) list_store_files로 파일 수 변화 감지/지연 로그 등 가능
        time.sleep(poll_interval)
    print(f"[VS] ingestion wait done (vs_id={vs_id}, waited≈{timeout_sec}s)")


# ===== 조회/삭제 =====
def list_store_files(vs_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    VS에 연결된 파일 목록을 간단 조회.
    참고: 페이징/정렬 등은 필요 시 확장.
    """
    items: List[Dict[str, Any]] = []
    # SDK에 따라 pagination 객체가 다를 수 있어 간단히 page size만 제한
    page = client.vector_stores.files.list(vector_store_id=vs_id, limit=limit)
    for f in getattr(page, "data", []) or []:
        items.append({"id": f.id, "created_at": getattr(f, "created_at", None)})
    print(f"[VS] list files: vs_id={vs_id}, count={len(items)}")
    return items


def delete_store_files(vs_id: str, file_ids: Iterable[str]) -> None:
    """
    VS에 연결된 파일들을 제거(분리)합니다.
    Files API의 실제 파일 삭제 수명주기는 별도이며,
    여기서는 벡터 스토어에서만 분리됩니다.
    """
    cnt = 0
    for fid in file_ids:
        try:
            client.vector_stores.files.delete(vector_store_id=vs_id, file_id=fid)
            cnt += 1
        except Exception as e:
            print(f"[VS][WARN] delete file failed: vs_id={vs_id}, file_id={fid}, err={e}")
    print(f"[VS] detached files: vs_id={vs_id}, count={cnt}")


def delete_store(vs_id: str) -> None:
    """
    벡터 스토어 자체를 삭제합니다.
    (주의: 영구 스토어는 삭제하지 마세요)
    """
    try:
        client.vector_stores.delete(vector_store_id=vs_id)
        print(f"[VS] store deleted: {vs_id}")
    except Exception as e:
        print(f"[VS][WARN] store delete failed: vs_id={vs_id}, err={e}")


# ===== 컨텍스트 매니저: 임시 스토어 자동 정리 =====
class EphemeralVectorStore:
    """
    with EphemeralVectorStore() as vs_id:
        # vs_id 사용 (업로드/검색)
    # 블록 종료 시 파일 분리/스토어 삭제 수행(옵션)
    """

    def __init__(self, name: str = "url_ephemeral", delete_on_exit: bool = True,
                 detach_files_on_exit: bool = True):
        self.name = name
        self.delete_on_exit = delete_on_exit
        self.detach_files_on_exit = detach_files_on_exit
        self.vs_id: Optional[str] = None
        self._attached_files: List[str] = []

    def __enter__(self) -> str:
        self.vs_id = ensure_ephemeral_store(self.name)
        return self.vs_id

    def __exit__(self, exc_type, exc, tb):
        if not self.vs_id:
            return False

        try:
            if self.detach_files_on_exit:
                files = list_store_files(self.vs_id, limit=200)
                file_ids = [f["id"] for f in files]
                if file_ids:
                    delete_store_files(self.vs_id, file_ids)
            if self.delete_on_exit:
                delete_store(self.vs_id)
        finally:
            self.vs_id = None
        # 예외 전파는 기본 동작(필요 시 False/True 조절)
        return False

    # 업로드 헬퍼 (컨텍스트 내에서 호출 시 파일 id 추적)
    def upload_text(self, text: str, filename: str = "snippet.txt") -> str:
        if not self.vs_id:
            raise RuntimeError("EphemeralVectorStore not initialized")
        fid = upload_text_to_store(self.vs_id, text, filename)
        self._attached_files.append(fid)
        return fid

    def upload_file(self, path: str) -> str:
        if not self.vs_id:
            raise RuntimeError("EphemeralVectorStore not initialized")
        fid = upload_file_to_store(self.vs_id, path, delete_local=False)
        self._attached_files.append(fid)
        return fid
