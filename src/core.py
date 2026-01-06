from insightface.app import FaceAnalysis

class FaceEngine:
    def __init__(self, model_name='buffalo_l', root='my_models', providers=['CPUExecutionProvider'], ctx_id=0,
                 det_size=(640, 640)):
        """
        :param root: 模型根目录，对应 config 中的 model.root
        """
        if isinstance(det_size, int):
            det_size = (det_size, det_size)

        # 传入 root，指定模型存放位置
        self.app = FaceAnalysis(name=model_name, root=root, providers=providers)
        self.app.prepare(ctx_id=ctx_id, det_size=det_size)

    def extract(self, img_data):
        if img_data is None:
            return []

        # 如果图片无法读取，返回空列表而不是报错
        try:
            faces = self.app.get(img_data)
        except Exception as e:
            print(f" AI 引擎推理出错: {e}")
            return []

        results = []
        for face in faces:
            results.append({
                "bbox": face.bbox,
                "kps": face.kps,
                "score": face.det_score,
                "embedding": face.embedding
            })
        return results