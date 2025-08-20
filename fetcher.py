# fetcher.py
"""
URL을 수집하여 보안 분석에 유용한 텍스트와 메타데이터를 리턴합니다.

기능:
- robots.txt 준수(가능한 한 보수적으로)
- HTTP GET (헤더/타임아웃/리다이렉트 제한/사이즈 제한)
- HTML -> 텍스트 추출 (trafilatura 우선, 실패 시 Readability/BeautifulSoup fallback)
- 폼/코드블록/링크 등 보안 관련 아티팩트 추출
- 메타데이터: 상태코드, MIME, 최종 URL, 컨텐츠 길이, 수집시각 등

반환 형식:
{
  "text": str,         # 정제된 본문 텍스트
  "raw_html": str,     # 원본 HTML (최대 max_bytes 한도)
  "url": str,          # 최종 URL
  "meta": {...},       # 상태/헤더/robots/타임스탬프 등
  "artifacts": {...}   # forms/code_blocks/links 등
}
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import re
import time
import json
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from urllib import robotparser

# 선택적 고급 추출기들
try:
    import trafilatura
except Exception:
    trafilatura = None

USER_AGENT = "SecRAGBot/1.0 (+https://example.local)"
DEFAULT_TIMEOUT = 12
MAX_BYTES = 2 * 1024 * 1024  # 2MB 상한(과도한 메모리 사용 방지)
ALLOW_REDIRECTS = True
MAX_REDIRECTS = 5


def _check_robots_allow(url: str, user_agent: str = USER_AGENT, timeout: int = 6) -> Optional[bool]:
    """
    robots.txt를 확인하여 크롤링 허가 여부를 반환.
    - True: 허가
    - False: 불허
    - None: 판단 불가(타임아웃/실패 시 보수적 처리 위해 None 반환)
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        # requests로 긁어서 넣는 편이 타임아웃 제어가 쉬움
        r = requests.get(robots_url, headers={"User-Agent": user_agent}, timeout=timeout)
        if r.status_code >= 400:
            return None
        rp.parse(r.text.splitlines())
        return rp.can_fetch(user_agent, url)
    except Exception:
        return None


def _stream_limited_get(url: str,
                        headers: Optional[Dict[str, str]] = None,
                        timeout: int = DEFAULT_TIMEOUT,
                        allow_redirects: bool = ALLOW_REDIRECTS) -> Tuple[requests.Response, bytes]:
    """
    최대 MAX_BYTES만 메모리에 적재하도록 스트리밍 GET.
    """
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko,en;q=0.9",
        **(headers or {})
    }
    with requests.get(
        url,
        headers=hdrs,
        timeout=timeout,
        allow_redirects=allow_redirects,
        stream=True,
    ) as resp:
        resp.raise_for_status()
        buf = bytearray()
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                buf.extend(chunk)
                if len(buf) > MAX_BYTES:
                    break
        return resp, bytes(buf)


def _html_to_text_with_trafilatura(html: str, base_url: str) -> Optional[str]:
    if not trafilatura:
        return None
    try:
        # favor precision: 표/목록 보존에 유리
        extracted = trafilatura.extract(
            html,
            url=base_url,
            include_tables=True,
            include_links=True,
            no_fallback=False,
            favor_recall=False,
            favor_precision=True,
        )
        if extracted and extracted.strip():
            return extracted.strip()
    except Exception:
        return None
    return None


