from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from volcenginesdkarkruntime import Ark  # 🌟 换用火山引擎官方 SDK
import json
import os
import base64
import re

# 加载 .env 密码本
load_dotenv()

app = FastAPI()

# ==========================================
# 🤖 初始化火山引擎 AI 大脑 (官方 SDK 版)
# ==========================================
ARK_API_KEY = os.getenv("ARK_API_KEY")
# 这里的 ENDPOINT_ID 就是你建好的推理接入点，比如 ep-2024xxxx
ARK_ENDPOINT_ID = os.getenv("ARK_ENDPOINT_ID") 

ai_client = None
if ARK_API_KEY and ARK_ENDPOINT_ID:
    # 使用官方 Ark 客户端
    ai_client = Ark(
        api_key=ARK_API_KEY,
        timeout=120 # 总结任务不需要太久，120秒防超时足够了
    )

# ==========================================
# 🛡️ 安全门卫 (全局拦截器)
# ==========================================
@app.middleware("http")
async def basic_auth(request: Request, call_next):
    MY_USER = os.getenv("AUTH_USER", "default_admin")
    MY_PASS = os.getenv("AUTH_PASS", "default_password_123")

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        return Response(content="Unauthorized", status_code=401, headers={"WWW-Authenticate": 'Basic realm="StudyLog Server"'})
    
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, _, password = decoded.partition(":")
        if username != MY_USER or password != MY_PASS:
            return Response(content="Wrong Username or Password", status_code=401, headers={"WWW-Authenticate": 'Basic realm="StudyLog Server"'})
    except Exception:
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="StudyLog Server"'})
        
    return await call_next(request)

# ==========================================
# 💾 数据库与常规接口
# ==========================================
DATA_FILE = "study_data.json"

class LogData(BaseModel):
    tasks: list
    memo: str = ""

@app.get("/api/data")
def get_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": [], "memo": ""}

@app.post("/api/data")
def save_data(data: LogData):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data.dict(), f, ensure_ascii=False, indent=2)
    return {"status": "success"}

# ==========================================
# ✨ AI 智能分类与总结接口
# ==========================================
class AIRequest(BaseModel):
    tasks: list

@app.post("/api/ai_summary")
def get_ai_summary(req: AIRequest):
    if not ai_client:
        return {"error": "AI 配置缺失，请检查 .env 文件"}
        
    # 只提取任务的文本发给 AI，保护隐私且节省 Token
    task_texts = [t.get("text") for t in req.tasks]
    if not task_texts:
        return {"summary": "当前还没有完成的任务哦，快去打卡吧！", "categories": []}
        
    prompt = f"""
    你是一个专业的效率分析助手。请对以下我完成的任务进行分类统计，并给出简短的鼓励。
    我的任务：{task_texts}
    
    要求：
    1. 将任务归类到合适的维度（例如：学术科研、代码开发、日常事务、运动健康等，根据任务内容动态生成，分类总数不要超过5个）。
    2. 严格返回 JSON 格式数据。
    
    必须返回以下 JSON 格式（不要包含任何其他文字或 markdown 标记）：
    {{
        "summary": "一句简短的总结鼓励（20字以内）",
        "categories": [
            {{"name": "学术科研", "value": 2}},
            {{"name": "日常事务", "value": 1}}
        ]
    }}
    """
    
    try:
        # 🌟 使用官方 SDK 的调用方式，将接入点 ID 传给 model 参数
        response = ai_client.chat.completions.create(
            model=ARK_ENDPOINT_ID,
            messages=[
                {"role": "system", "content": "你是一个只输出严格 JSON 格式的得力助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3 # 降低发散性，保证分类精准
        )
        
        # 清理可能存在的 markdown 代码块标记，提取纯 JSON
        raw_content = response.choices[0].message.content.strip()
        raw_content = re.sub(r'^```json\s*', '', raw_content)
        raw_content = re.sub(r'\s*```$', '', raw_content)
        
        return json.loads(raw_content)
    except Exception as e:
        return {"error": f"AI 分析失败: {str(e)}"}

# 挂载前端网页
app.mount("/", StaticFiles(directory="study-log", html=True), name="static")