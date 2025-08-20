# mcp_llm.py (리팩토링)
import os, re, json, time, asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from openai import OpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-5-mini")
MCP_SSE_URL    = os.getenv("MCP_SSE_URL", "http://localhost:7456/sse")

POLL_INTERVAL  = float(os.getenv("ZAP_POLL_INTERVAL", "2.0"))
SPIDER_TIMEOUT = int(os.getenv("ZAP_SPIDER_TIMEOUT_SECS", "600"))
ASCAN_TIMEOUT  = int(os.getenv("ZAP_ASCAN_TIMEOUT_SECS", "1200"))

SYSTEM_FOR_SUMMARY = """당신은 웹 애플리케이션 보안 분석 전문가입니다.  
입력으로 ZAP 스캔 결과(알림, URL/사이트 스니펫, 리포트 경로)와 사용자가 지정한 Focus 목록을 받습니다.  

[역할]
- 보안 전문가로서 개발자/운영자가 바로 활용할 수 있는 간결한 보고서를 작성합니다.
- 불필요한 대화체나 장황한 설명은 하지 않습니다.
- 모든 출력은 Markdown 형식으로, 규격화된 구조를 따릅니다.

[출력 규격]
# 📌 보안 분석 요약

## ✅ 요약 (3줄 이내)
- 핵심 취약점 현황 요약 (예: "고위험 2건, 중위험 3건 발견")

## 📄 상세 결과
- **High 위험**
  - [취약점명]: 영향 URL (간단 설명)
- **Medium 위험**
  - [취약점명]: 영향 URL (간단 설명)
- **Low 위험**
  - [취약점명]: 영향 URL (간단 설명)

## 🔐 권고 사항
- 취약점별 주요 대응책 (항목별 1~2줄)
- Focus 목록과 연계된 보완 포인트 명시

---

[작성 원칙]
1. 반드시 위 구조를 유지합니다.
2. 각 항목은 1~2줄 이내로 요약합니다.
3. 구체적이지 않은 문구("조치 필요")는 피하고, 실무적 권고(예: Prepared Statement 적용, CSP 추가)를 제시합니다.
4. 대화체, 불필요한 서두/결론 문구는 절대 포함하지 않습니다.
당신은 웹 애플리케이션 보안 분석 전문가입니다.  
입력으로 ZAP 스캔 결과(알림, URL/사이트 스니펫, 리포트 경로)와 사용자가 지정한 Focus 목록을 받습니다.  

[역할]
- 보안 전문가로서 개발자/운영자가 바로 활용할 수 있는 간결한 보고서를 작성합니다.
- 불필요한 대화체나 장황한 설명은 하지 않습니다.
- 모든 출력은 Markdown 형식으로, 규격화된 구조를 따릅니다.

[출력 규격]
# 📌 보안 분석 요약

## ✅ 요약 (3줄 이내)
- 핵심 취약점 현황 요약 (예: "고위험 2건, 중위험 3건 발견")

## 📄 상세 결과
- **High 위험**
  - [취약점명]: 영향 URL (간단 설명)
- **Medium 위험**
  - [취약점명]: 영향 URL (간단 설명)
- **Low 위험**
  - [취약점명]: 영향 URL (간단 설명)

## 🔐 권고 사항
- 취약점별 주요 대응책 (항목별 1~2줄)
- Focus 목록과 연계된 보완 포인트 명시

---

[작성 원칙]
1. 반드시 위 구조를 유지합니다.
2. 각 항목은 1~2줄 이내로 요약합니다.
3. 구체적이지 않은 문구("조치 필요")는 피하고, 실무적 권고(예: Prepared Statement 적용, CSP 추가)를 제시합니다.
4. 대화체, 불필요한 서두/결론 문구는 절대 포함하지 않습니다.
5. Focus 목록에 명시된 항목과 관련된 취약점은 반드시 언급합니다.
"""

# --- 기존 유틸 함수 (생략 없이 유지) ---
def blocks_to_text(blocks) -> str:
    parts=[]
    for b in blocks:
        if getattr(b,"type","") == "text":
            parts.append(getattr(b,"text","") or "")
        else:
            d=getattr(b,"data",None)
            if d is not None:
                try: parts.append(json.dumps(d, ensure_ascii=False))
                except Exception: parts.append(str(d))
    return "\n".join([p for p in parts if p]).strip()

def parse_scan_id(text: str) -> Optional[str]:
    m = re.search(r'\b(scanId|scan)\b\D+(\d+)', text, re.I)
    return m.group(2) if m else None

def parse_percent(text: str) -> Optional[int]:
    m = re.search(r'"status"\s*:\s*"?(?P<p>\d{1,3})"?', text, re.I)
    if m: return max(0, min(100, int(m.group("p"))))
    m = re.search(r'(\d{1,3})\s*%', text)
    if m: return max(0, min(100, int(m.group(1))))
    m = re.search(r'\b(\d{1,3})\b', text)
    if m: return max(0, min(100, int(m.group(1))))
    return None

