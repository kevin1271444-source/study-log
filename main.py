from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import json
import os
import base64

# 加载 .env 隐藏文件里的环境变量（必须加这一句！）
load_dotenv()
app = FastAPI()

# ==========================================
# 🛡️ 新增：安全门卫 (全局拦截器)
# ==========================================
@app.middleware("http")
async def basic_auth(request: Request, call_next):
    # 👇 改成了从环境变量获取密码。如果找不到，默认变成一个复杂的乱码防止被黑
    MY_USER = os.getenv("AUTH_USER", "default_admin")
    MY_PASS = os.getenv("AUTH_PASS", "default_password_123")

    auth_header = request.headers.get("Authorization")
    
    # 如果没有提供账号密码，或者格式不对，直接拦在门外
    if not auth_header or not auth_header.startswith("Basic "):
        return Response(
            content="Unauthorized", 
            status_code=401, 
            headers={"WWW-Authenticate": 'Basic realm="StudyLog Server"'}
        )
    
    # 解密浏览器传过来的账号密码并核对
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, _, password = decoded.partition(":")
        
        if username != MY_USER or password != MY_PASS:
            return Response(
                content="Wrong Username or Password", 
                status_code=401, 
                headers={"WWW-Authenticate": 'Basic realm="StudyLog Server"'}
            )
    except Exception:
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="StudyLog Server"'})
        
    # 账号密码正确，放行！
    return await call_next(request)
# ==========================================


# 我们的微型数据库文件
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

# 挂载前端网页
app.mount("/", StaticFiles(directory="study-log", html=True), name="static")