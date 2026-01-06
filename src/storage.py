import os
from pathlib import Path

class StorageManager:
    def __init__(self, cfg):
        # 1. 设定根目录
        self.base_root = Path(cfg['storage']['base_root']).resolve()
        self.paths_map = cfg['storage']['paths']

        # 2. 创建必要的文件夹
        if not self.base_root.exists():
            print(f"[Storage] 基准目录不存在，正在创建: {self.base_root}")
            os.makedirs(self.base_root, exist_ok=True)

        for category, rel_path in self.paths_map.items():
            full_path = self.base_root / rel_path
            os.makedirs(full_path, exist_ok=True)

    def get_path(self, category: str, filename: str = "") -> str:
        """
        获取文件的绝对路径，并进行安全检查
        :param category: 资源类型 (如 'inputs', 'staff_images')
        :param filename: 相对路径/文件名 (如 '2023/001.jpg')
        """
        if category not in self.paths_map:
            raise ValueError(f"未定义的资源类型: {category}")

        target_dir = (self.base_root / self.paths_map[category]).resolve()

        # 如果 filename 为空，只返回目录路径
        if not filename:
            return str(target_dir)

        final_path = (target_dir / filename).resolve()

        # 拦截
        if not str(final_path).startswith(str(target_dir)):
            raise PermissionError(f"非法路径访问拦截: {filename}")

        return str(final_path)
