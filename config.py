# config.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in .env (set OPENAI_API_KEY=...)")
os.environ["OPENAI_API_KEY"] = api_key

# ✅ 모델 중앙관리 (환경변수로 오버라이드 가능)
# 기본값은 현재 프로젝트에서 쓰는 응답 모델
MODEL_RESPONSES = os.getenv("OPENAI_MODEL_RESPONSES", "gpt-5-mini")

# (선택) 역할별로 분리하고 싶다면 주석 해제해 사용
# MODEL_PLANNER   = os.getenv("OPENAI_MODEL_PLANNER",   MODEL_RESPONSES)
# MODEL_EVALUATOR = os.getenv("OPENAI_MODEL_EVALUATOR", MODEL_RESPONSES)

client = OpenAI()
