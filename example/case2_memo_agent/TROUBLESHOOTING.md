# 트러블슈팅 가이드

## Python 3.14 호환성 문제

### 오류 메시지
```
pydantic.v1.errors.ConfigError: unable to infer type for attribute "description"
```

### 원인
- Python 3.14는 아직 프리뷰 버전입니다
- LangFuse가 내부적으로 사용하는 Pydantic v1이 Python 3.14를 완전히 지원하지 않습니다
- 경고 메시지: "Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater"

### 해결 방법 1: Python 3.13 사용 (권장)

#### 1-1. 현재 Python 버전 확인
```bash
python3 --version
python3.13 --version
```

#### 1-2. Python 3.13 설치 (없는 경우)
Ubuntu/Debian:
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv
```

#### 1-3. 기존 가상환경 삭제 및 재생성
```bash
cd /home/gomsonixx/Workspace/f-lab-study/example/case2_memo_agent

# 기존 가상환경 삭제
rm -rf .venv

# Python 3.13으로 가상환경 재생성
uv venv --python 3.13

# 또는 직접 지정
uv venv --python python3.13

# 패키지 재설치
uv sync
```

#### 1-4. 실행
```bash
uv run python memo_agent.py
```

### 해결 방법 2: LangFuse 없이 실행

LangFuse 통합을 일시적으로 비활성화하고 나중에 Python 버전을 변경할 수 있습니다.

#### 2-1. .env에서 LangFuse 키 제거 또는 주석 처리
```bash
# LangFuse Observability (Optional)
#LANGFUSE_HOST=https://cloud.langfuse.com
#LANGFUSE_PUBLIC_KEY=pk-lf-2be9e4e1-1e67-4c46-b20a-8029eef2cee4
#LANGFUSE_SECRET_KEY=sk-lf-cd4fac2a-906d-4fd4-9c68-55ee4908126d
```

#### 2-2. 실행
```bash
uv run python memo_agent.py
```

출력:
```
ℹ️  LangFuse 비활성화 (환경 변수 미설정)
✅ LangGraph 메모 에이전트가 준비되었습니다.
```

### 해결 방법 3: 대체 Observability 도구 사용

Python 3.14를 계속 사용하면서 다른 관찰성 도구를 사용할 수 있습니다:

#### 3-1. LangSmith (LangChain 공식)
```bash
# pyproject.toml에 추가
dependencies = [
    # ...
    "langsmith>=0.1.0",
]
```

```python
# memo_agent.py
from langsmith import Client

# 환경 변수
# LANGSMITH_API_KEY=...
# LANGSMITH_PROJECT=memo-agent
```

#### 3-2. OpenTelemetry
```bash
dependencies = [
    # ...
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-instrumentation-langchain>=0.1.0",
]
```

## 권장 사항

**프로덕션 환경에서는 Python 3.13 이하를 사용하세요.**

Python 3.14는 2025년 10월에 정식 릴리스될 예정이며, 현재는:
- 많은 라이브러리가 완전히 지원하지 않음
- 프리뷰/베타 버전으로 불안정할 수 있음
- LangChain 생태계가 아직 완전히 테스트되지 않음

## 현재 설정 확인

### Python 버전
```bash
python3 --version
uv python list
```

### 가상환경 Python 버전
```bash
cd /home/gomsonixx/Workspace/f-lab-study/example/case2_memo_agent
.venv/bin/python --version
```

### UV로 특정 Python 버전 설치
```bash
# 사용 가능한 Python 버전 확인
uv python list

# Python 3.13 설치
uv python install 3.13

# Python 3.13으로 가상환경 생성
uv venv --python 3.13
```

## 추가 참고 사항

### LangFuse GitHub Issues
이 문제는 LangFuse 프로젝트에서도 인지하고 있을 가능성이 높습니다:
- https://github.com/langfuse/langfuse-python/issues

### Pydantic v1 → v2 마이그레이션
LangFuse가 Pydantic v2로 완전히 마이그레이션하면 이 문제가 해결될 것입니다.

### 임시 회피책 (비추천)
환경 변수로 경고를 무시할 수 있지만, 근본적인 해결책은 아닙니다:
```bash
export PYTHONWARNINGS="ignore::UserWarning"
```
