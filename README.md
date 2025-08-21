![캡처](AIgis_Logo.png)

# 🛡️ AIgis

보안 전문가(Persona)를 기반으로 *OpenAI Responses API + File Search (RAG) + MCP(ZAP 연동)를 활용한 보안 취약점 자동 분석 프로젝트입니다.
PDF 문서를 기반으로 보안 가이드를 검색(RAG)하고, 웹 애플리케이션에 대해 정적/동적 분석(MCP + ZAP)을 수행하여 최종적으로 전문가 수준의 보고서를 생성합니다.

---

## 📂 프로젝트 구조

```
.
├─ config.py                  # OpenAI 클라이언트 및 모델 설정
├─ rag.py                     # File Search 기반 RAG 로직
├─ mcp_llm.py                 # ZAP 기반 정적/동적 웹 취약점 분석 (MCP 연동)
├─ orchestrator.py            # 전체 오케스트레이션 (URL 입력 → 키워드 추출 → 정적/동적 분석 → RAG 결합)
├─ gpt_main.py                # 단순 RAG CLI 실행 스크립트
├─ prompts/
│   └─ security_rag_baseline.txt   # 보안 전문가용 Baseline Prompt
└─ Data/                      # 분석할 PDF 파일 저장 경로
```

---

## 🚀 설치 & 실행

### 1. 의존성 설치

```bash
pip install "openai>=1.40.0" mcp httpx httpx-sse python-dotenv
```

### 2. 환경 변수 설정

`.env` 파일 내부 API 키 수정:

```bash
OPENAI_API_KEY="your_api_key_here"
```

---

## 🔧 ZAP + MCP 서버 실행 준비

본 프로젝트의 **정적/동적 분석** 기능은 `mcp-zap-server`와 ZAP Docker 컨테이너가 필요합니다.

### 1. mcp-zap-server 설치

```bash
git clone https://github.com/dtkmn/mcp-zap-server.git
cd mcp-zap-server
export LOCAL_ZAP_WORKPLACE_FOLDER=$(pwd)/zap-workplace
```

### 2. ZAP 실행 (Docker)

```bash
docker run --name zap -u zap -d -p 8090:8090 \
  --add-host=host.docker.internal:host-gateway \
  zaproxy/zap-stable \
  zap.sh -daemon -host 0.0.0.0 -port 8090 \
  -config 'api.disablekey=true' \
  -config 'api.addrs.addr.name=.*' -config 'api.addrs.addr.regex=true'
```

### 3. MCP ZAP Server 실행 (Docker)

```bash
docker build -t mcp-zap-server:latest .
docker run -d --name mcp-zap-server \
  -p 7456:7456 \
  --add-host=host.docker.internal:host-gateway \
  -e ZAP_API_URL=host.docker.internal \
  -e ZAP_API_PORT=8090 \
  mcp-zap-server:latest
```

---

## 🧑‍💻 사용 방법

### 1. 단순 RAG 실행

PDF 기반 보안 가이드 검색만 수행:

```bash
python gpt_main.py
```

### 2. 오케스트레이터 실행 (권장)

URL 기반 정적/동적 분석 + RAG 결합:

```bash
python orchestrator.py
```

실행 흐름:

1. URL 입력
2. Prompt 입력 → 주요 보안 키워드 자동 추출
3. 정적 분석(Spider) 수행
4. 동적 분석 여부를 사용자에게 확인 후 실행
5. 최종적으로 RAG 기반 가이드와 통합하여 보고서 출력

---

## 📝 Baseline Prompt (보안 전문가)

* `prompts/security_rag_baseline.txt`에서 관리
* 기본 Persona: **Security Specialist**
* 답변 원칙:

  * 컨텍스트 기반 (추측 금지)
  * 보안 전문가 시각 반영 (위협/취약점/방어)
  * 출처 표시
  * 구조화된 보고서 (요약 → 상세 분석 → 보안적 시사점 → 출처)

---

## ⚙️ 주요 특징

* OpenAI **Responses API + File Search** → 관리형 RAG 구현
* `mcp-zap-server` + ZAP 연동 → 실제 웹 애플리케이션 취약점 분석 (Spider/Active Scan)
* `orchestrator.py` → 키워드 추출 + 정적/동적 분석 + RAG 결합
* 출력 보고서 → **Markdown 기반, 보안 전문가 시각의 구조화된 결과**
