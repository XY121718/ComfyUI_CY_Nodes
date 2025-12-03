"""
通用ComfyUI自定义节点加载器
支持任何文件夹名称，自动检测并加载节点
"""

import importlib.util
import inspect
from pathlib import Path

# 获取当前文件夹路径
current_dir = Path(__file__).parent

# 初始化节点映射字典
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _discover_nodes(module):
    """Return node + display mappings for the given module, auto-detecting classes if needed."""
    node_mappings = getattr(module, "NODE_CLASS_MAPPINGS", None)
    display_mappings = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", None)

    if not node_mappings:
        node_mappings = {}
        # 仅注册当前模块中定义且具有节点特征的类
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if not hasattr(cls, "RETURN_TYPES"):
                continue
            node_mappings[name] = cls

    if not node_mappings:
        return None, None

    if not display_mappings:
        display_mappings = {}

    for node_name, node_cls in node_mappings.items():
        display_mappings.setdefault(node_name, getattr(node_cls, "DISPLAY_NAME", node_name))

    return node_mappings, display_mappings


# 自动查找并加载所有Python文件中的节点
for py_file in current_dir.glob("*.py"):
    if py_file.name == "__init__.py":
        continue

    try:
        # 动态导入模块
        module_name = py_file.stem
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        node_map, display_map = _discover_nodes(module)
        if not node_map:
            print(f"[WARN] 未在 {py_file.name} 中找到可注册的节点类")
            continue

        NODE_CLASS_MAPPINGS.update(node_map)
        NODE_DISPLAY_NAME_MAPPINGS.update(display_map)

        print(f"[OK] 成功加载节点文件: {py_file.name}")

    except Exception as e:  # noqa: BLE001
        print(f"[ERR] 加载节点文件失败 {py_file.name}: {str(e)}")

# 打印加载的节点信息
if NODE_CLASS_MAPPINGS:
    print(f"[INFO] 总共加载了 {len(NODE_CLASS_MAPPINGS)} 个自定义节点:")
    for node_name in NODE_CLASS_MAPPINGS.keys():
        display_name = NODE_DISPLAY_NAME_MAPPINGS.get(node_name, node_name)
        print(f"   - {display_name} ({node_name})")
else:
    print("[WARN] 未找到任何有效的节点")

# ComfyUI需要的变量
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
WEB_DIRECTORY = "./web"
