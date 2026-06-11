"""
AI对话客户端 - 应用入口

PyQt6应用主入口，创建主窗口并启动应用
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

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

# 导入Qdrant管理器
from qdrant_manager import get_qdrant_manager, stop_qdrant


def create_application() -> object:
    """
    创建PyQt应用
    
    Returns:
        QApplication: PyQt应用实例
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


def create_main_window_without_agent() -> object:
    """
    创建主窗口（不创建Agent，用于初始化阶段显示遮罩）
    
    Returns:
        MainWindow: 主窗口实例（agent为None）
    """
    from ui.main_window import MainWindow
    
    logger.info("创建主窗口（无Agent）")
    
    # 创建主窗口（agent为None）
    window = MainWindow(agent=None)
    
    return window


def init_qdrant_and_agent(window: object) -> object:
    """
    初始化Qdrant和Agent
    
    Args:
        window: 主窗口实例
        
    Returns:
        Agent: Agent实例
    """
    from agent import Agent
    from config import get_config
    from PyQt6.QtWidgets import QApplication
    
    try:
        # 1. 启动Qdrant
        logger.info("开始初始化Qdrant...")
        window.show_init_overlay(message="正在启动 Qdrant 服务...")
        
        qdrant_manager = get_qdrant_manager()
        
        # 启动Qdrant（传递process_events_callback让UI事件得到处理，动画继续）
        if not qdrant_manager.is_running():
            logger.info("Qdrant未运行，正在启动...")
            # 传递QApplication.processEvents作为回调，让等待期间UI不卡死
            qdrant_manager.start(wait_timeout=30.0, process_events_callback=QApplication.processEvents)
            logger.info("Qdrant启动成功")
        else:
            logger.info("Qdrant已经在运行")
        
        # 2. 创建Agent
        logger.info("开始创建Agent...")
        window.show_init_overlay(message="正在初始化 Agent...")
        
        config = get_config()
        agent = Agent(user_id=config.USER_ID)
        
        logger.info("Agent创建成功")
        
        # 3. 设置Agent到窗口（但不隐藏遮罩，记忆加载完成后才隐藏）
        window.set_agent(agent)  # 将agent设置到窗口
        
        logger.info("Qdrant和Agent初始化完成，开始加载记忆...")
        
        return agent
        
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        window.show_init_overlay(message=f"初始化失败: {str(e)}\n请检查配置后重试。")
        # 不重新抛出异常，让用户可以看到错误信息


def run_app():
    """
    运行应用
    
    主入口函数，先创建窗口显示遮罩，然后异步初始化Qdrant和Agent
    """
    logger.info("=" * 50)
    logger.info("AI对话客户端启动")
    logger.info("=" * 50)
    
    app = None
    window = None
    
    try:
        # 1. 创建应用
        app = create_application()
        
        # 2. 创建主窗口（不创建Agent）
        window = create_main_window_without_agent()
        
        # 3. 显示窗口（显示初始化遮罩）
        window.show()
        window.show_init_overlay(message="正在启动应用...")
        
        # 4. 使用QTimer单次定时器，在事件循环启动后执行初始化
        from PyQt6.QtCore import QTimer
        
        def do_init():
            """执行初始化"""
            try:
                agent = init_qdrant_and_agent(window)
                # 不隐藏遮罩 - 显示"正在加载记忆..."并触发记忆加载
                window.show_init_overlay(message="正在加载记忆...")
                
                # 先连接 memories_loaded 信号（避免竞态：worker 先完成）
                if hasattr(window, 'memory_widget') and window.memory_widget:
                    # 确保只连接一次
                    try:
                        window.memory_widget.memories_loaded.disconnect()
                    except:
                        pass
                    window.memory_widget.memories_loaded.connect(
                        lambda: window.hide_init_overlay()
                    )
                    # 再触发记忆加载（异步）
                    window.memory_widget.refresh_memories()
            except Exception as e:
                logger.error(f"初始化过程中发生错误: {e}", exc_info=True)
        
        # 延迟100ms执行初始化，确保窗口已经显示
        QTimer.singleShot(100, do_init)
        
        logger.info("主窗口已显示，开始异步初始化...")
        
        # 5. 运行事件循环（在aboutToQuit信号中停止Qdrant，确保退出时清理）
        def on_about_to_quit():
            """应用即将退出时停止Qdrant"""
            logger.info("收到aboutToQuit信号，正在停止Qdrant...")
            try:
                stop_qdrant()
                logger.info("Qdrant已停止")
            except Exception as e:
                logger.error(f"停止Qdrant时出错: {e}")
        
        app.aboutToQuit.connect(on_about_to_quit)
        
        exit_code = app.exec()
        logger.info(f"事件循环退出，退出码: {exit_code}")
        
        logger.info("应用已退出")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}", exc_info=True)
        if app:
            sys.exit(app.exec())
        else:
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
