#!/usr/bin/env python3
"""
AI对话客户端 - 启动脚本

快速启动应用的入口脚本
"""

import sys
import os
import subprocess
from pathlib import Path

# 抑制 HuggingFace 未认证警告
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

# 切换到项目目录
os.chdir(Path(__file__).parent)

# 添加项目根目录和src目录到路径
PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

def check_and_install_dependencies():
    """检查并安装必要的依赖"""
    required_packages = [
        ('matplotlib', 'matplotlib'),
    ]
    
    for module_name, pip_name in required_packages:
        try:
            __import__(module_name)
        except ImportError:
            print(f"[启动] 正在安装 {pip_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            print(f"[启动] {pip_name} 安装完成")

def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("AI对话客户端")
    print("=" * 50)
    
    # 检查并安装依赖
    check_and_install_dependencies()
    
    try:
        # 导入并运行应用
        from src.main import run_app
        run_app()
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
