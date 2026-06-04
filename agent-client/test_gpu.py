"""
GPU测试脚本

检测CUDA可用性、GPU信息获取、RTX 2060验证
"""

import sys
import torch
from pathlib import Path


def test_cuda_availability() -> dict:
    """
    测试CUDA可用性
    
    Returns:
        dict: CUDA状态信息
    """
    result = {
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": None,
        "pytorch_version": torch.__version__,
    }
    
    if result["cuda_available"]:
        result["cuda_version"] = torch.version.cuda
        result["cudnn_version"] = torch.backends.cudnn.version()
        result["device_count"] = torch.cuda.device_count()
    
    return result


def get_gpu_info() -> list:
    """
    获取所有GPU信息
    
    Returns:
        list: GPU信息列表
    """
    if not torch.cuda.is_available():
        return []
    
    gpu_list = []
    
    for i in range(torch.cuda.device_count()):
        gpu_info = {
            "index": i,
            "name": torch.cuda.get_device_name(i),
            "total_memory_gb": round(torch.cuda.get_device_properties(i).total_memory / (1024**3), 2),
            "capability_major": torch.cuda.get_device_capability(i)[0],
            "capability_minor": torch.cuda.get_device_capability(i)[1],
        }
        gpu_list.append(gpu_info)
    
    return gpu_list


def test_tensor_operations() -> dict:
    """
    测试GPU张量操作
    
    Returns:
        dict: 测试结果
    """
    if not torch.cuda.is_available():
        return {"success": False, "error": "CUDA不可用"}
    
    try:
        # 创建测试张量
        device = torch.device("cuda:0")
        
        # 测试基本运算
        a = torch.randn(1000, 1000).to(device)
        b = torch.randn(1000, 1000).to(device)
        
        # 矩阵乘法
        c = torch.mm(a, b)
        
        # 同步GPU
        torch.cuda.synchronize()
        
        return {
            "success": True,
            "device": str(device),
            "result_shape": list(c.shape),
            "result_dtype": str(c.dtype),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_rtx_2060() -> dict:
    """
    测试RTX 2060特定功能
    
    Returns:
        dict: 测试结果
    """
    gpu_list = get_gpu_info()
    
    if not gpu_list:
        return {"success": False, "error": "未检测到GPU"}
    
    # 查找RTX 2060
    rtx_2060 = None
    for gpu in gpu_list:
        if "2060" in gpu["name"]:
            rtx_2060 = gpu
            break
    
    if not rtx_2060:
        return {
            "success": False,
            "error": "未检测到RTX 2060",
            "detected_gpus": [gpu["name"] for gpu in gpu_list],
        }
    
    # RTX 2060特性验证
    return {
        "success": True,
        "gpu_name": rtx_2060["name"],
        "memory_gb": rtx_2060["total_memory_gb"],
        "compute_capability": f"{rtx_2060['capability_major']}.{rtx_2060['capability_minor']}",
        "tensor_cores_available": rtx_2060["capability_major"] >= 7,  # Turing及以上架构
    }


def print_report() -> None:
    """打印测试报告"""
    print("\n" + "=" * 60)
    print("GPU测试报告")
    print("=" * 60)
    
    # CUDA可用性
    cuda_info = test_cuda_availability()
    print("\n[1] CUDA可用性检测")
    print("-" * 40)
    print(f"  CUDA可用: {'✓ 是' if cuda_info['cuda_available'] else '✗ 否'}")
    print(f"  PyTorch版本: {cuda_info['pytorch_version']}")
    if cuda_info['cuda_available']:
        print(f"  CUDA版本: {cuda_info['cuda_version']}")
        print(f"  cuDNN版本: {cuda_info['cudnn_version']}")
        print(f"  设备数量: {cuda_info['device_count']}")
    
    # GPU信息
    gpu_list = get_gpu_info()
    print("\n[2] GPU信息")
    print("-" * 40)
    if gpu_list:
        for gpu in gpu_list:
            print(f"  GPU {gpu['index']}: {gpu['name']}")
            print(f"    显存: {gpu['total_memory_gb']} GB")
            print(f"    计算能力: {gpu['capability_major']}.{gpu['capability_minor']}")
    else:
        print("  未检测到GPU")
    
    # 张量操作测试
    tensor_result = test_tensor_operations()
    print("\n[3] GPU张量操作测试")
    print("-" * 40)
    if tensor_result['success']:
        print(f"  测试结果: ✓ 成功")
        print(f"  设备: {tensor_result['device']}")
        print(f"  结果形状: {tensor_result['result_shape']}")
        print(f"  数据类型: {tensor_result['result_dtype']}")
    else:
        print(f"  测试结果: ✗ 失败")
        print(f"  错误: {tensor_result.get('error', '未知错误')}")
    
    # RTX 2060测试
    rtx_result = test_rtx_2060()
    print("\n[4] RTX 2060验证")
    print("-" * 40)
    if rtx_result['success']:
        print(f"  RTX 2060: ✓ 检测到")
        print(f"  GPU名称: {rtx_result['gpu_name']}")
        print(f"  显存: {rtx_result['memory_gb']} GB")
        print(f"  计算能力: {rtx_result['compute_capability']}")
        print(f"  Tensor Cores: {'✓ 可用' if rtx_result['tensor_cores_available'] else '✗ 不可用'}")
    else:
        print(f"  RTX 2060: ✗ 未检测到")
        print(f"  原因: {rtx_result.get('error', '未知')}")
        if 'detected_gpus' in rtx_result:
            print(f"  已检测到的GPU: {', '.join(rtx_result['detected_gpus'])}")
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if cuda_info['cuda_available']:
        print("✓ CUDA环境正常")
        if rtx_result['success']:
            print("✓ RTX 2060可用，Tensor Cores已启用")
            print("  → 嵌入模型将使用GPU加速")
        else:
            print("✓ GPU可用，但非RTX 2060")
            print("  → 嵌入模型仍可使用GPU加速")
    else:
        print("✗ CUDA不可用，将使用CPU模式")
        print("  → 嵌入模型将使用CPU，速度较慢")
    
    print("\n测试完成！")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("GPU测试工具")
    print("=" * 60)
    print("\n正在检测GPU环境...")
    
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
