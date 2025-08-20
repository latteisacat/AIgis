from rag import rag_query

def main():
    print("보안 RAG + MCP 테스트 (종료: exit/quit)")
    while True:
        url = input("\n대상 URL 입력: ").strip()
        if url.lower() in {"exit", "quit"}:
            break
        q = input("분석 쿼리 입력: ").strip()
        try:
            ans = rag_query(url, q)
            print("\n=== 분석 결과 ===")
            print(ans)
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    main()