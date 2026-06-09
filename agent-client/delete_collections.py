"""
删除 Qdrant 中的旧集合（解决向量维度不匹配问题）
"""
import requests
import sys

QDRANT_URL = "http://localhost:6333"

collections_to_delete = [
    "agent_memories_v4",
    "agent_memories_v4_entities"
]

def delete_collections():
    """删除指定的集合"""
    for collection_name in collections_to_delete:
        url = f"{QDRANT_URL}/collections/{collection_name}"
        print(f"正在删除集合: {collection_name}...")
        
        try:
            response = requests.delete(url)
            if response.status_code == 200:
                print(f"✓ 成功删除集合: {collection_name}")
                print(f"  响应: {response.json()}")
            elif response.status_code == 404:
                print(f"⚠ 集合不存在（可能已删除）: {collection_name}")
            else:
                print(f"✗ 删除失败: {collection_name}, 状态码: {response.status_code}")
                print(f"  响应: {response.text}")
        except Exception as e:
            print(f"✗ 删除集合时出错: {collection_name}, 错误: {e}")
    
    print("\n完成！请重启 Python 程序，它会自动创建新集合。")

if __name__ == "__main__":
    delete_collections()
