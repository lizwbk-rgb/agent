"""
配置管理模块

负责从.env文件读取配置、GPU检测、mem0配置生成和配置验证
"""

import os
import torch
from dotenv import load_dotenv
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    """应用配置类"""
    
    # DeepSeek API配置
    DEEPSEEK_API_KEY: str = Field(..., description="DeepSeek API密钥")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com", description="DeepSeek API基础URL")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat", description="DeepSeek模型名称")
    
    # 用户配置
    USER_ID: str = Field(default="default_user", description="用户ID")
    
    # 记忆配置
    MAX_MEMORY_COUNT: int = Field(default=10, ge=1, le=50, description="最大注入记忆数量")
    
    # Qdrant向量数据库配置
    QDRANT_HOST: str = Field(default="localhost", description="Qdrant主机地址")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant端口")
    
    # mem0配置
    MEM0_COLLECTION_NAME: str = Field(default="agent_memories", description="mem0集合名称")
    
    # GPU配置（运行时检测）
    GPU_AVAILABLE: bool = Field(default=False, description="GPU是否可用")
    DEVICE: str = Field(default="cpu", description="设备类型: cuda 或 cpu")
    
    @classmethod
    def from_env(cls, env_path: str = ".env") -> "Config":
        """从.env文件加载配置"""
        # 加载.env文件
        if os.path.exists(env_path):
            load_dotenv(env_path)
        
        # 检测GPU
        gpu_available = torch.cuda.is_available()
        device = "cuda" if gpu_available else "cpu"
        
        return cls(
            DEEPSEEK_API_KEY=os.getenv("DEEPSEEK_API_KEY", ""),
            DEEPSEEK_BASE_URL=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            DEEPSEEK_MODEL=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            USER_ID=os.getenv("USER_ID", "default_user"),
            MAX_MEMORY_COUNT=int(os.getenv("MAX_MEMORY_COUNT", "10")),
            QDRANT_HOST=os.getenv("QDRANT_HOST", "localhost"),
            QDRANT_PORT=int(os.getenv("QDRANT_PORT", "6333")),
            MEM0_COLLECTION_NAME=os.getenv("MEM0_COLLECTION_NAME", "agent_memories"),
            GPU_AVAILABLE=gpu_available,
            DEVICE=device
        )
    
    @field_validator("DEEPSEEK_API_KEY")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """验证API密钥"""
        if not v or v == "your_api_key_here":
            raise ValueError("DEEPSEEK_API_KEY未配置，请在.env文件中设置有效的API密钥")
        return v
    
    @field_validator("MAX_MEMORY_COUNT")
    @classmethod
    def validate_max_memory(cls, v: int) -> int:
        """验证最大记忆数量"""
        if v < 1:
            return 1
        if v > 50:
            return 50
        return v
    
    def get_device(self) -> str:
        """获取当前设备"""
        return self.DEVICE
    
    def is_gpu_available(self) -> bool:
        """检查GPU是否可用"""
        return self.GPU_AVAILABLE
    
    @staticmethod
    def get_mem0_config() -> dict:
        """
        返回mem0配置字典
        
        包含LLM、Embedder和Vector Store的完整配置
        """
        config = Config.from_env()
        
        return {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": config.DEEPSEEK_MODEL,
                    "openai_base_url": config.DEEPSEEK_BASE_URL,
                    "api_key": config.DEEPSEEK_API_KEY,
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            },
            "embedder": {
                "provider": "sentence_transformer",
                "config": {
                    "model_name": "all-MiniLM-L6-v2",
                    "device": config.DEVICE,
                    "normalize_embeddings": True
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "path": "data/qdrant.db"
                }
            },
            "history_db": {
                "provider": "sqlite",
                "config": {
                    "db_path": "data/history.db"
                }
            }
        }
    
    @staticmethod
    def get_local_embedder_config() -> dict:
        """
        返回本地嵌入模型配置（GPU加速）
        
        使用SentenceTransformer本地模型，支持GPU加速
        """
        config = Config.from_env()
        
        return {
            "embedder": {
                "provider": "sentence_transformer",
                "config": {
                    "model_name": "all-MiniLM-L6-v2",  # 或使用更大模型 "all-mpnet-base-v2"
                    "device": config.DEVICE,
                    "normalize_embeddings": True
                }
            }
        }
    
    @staticmethod
    def get_deepseek_embedder_config() -> dict:
        """
        返回DeepSeek嵌入模型配置
        
        使用DeepSeek的嵌入API
        """
        config = Config.from_env()
        
        return {
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "deepseek-embedding",  # 假设DeepSeek有嵌入模型
                    "base_url": config.DEEPSEEK_BASE_URL,
                    "api_key": config.DEEPSEEK_API_KEY,
                    "dimensions": 1024
                }
            }
        }
    
    def print_config(self):
        """打印当前配置（隐藏敏感信息）"""
        print("=" * 50)
        print("应用配置")
        print("=" * 50)
        print(f"DeepSeek API Key: {'*' * 20}...{self.DEEPSEEK_API_KEY[-4:]}")
        print(f"DeepSeek Base URL: {self.DEEPSEEK_BASE_URL}")
        print(f"DeepSeek Model: {self.DEEPSEEK_MODEL}")
        print(f"User ID: {self.USER_ID}")
        print(f"Max Memory Count: {self.MAX_MEMORY_COUNT}")
        print(f"Qdrant Host: {self.QDRANT_HOST}:{self.QDRANT_PORT}")
        print(f"Mem0 Collection: {self.MEM0_COLLECTION_NAME}")
        print(f"GPU Available: {self.GPU_AVAILABLE}")
        print(f"Device: {self.DEVICE}")
        print("=" * 50)


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_config() -> list[str]:
        """
        验证配置并返回错误列表
        
        Returns:
            list[str]: 错误信息列表，如果为空则表示配置有效
        """
        errors = []
        
        try:
            config = Config.from_env()
            
            # 验证API密钥
            if not config.DEEPSEEK_API_KEY or config.DEEPSEEK_API_KEY == "your_api_key_here":
                errors.append("DEEPSEEK_API_KEY未配置或使用默认值")
            
            # 验证Qdrant配置
            if config.QDRANT_HOST == "localhost":
                print("警告: Qdrant使用默认localhost配置，确保Qdrant服务已启动")
            
        except Exception as e:
            errors.append(f"配置加载失败: {str(e)}")
        
        return errors
    
    @staticmethod
    def check_gpu() -> dict:
        """
        检查GPU状态
        
        Returns:
            dict: GPU信息字典
        """
        gpu_info = {
            "available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "device_name": None,
            "device_capability": None
        }
        
        if torch.cuda.is_available():
            gpu_info["device_name"] = torch.cuda.get_device_name(0)
            capability = torch.cuda.get_device_capability(0)
            gpu_info["device_capability"] = f"{capability[0]}.{capability[1]}"
        
        return gpu_info
    
    @staticmethod
    def check_qdrant_connection(host: str = "localhost", port: int = 6333) -> bool:
        """
        检查Qdrant连接
        
        Args:
            host: Qdrant主机
            port: Qdrant端口
            
        Returns:
            bool: 是否连接成功
        """
        try:
            from qdrant_client import QdrantClient
            
            client = QdrantClient(host=host, port=port, timeout=5)
            collections = client.get_collections()
            return True
        except Exception:
            return False


# 全局配置实例
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例（单例模式）"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config.from_env()
    return _config_instance


def reload_config() -> Config:
    """重新加载配置"""
    global _config_instance
    _config_instance = Config.from_env()
    return _config_instance


# 便捷函数
config = get_config()
