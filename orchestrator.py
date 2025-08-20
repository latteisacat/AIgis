# orchestrator.py (최종 반영)
import asyncio
from config import client, MODEL_RESPONSES
from rag import rag_query, load_baseline_prompt
from mcp_llm import run as mcp_run

MODEL = MODEL_RESPONSES

async def analyze(url: str, user_prompt: str):
    sys_prompt = load_baseline_prompt()

    # Step1: Prompt → Keyword 추출
    kw_resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "너는 보안 전문가다. 반드시 핵심 키워드만 콤마(,)로 구분해서 출력해라. 설명하지 마라. sqli, xss, csrf 등과 같은 취약점 키워드를 추출한다."},
            {"role": "user", "content": f"다음 사용자 요청에서 보안 취약점 관련 핵심 키워드만 뽑아줘:\n\n{user_prompt}"}
        ]
    )

    raw_keywords = kw_resp.choices[0].message.content.strip()
    # 불필요한 줄바꿈 제거
    keywords = [kw.strip() for kw in raw_keywords.replace("\n", ",").split(",") if kw.strip()]
    print(f"\n=== 🔑 추출된 키워드 ===\n{keywords}")

    # Step2: 정적 분석 (Spider)
    print("\n=== 🕷️ 정적 분석 시작 ===")
    static_results = await mcp_run(url, keywords, None, "http://localhost:7456/sse", do_active=False)

    # Step3: 동적 분석 여부 확인
    dynamic_results = {}
    yn = input("\n동적 분석(Active Scan)을 진행할까요? (y/n): ").lower()
    if yn == "y":
        print("\n=== ⚡ 동적 분석 실행 ===")
        dynamic_results = await mcp_run(url, keywords, None, "http://localhost:7456/sse", do_active=True)
    else:
        print("동적 분석을 건너뜁니다.")

    # Step4: 최종 RAG 분석 (정적+동적 결과 통합)
    print("\n=== 📊 RAG 분석 결과 생성 ===\n")
    merged_results = {**(static_results or {}), **(dynamic_results or {})}
    final_ans = rag_query(url, user_prompt, merged_results)
    print(final_ans)


def main():
    print("보안 취약점 자동 분석 오케스트레이터 (종료: exit/quit)")
    while True:
        url = input("\n대상 URL 입력: ").strip()
        if url.lower() in {"exit", "quit"}:
            break
        q = input("분석 Prompt 입력: ").strip()
        asyncio.run(analyze(url, q))


if __name__ == "__main__":
    main()
