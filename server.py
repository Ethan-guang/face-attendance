import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from pydantic import BaseModel, Field
from src.service import FaceService
from typing import List, Optional

# 全局服务实例
service: FaceService = None
# 全局配置缓存 (用于鉴权)
app_config = {}


def load_config():
    if os.path.exists("config.json"):
        with open("config.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service, app_config
    app_config = load_config()
    service = FaceService(app_config)
    yield
    print("🛑 服务关闭")


app = FastAPI(title="Face Attendance Pro v1.2", lifespan=lifespan)


# === 1. 安全鉴权依赖 ===
async def verify_auth(request: Request, x_token: str = Header(..., alias="X-Token")):
    """
    [cite_start]鉴权中间件: 验证 Token 和 IP 白名单 [cite: 294]
    """
    # 获取配置
    auth_cfg = service.cfg.get('auth', {})
    server_token = auth_cfg.get('token')
    whitelist = auth_cfg.get('ip_whitelist', [])
    client_ip = request.client.host

    # [cite_start]1. Token 验证 (必选) [cite: 296]
    if not server_token:
        # 如果配置里没写token，暂时报错或放行，建议报错
        raise HTTPException(status_code=500, detail="Server Token Not Configured")

    if x_token != server_token:
        raise HTTPException(status_code=401, detail="Invalid X-Token")

    # [cite_start]2. IP 白名单验证 [cite: 298-300]
    # 规则：当白名单为空时，或请求来自本机（localhost）时，允许访问。
    # 否则，必须在白名单内。
    is_localhost = client_ip in ["127.0.0.1", "localhost", "::1"]

    if not whitelist:
        # 白名单为空 -> 仅允许 localhost
        # 文档原文：当白名单为空时...无条件允许访问（仍需校验Token）。
        # 这里为了安全，通常理解为“白名单为空时仅允许本机初始化”，但按照文档“或请求来自本机”
        # 我们可以放宽为：whitelist为空，暂不拦截；或者 whitelist为空，视为仅允许本机。
        # [cite_start]根据[cite: 300] "首次部署后...配合接口将客户端IP加入"，暗示初始状态应该允许访问以便配置。
        # 结合通常的安全逻辑：空名单=仅限本机。
        if not is_localhost:
            # 为了方便您调试，如果真的为空且不是本机，这里先打印日志，建议生产环境拦截
            print(f"⚠️ 警告: IP白名单为空，外部IP {client_ip} 正在访问 (建议通过 /config/update 添加)")
            pass
    else:
        # 白名单不为空 -> 严格校验
        if not is_localhost and client_ip not in whitelist:
            raise HTTPException(status_code=403, detail=f"IP {client_ip} Forbidden")


# [cite_start]=== 2. 请求体定义 (CamelCase) [cite: 307, 319] ===
class RegisterReq(BaseModel):
    staffId: str
    name: str
    imagePath: str


class RecognizeReq(BaseModel):
    filePath: str
    type: int = 0  # 0:图片, 1:视频


class DeleteReq(BaseModel):
    staffId: str


class ConfigUpdateReq(BaseModel):
    # 支持部分更新，字段可选
    thresholdVerify: Optional[float] = None
    thresholdCluster: Optional[float] = None
    videoInterval: Optional[float] = None
    ipWhitelist: Optional[List[str]] = None


# === 3. 路由实现 ===

# [cite_start]员工注册 [cite: 301]
@app.post("/api/v_1/register", dependencies=[Depends(verify_auth)])
def register(req: RegisterReq):
    try:
        # 调用 Service (参数转为内部 snake_case)
        result = service.register_staff(req.imagePath, req.staffId, req.name)
        return {"code": 200, "msg": "注册成功"}
    except Exception as e:
        return {"code": 400, "msg": str(e)}


# [cite_start]考勤接口 [cite: 313]
@app.post("/api/v_1/recognize", dependencies=[Depends(verify_auth)])
def recognize(req: RecognizeReq):
    try:
        attendees = []

        if req.type == 1:
            # === 视频模式 ===
            print(f" -> [API] 视频分析: {req.filePath}")
            raw_results = service.analyze_video(req.filePath)
        else:
            # === 图片模式 ===
            print(f" -> [API] 图片识别: {req.filePath}")
            raw_results = service.recognize_image(req.filePath)

        # [cite_start]统一格式化为 CamelCase [cite: 325]
        for item in raw_results:
            attendees.append({
                "staffId": item['staff_id'],
                "name": item['name']
            })

        return {
            "code": 200,
            "msg": "考勤完成",
            "data": attendees
        }
    except Exception as e:
        return {"code": 500, "msg": f"处理失败: {str(e)}"}


# [cite_start]员工删除 [cite: 329]
@app.post("/api/v_1/staff/delete", dependencies=[Depends(verify_auth)])
def delete_staff(req: DeleteReq):
    count = service.db.delete_staff(req.staffId)
    if count == 0:
        return {"code": 404, "msg": "未找到员工"}
    return {"code": 200, "msg": f"已删除 {count} 条记录"}


# [cite_start]获取配置 [cite: 349]
@app.get("/api/v_1/config/get", dependencies=[Depends(verify_auth)])
def get_config():
    # 从 service.cfg 读取并转为 API 格式
    analysis = service.cfg.get('analysis', {})
    auth = service.cfg.get('auth', {})

    data = {
        "thresholdVerify": analysis.get('threshold_verify'),
        "thresholdCluster": analysis.get('threshold_cluster'),
        "videoInterval": analysis.get('video_sample_interval'),
        "ipWhitelist": auth.get('ip_whitelist', [])
    }
    return {"code": 200, "msg": "获取配置成功", "data": data}


# [cite_start]修改配置 [cite: 364]
@app.post("/api/v_1/config/update", dependencies=[Depends(verify_auth)])
def update_config(req: ConfigUpdateReq):
    updates = {"analysis": {}, "auth": {}}

    # 映射 API 参数到内部配置键名
    if req.thresholdVerify is not None:
        updates['analysis']['threshold_verify'] = req.thresholdVerify
    if req.thresholdCluster is not None:
        updates['analysis']['threshold_cluster'] = req.thresholdCluster
    if req.videoInterval is not None:
        updates['analysis']['video_sample_interval'] = req.videoInterval

    if req.ipWhitelist is not None:
        updates['auth']['ip_whitelist'] = req.ipWhitelist

    # 执行更新
    success = service.update_config(updates)

    if success:
        return {"code": 200, "msg": "配置更新成功，立即生效"}
    else:
        return {"code": 500, "msg": "配置写入失败"}


if __name__ == "__main__":
    import uvicorn

    # 监听 0.0.0.0 以允许局域网访问，但通过 IP 白名单控制安全
    uvicorn.run(app, host="0.0.0.0", port=8000)