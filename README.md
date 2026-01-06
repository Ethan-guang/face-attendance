# Face Attendance Pro (人脸考勤系统) v1.2

基于 InsightFace 和 ChromaDB 的高性能人脸考勤后端系统。支持**图片/视频流识别**、**员工管理**、**动态配置**以及**企业级安全鉴权**。

---

## ✨ 核心功能

* **人脸底库管理**：支持员工人脸注册、更新（自动覆盖）、删除。
* **多模态考勤**：
    * 📸 **图片模式**：上传单张图片进行打卡。
    * 📹 **视频模式**：自动对视频流抽帧、聚类分析，排除误检。
* **企业级鉴权**：
    * **Token 验证**：静态 Header 令牌认证。
    * **IP 白名单**：支持动态配置允许访问的 IP（支持冷启动 Localhost 信任）。
* **高性能架构**：
    * API 层：FastAPI (异步/线程池并发)。
    * 计算层：InsightFace (ONNX Runtime)。
    * 存储层：ChromaDB (向量数据库) + 本地文件存储。

---

## 🛠️ 目录结构

```text
face-attendance/
├── config.json              # 核心配置文件 (Token/白名单/阈值)
├── main.py                  # 本地 CLI 工具 (测试用)
├── server.py                # API 服务器启动入口
├── requirements.txt         # 依赖列表
├── my_models/               # InsightFace 模型文件夹 (需自行下载)
├── src/                     # 核心源码
│   ├── core.py              # AI 引擎封装
│   ├── database.py          # 向量数据库操作
│   ├── service.py           # 业务逻辑层
│   └── storage.py           # 文件路径管理
└── data/                    # 数据存储 (自动生成)
    ├── images/staff/        # 员工底照
    ├── inputs/              # 接收的上传文件
    └── vector_db/           # ChromaDB 数据库文件
```
## 🚀 快速开始

### 1. 环境准备

- Python 3.10+
- 推荐使用虚拟环境（`venv` 或 `conda`）

```bash
# 安装依赖
pip install -r requirements.txt
```
### 2. 模型下载（重要！）

本项目依赖 **buffalo_l** 人脸识别模型。

- 如果第一次运行时报错，请**手动下载模型**并解压到 `my_models/` 目录  
- 或由程序**自动下载**（取决于网络情况）
### 3. 启动 API 服务

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```
启动成功后，访问 Swagger 文档页面进行测试：  
👉 http://127.0.0.1:8000/docs
## 🔐 鉴权说明（Authentication）

所有 API 请求（除静态资源外）**必须**包含以下 Header：

- **Key**: `X-Token`
- **Value**: `sk-admin-123`（默认值，可在 `config.json` 中修改）

### IP 白名单策略

- **初始状态**：白名单为空，仅允许 `Localhost (127.0.0.1)` 访问  
- **添加 IP**：请在服务器本机调用  
  `/api/v_1/config/update` 接口，将您的客户端 IP 加入白名单
## 📡 API 接口速查

所有接口前缀均为 `/api/v_1`。

| 功能       | 方法 | URL             | 说明                         |
|------------|------|------------------|------------------------------|
| 注册员工   | POST | /register        | 录入人脸（ID 重复自动更新） |
| 考勤识别   | POST | /recognize       | 支持 `type=0`（图片）或 `1`（视频） |
| 删除员工   | POST | /staff/delete    | 物理删除数据                 |
| 获取配置   | GET  | /config/get      | 查看阈值和白名单             |
| 修改配置   | POST | /config/update   | 热更新配置（立即生效）       |
## 💻 本地 CLI 工具（测试用）

如果你不想启动 Web 服务，可以直接使用 `main.py` 在终端测试效果（绕过鉴权）。
### 1. 注册员工

```bash
# 将 jack.jpg 放入 data/images/staff/ 目录后运行：
python main.py reg -p "jack.jpg" -i "1001" -n "Jack"
```
### 2. 识别测试

```bash
# 将 test.jpg 放入 data/inputs/ 目录后运行：
python main.py run -p "test.jpg"
```
## ⚙️ 配置文件（config.json）

```json
{
  "auth": {
    "token": "sk-admin-123",
    "ip_whitelist": []
  },
  "analysis": {
    "threshold_verify": 0.60,
    "threshold_cluster": 0.75,    
    "video_sample_interval": 1.0
  },
  "model": {
    "name": "buffalo_l",
    "det_size": 640,
    "providers": ["CPUExecutionProvider"]
  }
}
```
## ⚠️ 注意事项

- **显卡加速**：如果要在 NVIDIA 显卡上运行，请将 `requirements.txt` 中的 `onnxruntime` 修改为 `onnxruntime-gpu`，并在 `config.json` 中确认 `providers` 列表首位包含 `CUDAExecutionProvider`。

- **数据备份**：`data/` 目录存放了实际的向量数据库和图片，请定期备份；同时建议在 `.gitignore` 中忽略该目录，避免仓库过大。
## 📄 License

MIT

