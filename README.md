# 🛡️ AIgis

보안 전문가(Persona)를 기반으로 **OpenAI Responses API + File Search**를 활용한 RAG 데모 프로젝트입니다.
PDF 문서를 `Data/` 폴더에 넣으면, 자동으로 벡터 스토어에 업로드되고 검색된 컨텍스트를 바탕으로 답변합니다.
`prompts/security_rag_baseline.txt`에 정의된 **Baseline Prompt**를 통해 항상 보안 전문가 시각에서 답변하도록 설계되었습니다.

---

## 📂 프로젝트 구조

```
.
├─ config.py                  # OpenAI 클라이언트 공용 관리
├─ rag.py                     # File Search 기반 RAG 로직
├─ gpt_main.py                # CLI 실행 스크립트
├─ prompts/
│   └─ security_rag_baseline.txt   # 보안 전문가용 Baseline Prompt
└─ Data/                      # 분석할 PDF 파일 저장 경로
```

---

## 🚀 설치 & 실행

### 1. 의존성 설치

```bash
pip install "openai>=1.40.0"
```

### 2. 환경 변수 설정
.env 파일 내부 API 키 수정
```bash
OPENAI_API_KEY="your_api_key_here"
```

### 3. PDF 파일 준비

분석하고 싶은 PDF 파일을 `Data/` 폴더에 넣습니다.

### 4. 실행

```bash
python gpt_main.py
```

---

## 🧑‍💻 사용 방법

* CLI 실행 후 질문을 입력하면, `Data/` 폴더의 PDF들을 검색하여 답변을 생성합니다.
* 언제든 `exit` 또는 `quit`를 입력하면 종료됩니다.

예시:

```
질문을 입력하세요: 이 문서에서 제시하는 네트워크 보안 권고사항은?
```

---

## 📝 Baseline Prompt (보안 전문가)

* `prompts/security_rag_baseline.txt`에서 관리합니다.
* 기본 Persona: **Security Specialist**
* 답변 원칙:

  * 컨텍스트 기반 (추측 금지)
  * 보안 시각 반영 (위협/취약점/방어)
  * 출처 표시
  * 구조화된 답변 (요약 → 분석 → 보안적 시사점 → 출처)

---

## ⚙️ 주요 특징

* OpenAI **Responses API + File Search** → 관리형 RAG 구현
* `config.py`에서 클라이언트 공용 관리
* 별도의 **Baseline Prompt 파일**로 Persona 제어
* 추후 확장:

  * 파일명/페이지/근거 자동 인용
  * 모드 전환 (예: Compliance, Risk Analyst)
  * 스트리밍 출력 지원
