"""API 연결 진단. CHECK_API.bat 으로 실행한다."""
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
key_path = os.path.join(here, "api_key.txt")

print("[1] 키 파일:", key_path)
if os.path.exists(key_path):
    raw = open(key_path, encoding="utf-8", errors="replace").read()
    key = raw.strip().strip('"').strip("'")
    print("    존재함. 길이:", len(key), "| 시작:", key[:10] + "...", "| sk-ant- 로 시작:", key.startswith("sk-ant-"))
    if not key:
        print("    -> 파일이 비어 있습니다. SET_API_KEY.bat 으로 다시 넣으세요.")
else:
    print("    없음. SET_API_KEY.bat 을 실행해서 키를 넣으세요.")
    key = ""

env = os.environ.get("ANTHROPIC_API_KEY")
print("[2] 환경변수 ANTHROPIC_API_KEY:", "있음" if env else "없음")
key = env or key
if not key:
    print("-> 키가 없어서 여기서 끝.")
    sys.exit(1)

print("[3] anthropic 패키지:", end=" ")
try:
    import anthropic
    print("설치됨", anthropic.__version__)
except ImportError:
    print("없음 -> START.bat 을 다시 실행하거나: python -m pip install anthropic")
    sys.exit(1)

model = os.environ.get("CAT_MODEL", "")
if not model and os.path.exists(os.path.join(here, "model.txt")):
    model = open(os.path.join(here, "model.txt"), encoding="utf-8").read().strip()
model = model or "claude-opus-5-5"
print(f"[4] 모델 {model} 로 테스트 호출...")
client = anthropic.Anthropic(api_key=key)
try:
    r = client.messages.create(model=model, max_tokens=50, messages=[{"role": "user", "content": "냐옹 한 마디만 해줘"}])
    text = "".join(b.text for b in r.content if b.type == "text")
    print("    성공:", text)
    print("-> API 연결 정상. 고양이를 껐다 켜면 대화가 됩니다.")
except anthropic.AuthenticationError as e:
    print("    인증 실패 (401): 키가 틀렸거나 만료됨.", e.message)
except anthropic.PermissionDeniedError as e:
    print("    권한 없음 (403):", e.message)
except anthropic.NotFoundError as e:
    print(f"    모델 없음 (404): 이 계정에서 {model} 을 못 씁니다. SET_MODEL.bat 으로 다른 모델을 고르세요.", e.message)
except anthropic.RateLimitError as e:
    print("    한도 초과 (429):", e.message)
except anthropic.APIStatusError as e:
    print(f"    API 오류 ({e.status_code}):", e.message)
    if e.status_code == 400:
        print("    -> 크레딧이 없거나 결제 설정이 안 된 경우가 흔합니다. console.anthropic.com 에서 Billing 확인.")
except anthropic.APIConnectionError as e:
    print("    연결 실패: 인터넷/방화벽/프록시 문제.", e)
input("\n아무 키나 누르면 닫힙니다...")
