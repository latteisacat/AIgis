# gpt_main.py
from rag import rag_query

def main():
    print("File Search RAG 데모 (종료: exit/quit)")
    while True:
        q = input("\n질문을 입력하세요: ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        try:
            ans = rag_query(q, top_k=5, use_baseline=True)
            print("\n=== 답변 ===")
            print(ans)
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    main()