def _html_to_text_fallback(html: str) -> str:
    """
    Readability 대용으로 BeautifulSoup 기반 간단 추출.
    - 스크립트/스타일 제거
    - <pre>/<code>/<table>는 원문을 최대한 보존
    """
    soup = BeautifulSoup(html, "lxml")

    # 스크립트/스타일 제거
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # 코드/프리블록은 별도로 수집하고 본문에도 포함
    code_blocks = []
    for tag in soup.find_all(["pre", "code"]):
        text = tag.get_text("\n", strip=True)
        if text and len(text) > 0:
            code_blocks.append(text)

    # 테이블 텍스트 단순화(셀을 탭/개행으로)
    for table in soup.find_all("table"):
        for br in table.find_all("br"):
            br.replace_with("\n")
        table_text = []
        for row in table.find_all("tr"):
            cols = [col.get_text(" ", strip=True) for col in row.find_all(["td", "th"])]
            if cols:
                table_text.append("\t".join(cols))
        if table_text:
            table.replace_with("\n".join(table_text))

    # 나머지 본문
    text = soup.get_text("\n", strip=True)
    if code_blocks:
        text = text + "\n\n" + "\n\n".join([f"```code\n{cb}\n```" for cb in code_blocks])

    # 공백 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_artifacts(html: str, base_url: str) -> Dict[str, Any]:
    """
    폼/코드블록/링크 등 보안 관련 아티팩트를 수집.
    """
    soup = BeautifulSoup(html, "lxml")

    # forms
    forms = []
    for form in soup.find_all("form"):
        method = (form.get("method") or "GET").upper()
        action = form.get("action") or ""
        action_abs = urljoin(base_url, action) if action else base_url
        inputs = []
        for inp in form.find_all(["input", "textarea", "select"]):
            inputs.append({
                "name": inp.get("name"),
                "type": inp.get("type"),
                "value": inp.get("value")
            })
        forms.append({
            "method": method,
            "action": action_abs,
            "inputs": inputs
        })

    # code blocks
    code_blocks = []
    for tag in soup.find_all(["pre", "code"]):
        text = tag.get_text("\n", strip=True)
        if text:
            code_blocks.append(text[:5000])  # 과도한 길이 제한

    # links
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        href_abs = urljoin(base_url, href)
        links.append({"href": href_abs, "text": (a.get_text(strip=True) or "")[:200]})

    return {
        "forms": forms[:200],
        "code_blocks": code_blocks[:200],
        "links": links[:1000],
    }


def fetch_url(url: str) -> Dict[str, Any]:
    """
    URL을 가져와 텍스트/아티팩트/메타를 반환.
    실패 시 예외를 던지지 않고, 가능한 많은 정보를 반환합니다.
    """
    started = time.time()
    robots_allowed = _check_robots_allow(url)
    # 로봇 파일 판정에 실패(None)한 경우엔 안전을 위해 경고만 남기고 진행(정책에 맞게 조정)
    meta: Dict[str, Any] = {
        "requested_url": url,
        "robots_allowed": robots_allowed,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    raw_html = ""
    final_url = url
    status = None
    content_type = None
    text_out = ""
    artifacts: Dict[str, Any] = {"forms": [], "code_blocks": [], "links": []}

    try:
        resp, body = _stream_limited_get(url)
        status = resp.status_code
        content_type = resp.headers.get("Content-Type")
        final_url = str(resp.url)
        meta["headers"] = dict(resp.headers)
        meta["content_length"] = len(body)
        raw_html = body.decode(resp.encoding or "utf-8", errors="replace")

        # 본문 추출 (trafilatura -> fallback)
        text_out = (_html_to_text_with_trafilatura(raw_html, final_url) or "").strip()
        if not text_out:
            text_out = _html_to_text_fallback(raw_html)

        # 아티팩트 수집
        artifacts = _extract_artifacts(raw_html, final_url)

    except requests.RequestException as e:
        meta["error"] = f"request_error: {e.__class__.__name__}"
    except Exception as e:
        meta["error"] = f"unhandled_error: {e.__class__.__name__}"

    meta.update({
        "status": status,
        "content_type": content_type,
        "final_url": final_url,
        "elapsed_sec": round(time.time() - started, 3),
    })

    # 텍스트 길이 제한(벡터스토어 업로드/토큰 사용 보호)
    if len(text_out) > 400_000:
        text_out = text_out[:400_000] + "\n...[TRUNCATED]"

    return {
        "text": text_out or "",
        "raw_html": raw_html or "",
        "url": final_url,
        "meta": meta,
        "artifacts": artifacts
    }
