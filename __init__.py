"""
ComfyUI custom node loader for this plugin.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    from aiohttp import web
    from server import PromptServer
except Exception:  # noqa: BLE001
    PromptServer = None
    web = None


current_dir = Path(__file__).parent
PLUGIN_VERSION = "1.0.1"
UPDATE_META_PATH = current_dir / ".update_meta.json"
DEFAULT_REMOTE_URL = "https://github.com/XY121718/ComfyUI_CY_Nodes.git"
DEFAULT_BRANCH = "main"
PRESERVE_UPDATE_FILES = {
    ".git",
    "__pycache__",
    "config.ini",
    "config_v2.ini",
    "master_key.ini",
    ".update_meta.json",
}
_UPDATE_ROUTES_REGISTERED = False

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _discover_nodes(module):
    node_mappings = getattr(module, "NODE_CLASS_MAPPINGS", None)
    display_mappings = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", None)

    if not node_mappings:
        node_mappings = {}
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


def _parse_github_repo(remote_url: str):
    if not remote_url:
        return None, None

    ssh_match = re.match(r"git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", remote_url)
    if ssh_match:
        return ssh_match.group("owner"), ssh_match.group("repo")

    parsed = urlparse(remote_url)
    if parsed.netloc.lower() != "github.com":
        return None, None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None, None

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _load_update_meta():
    if not UPDATE_META_PATH.exists():
        return {}

    try:
        return json.loads(UPDATE_META_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_update_meta(meta: dict):
    UPDATE_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _git(cmd: list[str]):
    import subprocess

    result = subprocess.run(
        cmd,
        cwd=current_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result


def _git_available():
    return (current_dir / ".git").exists()


def _get_remote_url():
    if _git_available():
        result = _git(["git", "remote", "get-url", "origin"])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return _load_update_meta().get("remote_url") or DEFAULT_REMOTE_URL


def _get_branch():
    if _git_available():
        result = _git(["git", "branch", "--show-current"])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return _load_update_meta().get("branch") or DEFAULT_BRANCH


def _get_local_commit():
    if _git_available():
        result = _git(["git", "rev-parse", "HEAD"])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return _load_update_meta().get("commit")


def _get_remote_commit(remote_url: str, branch: str):
    if _git_available():
        result = _git(["git", "ls-remote", "origin", f"refs/heads/{branch}"])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split()[0]

    owner, repo = _parse_github_repo(remote_url)
    if not owner or not repo:
        return None

    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}",
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("sha")


def _download_and_apply_update(remote_url: str, branch: str, remote_commit: str | None):
    owner, repo = _parse_github_repo(remote_url)
    if not owner or not repo:
        raise ValueError("无法识别 GitHub 仓库地址。")

    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    response = requests.get(zip_url, timeout=60)
    response.raise_for_status()

    with tempfile.TemporaryDirectory(prefix="cy_nodes_update_") as tmp_dir:
        zip_path = Path(tmp_dir) / "update.zip"
        zip_path.write_bytes(response.content)

        extract_dir = Path(tmp_dir) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            zip_file.extractall(extract_dir)

        extracted_roots = [path for path in extract_dir.iterdir() if path.is_dir()]
        if not extracted_roots:
            raise ValueError("更新包解压失败，未找到插件目录。")

        source_root = extracted_roots[0]
        for source in source_root.rglob("*"):
            relative_path = source.relative_to(source_root)
            if not relative_path.parts:
                continue

            top_level = relative_path.parts[0]
            if top_level in PRESERVE_UPDATE_FILES:
                continue

            destination = current_dir / relative_path
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    _save_update_meta(
        {
            "remote_url": remote_url,
            "branch": branch,
            "commit": remote_commit,
        }
    )


def _build_update_status():
    remote_url = _get_remote_url()
    branch = _get_branch()
    local_commit = _get_local_commit()
    remote_commit = _get_remote_commit(remote_url, branch)
    update_available = None
    if local_commit and remote_commit:
        update_available = local_commit != remote_commit

    return {
        "plugin_version": PLUGIN_VERSION,
        "remote_url": remote_url,
        "branch": branch,
        "local_commit": local_commit,
        "remote_commit": remote_commit,
        "update_available": update_available,
    }


def _register_update_routes():
    global _UPDATE_ROUTES_REGISTERED

    if _UPDATE_ROUTES_REGISTERED:
        return

    if PromptServer is None or web is None:
        print("[WARN] PromptServer not available; update routes skipped")
        return

    routes = PromptServer.instance.routes

    @routes.get("/cy_nodes/updater/status")
    async def cy_nodes_updater_status(_request):
        try:
            return web.json_response({"success": True, **_build_update_status()})
        except Exception as exc:  # noqa: BLE001
            return web.json_response({"success": False, "message": str(exc)}, status=500)

    @routes.post("/cy_nodes/updater/update")
    async def cy_nodes_updater_update(_request):
        try:
            status = _build_update_status()
            _download_and_apply_update(
                status["remote_url"],
                status["branch"],
                status["remote_commit"],
            )
            return web.json_response(
                {
                    "success": True,
                    "message": "插件更新完成，请重载或重启 ComfyUI。",
                    "remote_commit": status["remote_commit"],
                    "requires_restart": True,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return web.json_response({"success": False, "message": str(exc)}, status=500)

    _UPDATE_ROUTES_REGISTERED = True


for py_file in current_dir.glob("*.py"):
    if py_file.name == "__init__.py":
        continue

    try:
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
    except Exception as exc:  # noqa: BLE001
        print(f"[ERR] 加载节点文件失败 {py_file.name}: {exc}")

if NODE_CLASS_MAPPINGS:
    print(f"[INFO] 总共加载了 {len(NODE_CLASS_MAPPINGS)} 个自定义节点:")
    for node_name in NODE_CLASS_MAPPINGS.keys():
        display_name = NODE_DISPLAY_NAME_MAPPINGS.get(node_name, node_name)
        print(f"   - {display_name} ({node_name})")
else:
    print("[WARN] 未找到任何有效的节点")

_register_update_routes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
WEB_DIRECTORY = "./web"
