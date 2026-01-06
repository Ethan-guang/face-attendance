import chromadb

class VectorDB:
    def __init__(self, db_path, collection_name="faces"):
        # 初始化客户端
        self.client = chromadb.PersistentClient(path=db_path)

        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )

        self.buffer = []
        self.batch_size = 50

    def buffer_add(self, id, embedding, metadata):
        """添加到缓冲区"""
        self.buffer.append({
            "id": id,
            "embedding": embedding,
            "metadata": metadata
        })
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        """将缓冲区数据写入磁盘"""
        if not self.buffer:
            return

        ids = [item['id'] for item in self.buffer]
        embeddings = [item['embedding'] for item in self.buffer]
        metadatas = [item['metadata'] for item in self.buffer]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas
        )
        self.buffer = []
        print(f"✅ 已存入 {len(ids)} 条人脸数据到数据库")

    def search(self, query_embedding, limit=1):
        """搜索最相似的人脸"""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit
        )

        parsed_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                parsed_results.append({
                    "id": results['ids'][0][i],
                    "score": 1 - results['distances'][0][i],  # 距离转相似度
                    "meta": results['metadatas'][0][i]
                })

        return parsed_results

    # 根据 staff_id 查询 ----------------------------
    def get_staff_info(self, staff_id):
        """
        根据 metadata 中的 staff_id 查询人员信息
        """
        # 使用 where 过滤器查询 metadata
        result = self.collection.get(
            where={"staff_id": staff_id}
        )

        if not result['ids']:
            return None

        # 返回找到的所有记录（可能一个人有多张脸）
        info_list = []
        for i in range(len(result['ids'])):
            info_list.append({
                "id": result['ids'][i],
                "metadata": result['metadatas'][i]
            })
        return info_list

    # 根据 staff_id 删除 -------------------------
    def delete_staff(self, staff_id):
        """
        删除指定 staff_id 的所有数据
        """
        # 先查询是否存在
        existing = self.get_staff_info(staff_id)
        if not existing:
            return 0

        # 执行删除 (根据 metadata 过滤)
        self.collection.delete(
            where={"staff_id": staff_id}
        )
        return len(existing)

    def is_id_exist(self, staff_id):
        """检查 Staff ID 是否已被占用"""
        result = self.collection.get(
            where={"staff_id": staff_id}
        )
        return len(result['ids']) > 0

    # === 新增：人脸是否重复检查 (防止一人多号) ===
    def is_face_exist(self, embedding, threshold=0.6):
        """
        检查这张脸是否已经在库里了
        返回: (是否存在, 那个人的信息)
        """
        # 搜索最相似的 1 个人
        results = self.search(embedding, limit=1)

        if results:
            top_match = results[0]
            if top_match['score'] > threshold:
                # 相似度过高，说明库里已经有这个人了
                return True, top_match

        return False, None