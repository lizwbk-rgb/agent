#!/usr/bin/env python3
"""
AI对话客户端 - 启动脚本

快速启动应用的入口脚本
"""

import sys
import os
from pathlib import Path

# 切换到项目目录
os.chdir(Path(__file__).parent)

# 添加项目根目录和src目录到路径
PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("AI对话客户端")
    print("=" * 50)
    
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
