import cv2
import numpy as np
import os
import json
from .core import FaceEngine
from .database import VectorDB
from .storage import StorageManager


class FaceService:
    def __init__(self, cfg):
        self.cfg = cfg
        print(" -> [Service] 正在启动业务服务...")

        # 管家初始化
        self.storage = StorageManager(cfg)

        # DB走管家的路径
        db_path = self.storage.get_path("vector_db")
        self.db = VectorDB(
            db_path=db_path,
            collection_name=cfg['database']['collection_name'],
        )

        # 初始化AI模型
        self.engine = FaceEngine(
            model_name=cfg['model']['name'],
            root=cfg['model']['root'],
            providers=cfg['model'].get('providers', ['CPUExecutionProvider']),
            det_size=cfg['model']['det_size'],
        )

    # ============ 注册 (覆盖更新模式) =====================
    def register_staff(self, rel_path: str, staff_id: str, name: str):
        full_path = self.storage.get_path("staff_images", rel_path)

        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"文件不存在: {full_path}")

        # [cite_start]逻辑检查：如果 ID 已存在，先删除旧数据 (实现覆盖更新) [cite: 312]
        if self.db.is_id_exist(staff_id):
            print(f" -> [Service] ID {staff_id} 已存在，正在执行覆盖更新...")
            self.db.delete_staff(staff_id)

        img = cv2.imread(full_path)
        if img is None:
            raise ValueError("无法读取图片文件")

        faces = self.engine.extract(img)
        if not faces:
            raise ValueError("未检测到人脸")

        # 取最大人脸
        faces.sort(key=lambda x: (x['bbox'][2] - x['bbox'][0]) * (x['bbox'][3] - x['bbox'][1]), reverse=True)
        target_face = faces[0]

        # 查重 (可选：如果需要防止同一个人换个ID注册，可以保留此逻辑；如果允许同一人多号，可注释)
        # is_exist, exist_info = self.db.is_face_exist(target_face['embedding'], threshold=0.7)
        # if is_exist:
        #     raise ValueError(f"人脸已存在: {exist_info['meta']['name']} (ID: {exist_info['meta']['staff_id']})")

        # 入库
        unique_id = f"staff_{staff_id}_{name}"  # 这里的 unique_id 是 ChromaDB 内部用的
        meta = {
            "staff_id": staff_id,
            "name": name,
            "file_name": os.path.basename(rel_path)
        }
        self.db.buffer_add(unique_id, target_face['embedding'], meta)
        self.db.flush()

        return {"staff_id": staff_id, "name": name, "status": "success"}

    # ============ 图片考勤 =====================
    def recognize_image(self, rel_path: str):
        full_path = self.storage.get_path("inputs", rel_path)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"文件不存在: {full_path}")

        img = cv2.imread(full_path)
        if img is None:
            raise ValueError("图片损坏或格式不支持")

        faces = self.engine.extract(img)
        results = []

        threshold = self.cfg['analysis']['threshold_verify']

        for face in faces:
            search_res = self.db.search(face['embedding'], limit=1)

            if search_res:
                top = search_res[0]
                if top['score'] > threshold:
                    match = {
                        "staff_id": top['meta']['staff_id'],
                        "name": top['meta']['name'],
                        "confidence": round(float(top['score']), 4)
                    }
                    results.append(match)

        return results

    # ============ 视频分析 =====================
    def analyze_video(self, rel_path: str):
        full_path = self.storage.get_path("inputs", rel_path)
        cap = cv2.VideoCapture(full_path)

        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频: {full_path}")

        local_clusters = []
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 视频采样间隔
        interval = self.cfg['analysis'].get('video_sample_interval', 1.0)
        stride = int(fps * interval) or 1

        current_frame = 0
        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            ret, frame = cap.read()
            if not ret: break

            h, w = frame.shape[:2]
            # 缩放加速
            if w > 640: frame = cv2.resize(frame, (640, int(640 * h / w)))

            faces = self.engine.extract(frame)
            for face in faces:
                self._update_clusters(local_clusters, face['embedding'])

            current_frame += stride
            if current_frame >= total_frames: break

        cap.release()

        # 核验聚类结果
        final_list = []
        verify_threshold = self.cfg['analysis']['threshold_verify']
        min_samples = self.cfg['analysis']['min_cluster_samples']

        for cluster in local_clusters:
            if cluster['count'] < min_samples: continue

            res = self.db.search(cluster['center'], limit=1)
            if res and res[0]['score'] > verify_threshold:
                top = res[0]
                final_list.append({
                    "staff_id": top['meta']['staff_id'],
                    "name": top['meta']['name']
                })

        # 简单去重
        unique_list = list({v['staff_id']: v for v in final_list}.values())
        return unique_list

    def _update_clusters(self, clusters, emb):
        best_sim, best_idx = -1, -1
        cluster_threshold = self.cfg['analysis']['threshold_cluster']

        for i, c in enumerate(clusters):
            sim = np.dot(emb, c['center']) / (np.linalg.norm(emb) * np.linalg.norm(c['center']))
            if sim > best_sim: best_sim, best_idx = sim, i

        if best_idx != -1 and best_sim > cluster_threshold:
            c = clusters[best_idx]
            # 移动平均更新中心
            c['center'] = (c['center'] * c['count'] + emb) / (c['count'] + 1)
            c['count'] += 1
        else:
            clusters.append({'center': emb, 'count': 1})

    # ============ 配置热更新 =====================
    def update_config(self, updates: dict):
        """
        更新内存配置并持久化到文件
        updates: 包含 analysis 或 auth 的部分更新字典
        """
        # 1. 更新内存中的 analysis 配置
        if 'analysis' in updates:
            for k, v in updates['analysis'].items():
                if k in self.cfg['analysis']:
                    self.cfg['analysis'][k] = v

        # 2. 更新内存中的 auth 配置 (如白名单)
        if 'auth' in updates:
            for k, v in updates['auth'].items():
                if k in self.cfg['auth']:
                    self.cfg['auth'][k] = v

        # 3. 持久化到 config.json
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(self.cfg, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 配置写入失败: {e}")
            return False