def pick_key(props: Dict[str, Any], *cands):
    props = props or {}
    lower = {k.lower(): k for k in props.keys()}
    for cand in cands:
        cl = cand.lower()
        for lk, orig in lower.items():
            if cl in lk:
                return orig
    return next(iter(props.keys())) if props else None

async def call_tool(session: ClientSession, name: str, args: Dict[str, Any]) -> str:
    res = await session.call_tool(name, args)
    return blocks_to_text(res.content) or "(empty)"

# --- Spider (정적 분석) ---
async def run_spider(session: ClientSession, target_url: str) -> Dict[str, Any]:
    results = {"target": target_url}
    tl = await session.list_tools()
    schema = {t.name: (t.inputSchema or {"type":"object","properties":{}}) for t in tl.tools}
    props  = {n: (schema[n].get("properties") or {}) for n in schema}

    if "zap_spider" not in schema or "zap_spider_status" not in schema:
        raise RuntimeError("MCP server does not expose spider tools")

    sp_p = props["zap_spider"]
    sp_url_key = pick_key(sp_p, "url", "targetUrl", "baseUrl", "base", "target")
    spider_txt = await call_tool(session, "zap_spider", {sp_url_key: target_url})
    sid = parse_scan_id(spider_txt)
    if not sid:
        raise RuntimeError(f"Spider did not return scanId: {spider_txt}")

    st_p = props["zap_spider_status"]
    sid_key = pick_key(st_p, "scanId", "scan", "id")

    t0 = time.time()
    while True:
        stat = await call_tool(session, "zap_spider_status", {sid_key: sid})
        pct = parse_percent(stat) or 0
        if pct >= 100: break
        if time.time()-t0 > SPIDER_TIMEOUT: raise TimeoutError("Spider timed out")
        await asyncio.sleep(POLL_INTERVAL)

    # 사이트/URL 샘플 수집
    if "zap_sites" in schema:
        results["sites"] = await call_tool(session, "zap_sites", {})
    if "zap_urls" in schema:
        up = props["zap_urls"]
        base_key = pick_key(up, "baseUrl", "base", "url")
        results["urls_sample"] = await call_tool(session, "zap_urls", {base_key: target_url})
    return results

# --- Active Scan (동적 분석) ---
async def run_active_scan(session: ClientSession, target_url: str) -> Dict[str, Any]:
    results = {"target": target_url}
    tl = await session.list_tools()
    schema = {t.name: (t.inputSchema or {"type":"object","properties":{}}) for t in tl.tools}
    props  = {n: (schema[n].get("properties") or {}) for n in schema}

    if "zap_active_scan" not in schema or "zap_active_scan_status" not in schema:
        raise RuntimeError("MCP server does not expose active scan tools")

    as_p = props["zap_active_scan"]
    as_url_key = pick_key(as_p, "url", "targetUrl", "baseUrl", "base", "target")
    as_args = {as_url_key: target_url}
    rec_key = pick_key(as_p, "recurse", "recursive")
    if rec_key: as_args[rec_key] = True

    ascan_txt = await call_tool(session, "zap_active_scan", as_args)
    aid = parse_scan_id(ascan_txt)
    if not aid:
        raise RuntimeError(f"Active scan did not return scanId: {ascan_txt}")

    ast_p = props["zap_active_scan_status"]
    aid_key = pick_key(ast_p, "scanId", "scan", "id")

    t1 = time.time()
    while True:
        stat = await call_tool(session, "zap_active_scan_status", {aid_key: aid})
        pct = parse_percent(stat) or 0
        if pct >= 100: break
        if time.time()-t1 > ASCAN_TIMEOUT: raise TimeoutError("Active scan timed out")
        await asyncio.sleep(POLL_INTERVAL)

    if "zap_alerts" in schema:
        ap = props["zap_alerts"]
        base_key = pick_key(ap, "base", "baseUrl", "url")
        results["alerts"] = await call_tool(session, "zap_alerts", {base_key: target_url})

    return results

# --- 최종 실행 함수 ---
async def run(target_url: str, focus: Optional[str], openapi_url: Optional[str], sse_url: str, do_active: bool = True):
    if not OPENAI_API_KEY: raise SystemExit("Set OPENAI_API_KEY")
    client = OpenAI(api_key=OPENAI_API_KEY)

    async with sse_client(url=sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Spider 먼저
            artifacts = await run_spider(session, target_url)

            # Active Scan은 옵션
            if do_active:
                active_results = await run_active_scan(session, target_url)
                artifacts.update(active_results)

    # Advisory 생성
    payload = f"Target: {target_url}\nFocus: {focus}\n\nArtifacts:\n{json.dumps(artifacts, indent=2, ensure_ascii=False)}"
    messages = [
        {"role": "system", "content": SYSTEM_FOR_SUMMARY},
        {"role": "user", "content": payload},
    ]
    resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
    print("\n==== Advisory ====\n")
    print(resp.choices[0].message.content or "(no advisory text produced)")
    return artifacts

