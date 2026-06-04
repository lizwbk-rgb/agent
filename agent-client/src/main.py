"""
AI对话客户端 - 应用入口

PyQt6应用主入口，创建主窗口并启动应用
"""

import sys
import os
import logging
from pathlib import Path

# 设置项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置数据目录
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# 配置日志
from utils.helpers import setup_logger

logger = setup_logger(
    name="agent_client",
    log_file=DATA_DIR / "agent_client.log",
    level=logging.INFO
)


def create_application() -> tuple:
    """
    创建PyQt应用和主窗口
    
    Returns:
        tuple: (QApplication, MainWindow)
    """
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyleSheet("""
        QApplication {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            font-size: 12px;
        }
        QMainWindow {
            background-color: #f5f5f5;
        }
        QWidget {
            font-size: 12px;
        }
    """)
    
    # 设置应用属性
    app.setApplicationName("AI对话客户端")
    app.setOrganizationName("AgentClient")
    
    return app


def create_agent() -> "Agent":
    """
    创建Agent实例
    
    Returns:
        Agent: Agent实例
    """
    from agent import Agent
    from config import get_config
    
    # 获取配置
    config = get_config()
    
    logger.info(f"创建Agent实例，用户ID: {config.USER_ID}")
    
    # 创建Agent
    agent = Agent(user_id=config.USER_ID)
    
    return agent


def create_main_window(agent) -> "MainWindow":
    """
    创建主窗口
    
    Args:
        agent: Agent实例
        
    Returns:
        MainWindow: 主窗口实例
    """
    from ui.main_window import MainWindow
    
    logger.info("创建主窗口")
    
    # 创建主窗口
    window = MainWindow(agent=agent)
    
    return window


def run_app():
    """
    运行应用
    
    主入口函数，创建应用、Agent和主窗口，然后启动事件循环
    """
    logger.info("=" * 50)
    logger.info("AI对话客户端启动")
    logger.info("=" * 50)
    
    try:
        # 创建应用
        app = create_application()
        
        # 创建Agent
        agent = create_agent()
        
        # 创建主窗口
        window = create_main_window(agent)
        
        # 显示窗口
        window.show()
        
        logger.info("主窗口已显示")
        logger.info("应用启动完成")
        
        # 运行事件循环
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_modules():
    """
    测试所有模块是否正常导入
    
    Returns:
        bool: 所有模块导入成功返回True
    """
    logger.info("开始测试模块导入...")
    
    modules = [
        ("config", "Config"),
        ("deepseek_client", "DeepSeekClient"),
        ("memory_manager", "MemoryManager"),
        ("agent", "Agent"),
        ("utils.helpers", "setup_logger"),
        ("utils.file_processor", "FileProcessor"),
    ]
    
    from importlib import import_module
    
    for module_path, class_name in modules:
        try:
            module = import_module(f".{module_path}", package="src")
            getattr(module, class_name)
            logger.info(f"  ✓ {module_path}.{class_name}")
        except ImportError as e:
            logger.error(f"  ✗ {module_path}.{class_name}: {e}")
            return False
    
    logger.info("所有模块导入测试通过")
    return True


if __name__ == "__main__":
    # 如果直接运行此文件，启动应用
    run_app()
