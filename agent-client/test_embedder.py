"""
嵌入器测试脚本

测试mem0配置、记忆功能、完整流程验证
"""

import sys
import os
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config, ConfigValidator


def test_mem0_config() -> dict:
    """
    测试mem0配置生成
    
    Returns:
        dict: 配置测试结果
    """
    try:
        # 加载配置
        config = Config.from_env()
        
        # 生成mem0配置
        mem0_config = Config.get_mem0_config()
        
        return {
            "success": True,
            "config_loaded": True,
            "deepseek_model": config.DEEPSEEK_MODEL,
            "deepseek_base_url": config.DEEPSEEK_BASE_URL,
            "qdrant_host": config.QDRANT_HOST,
            "qdrant_port": config.QDRANT_PORT,
            "collection_name": config.MEM0_COLLECTION_NAME,
            "gpu_available": config.GPU_AVAILABLE,
            "device": config.DEVICE,
            "mem0_config_keys": list(mem0_config.keys()),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_local_embedder_config() -> dict:
    """
    测试本地嵌入模型配置
    
    Returns:
        dict: 配置测试结果
    """
    try:
        config = Config.from_env()
        embedder_config = Config.get_local_embedder_config()
        
        return {
            "success": True,
            "model_name": embedder_config["embedder"]["config"]["model_name"],
            "device": embedder_config["embedder"]["config"]["device"],
            "normalize_embeddings": embedder_config["embedder"]["config"]["normalize_embeddings"],
            "gpu_acceleration": config.GPU_AVAILABLE,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_qdrant_connection() -> dict:
    """
    测试Qdrant连接
    
    Returns:
        dict: 连接测试结果
    """
    try:
        config = Config.from_env()
        
        # 尝试导入qdrant_client
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError:
            return {
                "success": False,
                "error": "qdrant_client未安装，请运行: pip install qdrant-client",
                "qdrant_installed": False
            }
        
        # 尝试连接
        client = QdrantClient(
            host=config.QDRANT_HOST,
            port=config.QDRANT_PORT,
            timeout=5.0
        )
        
        # 获取集合列表
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        # 检查目标集合是否存在
        target_collection = config.MEM0_COLLECTION_NAME
        collection_exists = target_collection in collection_names
        
        return {
            "success": True,
            "qdrant_installed": True,
            "host": config.QDRANT_HOST,
            "port": config.QDRANT_PORT,
            "collection_count": len(collection_names),
            "collections": collection_names[:5] if len(collection_names) > 5 else collection_names,
            "target_collection": target_collection,
            "target_exists": collection_exists,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_mem0_import() -> dict:
    """
    测试mem0模块导入
    
    Returns:
        dict: 导入测试结果
    """
    try:
        # 尝试导入mem0
        try:
            import mem0
            mem0_version = getattr(mem0, '__version__', 'unknown')
        except ImportError:
            return {
                "success": False,
                "error": "mem0未安装，请运行: pip install mem0ai",
                "mem0_installed": False
            }
        
        return {
            "success": True,
            "mem0_installed": True,
            "mem0_version": mem0_version,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_embedding_model() -> dict:
    """
    测试嵌入模型
    
    Returns:
        dict: 模型测试结果
    """
    try:
        # 尝试导入sentence_transformers
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return {
                "success": False,
                "error": "sentence-transformers未安装，请运行: pip install sentence-transformers",
                "installed": False
            }
        
        config = Config.from_env()
        device = config.DEVICE
        
        # 测试加载模型
        print("  正在加载嵌入模型（首次可能需要下载）...")
        model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            device=device
        )
        
        # 测试向量化
        test_text = "这是一个测试文本"
        embedding = model.encode(test_text)
        
        return {
            "success": True,
            "installed": True,
            "model_name": "all-MiniLM-L6-v2",
            "device": device,
            "embedding_dimension": len(embedding),
            "embedding_sample": embedding[:3].tolist(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def print_report() -> None:
    """打印测试报告"""
    print("\n" + "=" * 60)
    print("嵌入器测试报告")
    print("=" * 60)
    
    # mem0配置测试
    mem0_config_result = test_mem0_config()
    print("\n[1] mem0配置测试")
    print("-" * 40)
    if mem0_config_result['success']:
        print(f"  配置加载: {'✓ 成功' if mem0_config_result['config_loaded'] else '✗ 失败'}")
        print(f"  DeepSeek模型: {mem0_config_result['deepseek_model']}")
        print(f"  DeepSeek URL: {mem0_config_result['deepseek_base_url']}")
        print(f"  Qdrant地址: {mem0_config_result['qdrant_host']}:{mem0_config_result['qdrant_port']}")
        print(f"  集合名称: {mem0_config_result['collection_name']}")
        print(f"  GPU可用: {'✓ 是' if mem0_config_result['gpu_available'] else '✗ 否'}")
        print(f"  设备: {mem0_config_result['device']}")
        print(f"  mem0配置项: {mem0_config_result['mem0_config_keys']}")
    else:
        print(f"  错误: {mem0_config_result.get('error', '未知错误')}")
    
    # 本地嵌入器配置测试
    embedder_result = test_local_embedder_config()
    print("\n[2] 本地嵌入模型配置测试")
    print("-" * 40)
    if embedder_result['success']:
        print(f"  模型名称: {embedder_result['model_name']}")
        print(f"  设备: {embedder_result['device']}")
        print(f"  归一化: {'是' if embedder_result['normalize_embeddings'] else '否'}")
        print(f"  GPU加速: {'✓ 可用' if embedder_result['gpu_acceleration'] else '✗ 不可用'}")
    else:
        print(f"  错误: {embedder_result.get('error', '未知错误')}")
    
    # mem0导入测试
    mem0_import_result = test_mem0_import()
    print("\n[3] mem0模块测试")
    print("-" * 40)
    if mem0_import_result['success']:
        print(f"  mem0安装: {'✓ 已安装' if mem0_import_result['mem0_installed'] else '✗ 未安装'}")
        print(f"  版本: {mem0_import_result['mem0_version']}")
    else:
        print(f"  mem0安装: ✗ 未安装")
        print(f"  提示: {mem0_import_result.get('error', '请安装mem0ai')}")
    
    # Qdrant连接测试
    qdrant_result = test_qdrant_connection()
    print("\n[4] Qdrant连接测试")
    print("-" * 40)
    if qdrant_result['success']:
        print(f"  Qdrant安装: {'✓ 已安装' if qdrant_result['qdrant_installed'] else '✗ 未安装'}")
        print(f"  服务器地址: {qdrant_result['host']}:{qdrant_result['port']}")
        print(f"  集合数量: {qdrant_result['collection_count']}")
        print(f"  目标集合: {qdrant_result['target_collection']}")
        print(f"  集合存在: {'✓ 是' if qdrant_result['target_exists'] else '✗ 否'}")
        if qdrant_result['collections']:
            print(f"  现有集合: {', '.join(qdrant_result['collections'])}")
    else:
        print(f"  Qdrant连接: ✗ 失败")
        print(f"  错误: {qdrant_result.get('error', '未知错误')}")
    
    # 嵌入模型测试
    embedding_result = test_embedding_model()
    print("\n[5] 嵌入模型测试")
    print("-" * 40)
    if embedding_result['success']:
        print(f"  模型安装: {'✓ 已安装' if embedding_result['installed'] else '✗ 未安装'}")
        print(f"  模型名称: {embedding_result['model_name']}")
        print(f"  设备: {embedding_result['device']}")
        print(f"  向量维度: {embedding_result['embedding_dimension']}")
        print(f"  向量示例: [{', '.join(map(str, embedding_result['embedding_sample']))}, ...]")
    else:
        print(f"  嵌入模型: ✗ 不可用")
        print(f"  错误: {embedding_result.get('error', '未知错误')}")
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    # 统计测试结果
    tests = [
        ("mem0配置", mem0_config_result['success']),
        ("本地嵌入器配置", embedder_result['success']),
        ("mem0模块", mem0_import_result['success']),
        ("Qdrant连接", qdrant_result['success']),
        ("嵌入模型", embedding_result['success']),
    ]
    
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    
    print(f"\n通过: {passed}/{total}")
    
    for name, success in tests:
        status = "✓" if success else "✗"
        print(f"  [{status}] {name}")
    
    # 给出建议
    print("\n" + "-" * 40)
    if passed == total:
        print("✓ 所有测试通过！记忆系统可以正常使用。")
    else:
        print("⚠ 部分测试未通过，请检查以下事项：")
        
        if not mem0_import_result['success']:
            print("  • 安装mem0: pip install mem0ai")
        
        if not qdrant_result['success']:
            print("  • 启动Qdrant服务: docker run -p 6333:6333 qdrant/qdrant")
            print("  • 或安装Qdrant: pip install qdrant-client")
        
        if not embedding_result['success']:
            print("  • 安装sentence-transformers: pip install sentence-transformers")
            print("  • 安装PyTorch: pip install torch")
    
    print("\n测试完成！")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("嵌入器测试工具")
    print("=" * 60)
    print("\n正在测试记忆系统环境...")
    
    try:
        print_report()
        return 0
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
