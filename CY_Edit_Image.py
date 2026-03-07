import base64
import configparser
import io
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
import torch
import urllib3
from PIL import Image, ImageOps

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_RELAY_BASE_URL = "https://api.xheai.cc"
EDIT_ENDPOINT_PATH = "/v1/images/edits"
REQUEST_TIMEOUT = 600  # 10分钟，等待生图返回
CATEGORY = "初阳"
DEFAULT_PROMPT = "a banana"
CONFIG_PATH = Path(__file__).with_name("config.ini")
CONFIG_LOCK = threading.Lock()
CONFIG = configparser.ConfigParser()
if CONFIG_PATH.exists():
    CONFIG.read(CONFIG_PATH, encoding="utf-8")
else:
    CONFIG["DEFAULT"] = {}
    with CONFIG_PATH.open("w", encoding="utf-8") as fp:
        CONFIG.write(fp)

MASTER_KEY_PATH = Path(__file__).with_name("master_key.ini")
MASTER_KEY_LOCK = threading.Lock()
MASTER_KEY_CONFIG = configparser.ConfigParser()
if MASTER_KEY_PATH.exists():
    MASTER_KEY_CONFIG.read(MASTER_KEY_PATH, encoding="utf-8")
else:
    MASTER_KEY_CONFIG["DEFAULT"] = {}
    with MASTER_KEY_PATH.open("w", encoding="utf-8") as fp:
        MASTER_KEY_CONFIG.write(fp)

IMAGE_SIZE_MAP = {
    "1K": {
        "1:1": "1024x1024",
        "4:3": "1152x864",
        "3:4": "864x1152",
        "16:9": "1280x720",
        "9:16": "720x1280",
        "2:3": "832x1248",
        "3:2": "1248x832",
        "21:9": "1512x648",
        "5:4": "1280x1024",
        "4:5": "1024x1280",
    },
    "2K": {
        "1:1": "2048x2048",
        "4:3": "2048x1536",
        "3:4": "1536x2048",
        "16:9": "2048x1152",
        "9:16": "1152x2048",
        "2:3": "1536x2048",
        "3:2": "2048x1536",
        "21:9": "2048x864",
        "5:4": "2560x2048",
        "4:5": "2048x2560",
    },
    "4K": {
        "1:1": "4096x4096",
        "4:3": "4096x3072",
        "3:4": "3072x4096",
        "16:9": "4096x2304",
        "9:16": "2304x4096",
        "2:3": "3072x4096",
        "3:2": "4096x3072",
        "21:9": "4096x1728",
        "5:4": "4096x3276",
        "4:5": "3276x4096",
    },
}

DEFAULT_MODEL_MAP = {
    "gemini-3-pro-image-preview": "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview": "gemini-3.1-flash-image-preview",
    "nano-banana": "nano-banana",
    "nano-banana-2": "nano-banana-2",
    "nano-banana-2-2k": "nano-banana-2-2k",
    "nano-banana-2-4k": "nano-banana-2-4k",
}

ASPECT_DISPLAY_MAP = {
    "4:3": "4:3",
    "3:4": "3:4",
    "16:9": "16:9",
    "9:16": "9:16",
    "2:3": "2:3",
    "3:2": "3:2",
    "1:1": "1:1",
    "4:5": "4:5",
    "5:4": "5:4",
    "21:9": "21:9",
}

IMAGE_SIZE_DISPLAY_MAP = {
    "Auto": "Auto",
    "1K": "1K",
    "2K": "2K",
    "4K": "4K",
}

RELAY_FIELD_LABEL = "中转网址"
RELAY_CONFIG_FIELD = "relay_url"
RELAY_URL_OPTIONS = ["https://api.xheai.cc", "https://ai.aicy168.top"]


def normalize_base_url(candidate: Optional[str]) -> str:
    base = (candidate or "").strip()
    if not base:
        return DEFAULT_RELAY_BASE_URL.rstrip("/")
    return base.rstrip("/").rstrip("\\")


def build_endpoint(base_url: str, path: str) -> str:
    base = normalize_base_url(base_url)
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def smart_resize(image, target_width, target_height):
    return ImageOps.fit(image, (target_width, target_height), method=Image.LANCZOS)


def tensor_to_pil(image_tensor):
    if len(image_tensor.shape) > 3:
        image_tensor = image_tensor[0]
    array = np.clip(image_tensor.cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(array)


def preprocess_image_file(image_tensor, filename, max_side=1536):
    pil = tensor_to_pil(image_tensor)
    w, h = pil.size
    if w > max_side or h > max_side:
        ratio = min(max_side / w, max_side / h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        print(f"[CY图片编辑] 图片压缩: {w}x{h} → {new_w}x{new_h}")
        pil = pil.resize((new_w, new_h), Image.LANCZOS)
    else:
        print(f"[CY图片编辑] 图片尺寸正常: {w}x{h}，无需压缩")

    buffered = io.BytesIO()
    pil.save(buffered, format="PNG")
    buffered.seek(0)
    return ("image", (filename, buffered.getvalue(), "image/png"))


def resolve_display_value(selection: str, mapping: dict, label: str):
    if selection not in mapping:
        raise ValueError(f"Unrecognized {label} option: {selection}")
    return mapping[selection]


def extract_image_entries(response_json):
    if isinstance(response_json, list):
        return response_json
    data_block = response_json.get("data")
    if isinstance(data_block, list):
        return data_block
    if isinstance(data_block, dict):
        inner = data_block.get("data")
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict) and "data" in inner:
            return inner["data"]
    return None


def make_request(method, url, timeout=REQUEST_TIMEOUT, **kwargs):
    """发送请求，不重试"""
    kwargs.setdefault("verify", False)
    response = requests.request(method, url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response


def download_image_with_retry(url, max_retries=3, timeout=120):
    """下载图片，带重试机制"""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(url, timeout=timeout, verify=False)
            if res.status_code == 200:
                return Image.open(io.BytesIO(res.content)).convert("RGB")
            last_error = Exception(f"HTTP {res.status_code}")
        except Exception as exc:
            last_error = exc
            print(f"[WARN] 图片下载失败 (尝试 {attempt}/{max_retries}): {exc}")
        if attempt < max_retries:
            time.sleep(2 ** attempt)
    raise last_error or Exception("图片下载失败")


def download_process(response_json, target_w=None, target_h=None, strict_mode=False):
    if "error" in response_json:
        error_msg = response_json['error']
        # 如果是 no images generated 错误，返回 None 而不是抛出异常
        if isinstance(error_msg, dict) and error_msg.get('message') == 'no images generated':
            print(f"[WARN] API 未生成图片: {error_msg}")
            return None
        raise Exception(f"API Error: {response_json['error']}")

    image_objects = []

    # Gemini 格式: {"candidates": [{"content": {"parts": [{"inlineData": {"data": "..."}}]}}]}
    if "candidates" in response_json:
        candidates = response_json.get('candidates', [])
        if candidates:
            content = candidates[0].get('content', {})
            parts = content.get('parts', []) if content else []
            for part in parts:
                if 'inlineData' in part and 'data' in part['inlineData']:
                    try:
                        b64_data = part['inlineData']['data']
                        img = Image.open(io.BytesIO(base64.b64decode(b64_data))).convert("RGB")
                        image_objects.append(img)
                    except Exception as e:
                        print(f"[WARN] Gemini base64 解码失败: {e}")
    else:
        # OpenAI 格式: {"data": [{"url": "...", "b64_json": "..."}]}
        entries = extract_image_entries(response_json)

        if entries:
            for item in entries:
                if item.get("url"):
                    try:
                        img = download_image_with_retry(item["url"])
                        image_objects.append(img)
                    except Exception as e:
                        print(f"[WARN] 图片下载最终失败: {e}")
                elif item.get("b64_json"):
                    try:
                        img = Image.open(io.BytesIO(base64.b64decode(item["b64_json"]))).convert("RGB")
                        image_objects.append(img)
                    except Exception:
                        pass
        elif "choices" in response_json:
            content = response_json["choices"][0]["message"]["content"]

            b64_matches = re.findall(r"data:image/\w+;base64,([a-zA-Z0-9+/=]+)", content)
            for b64_str in b64_matches:
                try:
                    img = Image.open(io.BytesIO(base64.b64decode(b64_str))).convert("RGB")
                    image_objects.append(img)
                except Exception:
                    pass

            if not image_objects:
                urls = re.findall(r"(https?://[^\s)\]\"']+)", content)
                for url in urls:
                    try:
                        img = download_image_with_retry(url)
                        image_objects.append(img)
                    except Exception as e:
                        print(f"[WARN] 图片下载最终失败: {e}")

    if not image_objects:
        print(f"[WARN] API 未返回任何图片")
        return None

    final_tensors = []
    base_w, base_h = target_w, target_h

    for i, img in enumerate(image_objects):
        if strict_mode and target_w and target_h:
            img = smart_resize(img, target_w, target_h)
        elif i == 0 and not strict_mode:
            base_w, base_h = img.size
        elif not strict_mode:
            img = img.resize((base_w, base_h), Image.LANCZOS)

        img_np = np.array(img).astype(np.float32) / 255.0
        final_tensors.append(torch.from_numpy(img_np))

    if not final_tensors:
        print(f"[WARN] 未能创建图片张量")
        return None

    return (torch.stack(final_tensors),)


class CYImageEdit:
    DISPLAY_NAME = "CY图片编辑"
    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "IMAGE")
    RETURN_NAMES = ("输出1", "输出2", "输出3", "输出4", "输出5")
    IMAGE_OUTPUT_COUNT = 5
    FUNCTION = "run"
    CATEGORY = CATEGORY

    MODEL_MAP = DEFAULT_MODEL_MAP
    MODEL_OPTIONS = list(MODEL_MAP.keys())
    ASPECT_OPTIONS = list(ASPECT_DISPLAY_MAP.keys())
    IMAGE_SIZE_OPTIONS = [size for size in IMAGE_SIZE_DISPLAY_MAP.keys() if size != "Auto"]
    IMAGE_INPUT_NAMES = [f"输入{i}" for i in range(1, 9)]
    IMAGE_LEGACY_NAMES = [f"image_{i}" for i in range(1, 9)]

    # 不需要 __init__ 方法，ComfyUI 会处理实例化

    @classmethod
    def INPUT_TYPES(cls):
        optional_inputs = {}
        for idx, name in enumerate(cls.IMAGE_INPUT_NAMES):
            optional_inputs[name] = (
                "IMAGE",
                {"forceInput": idx != 0, "label": name},
            )



        return {
            "required": {
                "提示词": ("STRING", {"multiline": True, "default": DEFAULT_PROMPT, "label": "提示词", "dynamicPrompts": False, "rows": 8}),
                RELAY_FIELD_LABEL: (
                    RELAY_URL_OPTIONS,
                    {
                        "default": RELAY_URL_OPTIONS[0],
                        "label": RELAY_FIELD_LABEL,
                    },
                ),
                "总Key": ("STRING", {
                    "default": MASTER_KEY_CONFIG["DEFAULT"].get("master_key", ""),
                    "label": "总Key（创建令牌用）",
                    "tooltip": "填入总Key后点击创建令牌按钮，仅 api.xheai.cc 支持"
                }),
                "Key1": (
                    "STRING",
                    {"multiline": False, "label": "Key1（必填）", "default": CONFIG["DEFAULT"].get("api_key", "")},
                ),
                "模型": (cls.MODEL_OPTIONS, {"default": cls.MODEL_OPTIONS[0], "label": "模型"}),
                "默认宽高比": (cls.ASPECT_OPTIONS, {"default": cls.ASPECT_OPTIONS[0], "label": "默认宽高比"}),
                "图像尺寸": (cls.IMAGE_SIZE_OPTIONS, {"default": cls.IMAGE_SIZE_OPTIONS[0], "label": "图像尺寸"}),
                "匹配参考尺寸": (
                    "BOOLEAN",
                    {"default": False, "label": "匹配参考尺寸", "label_on": "开启", "label_off": "关闭"},
                ),
                "按行拆分提示词": (
                    "BOOLEAN",
                    {"default": False, "label": "按行拆分提示词", "label_on": "开启", "label_off": "关闭"},
                ),
                "种子": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 2147483647,
                        "control_after_generate": "randomize",
                        "tooltip": "随机种子 (0-2147483647)，每次生成后自动随机",
                    },
                ),
            },
            "optional": optional_inputs,
        }

    def run(self, **inputs):
        cfg_dirty = False

        def resolve_key(field_name: str, primary_name: str, legacy_name: Optional[str] = None):
            nonlocal cfg_dirty
            value = self._get_input_value(inputs, primary_name, legacy_name, default="") or ""
            clean = value.strip()
            if clean:
                if CONFIG["DEFAULT"].get(field_name, "") != clean:
                    CONFIG["DEFAULT"][field_name] = clean
                    cfg_dirty = True
                return clean
            return CONFIG["DEFAULT"].get(field_name, "").strip()

        prompt = self._get_input_value(inputs, "提示词", "prompt", default=DEFAULT_PROMPT)
        split_mode = bool(self._get_input_value(inputs, "按行拆分提示词", "enable_prompt_split", default=False))


        relay_default = CONFIG["DEFAULT"].get(RELAY_CONFIG_FIELD, DEFAULT_RELAY_BASE_URL)
        relay_input = self._get_input_value(
            inputs, RELAY_FIELD_LABEL, "relay_url", "relay_base_url", default=relay_default
        )
        relay_clean = normalize_base_url(relay_input or relay_default)
        stored_relay = CONFIG["DEFAULT"].get(RELAY_CONFIG_FIELD, relay_default)
        if normalize_base_url(stored_relay) != relay_clean:
            CONFIG["DEFAULT"][RELAY_CONFIG_FIELD] = relay_clean
            cfg_dirty = True

        api_key_clean = resolve_key("api_key", "Key1", "api_key")
        if not api_key_clean:
            raise ValueError("Key1 是必填项。")

        # 保存总Key到单独文件（加锁保护）
        master_key_input = self._get_input_value(inputs, "总Key", default="").strip()
        if master_key_input and master_key_input != MASTER_KEY_CONFIG["DEFAULT"].get("master_key", ""):
            with MASTER_KEY_LOCK:
                MASTER_KEY_CONFIG["DEFAULT"]["master_key"] = master_key_input
                with MASTER_KEY_PATH.open("w", encoding="utf-8") as fp:
                    MASTER_KEY_CONFIG.write(fp)

        model_select = self._get_input_value(inputs, "模型", "model_select", default=self.MODEL_OPTIONS[0])
        aspect_ratio = self._get_input_value(inputs, "默认宽高比", "aspect_ratio", default=self.ASPECT_OPTIONS[0])
        image_size = self._get_input_value(inputs, "图像尺寸", "image_size", default=self.IMAGE_SIZE_OPTIONS[0])
        match_reference_size = bool(
            self._get_input_value(inputs, "匹配参考尺寸", "match_reference_size", default=False)
        )

        if cfg_dirty:
            with CONFIG_LOCK:
                with CONFIG_PATH.open("w", encoding="utf-8") as fp:
                    CONFIG.write(fp)

        model_value = resolve_display_value(model_select, self.MODEL_MAP, "model")
        aspect_value = resolve_display_value(aspect_ratio, ASPECT_DISPLAY_MAP, "aspect ratio")
        image_size_value = resolve_display_value(image_size, IMAGE_SIZE_DISPLAY_MAP, "image size")
        prompt_segments = self._split_prompts(prompt) if split_mode else []
        prompt_list = prompt_segments if prompt_segments else [prompt]

        dispatch_prompts = prompt_list
        if split_mode:
            print(f"[CY图片编辑] 批量提示词模式: 拆分为 {len(dispatch_prompts)} 段")
        
        # 获取种子值
        seed_value = self._get_input_value(inputs, "种子", default=0)
        
        channel_configs = self._collect_channel_configs(api_key_clean, len(dispatch_prompts))
        if not channel_configs:
            raise ValueError("Key1 是必填项。")

        provided_images = []
        primary_image_indices = [None] * self.IMAGE_OUTPUT_COUNT
        global_image_indices = []
        for idx, name in enumerate(self.IMAGE_INPUT_NAMES):
            value = self._get_input_value(
                inputs,
                name,
                self.IMAGE_LEGACY_NAMES[idx] if idx < len(self.IMAGE_LEGACY_NAMES) else None,
            )
            if value is not None:
                provided_images.append(value)
                image_idx = len(provided_images) - 1
                if idx < self.IMAGE_OUTPUT_COUNT:
                    primary_image_indices[idx] = image_idx
                else:
                    global_image_indices.append(image_idx)

        if not provided_images:
            raise ValueError("请至少输入一张参考图像。")

        image_groups = None
        if split_mode:
            target_pairs = len(dispatch_prompts)
            if target_pairs < 1:
                raise ValueError("请至少输入一条提示词用于拆分。")
            for port_idx in range(target_pairs):
                if primary_image_indices[port_idx] is None:
                    raise ValueError(f"图像输入{port_idx + 1} 是必填项，请为第 {port_idx + 1} 个输出提供参考图。")
            image_groups = []
            for port_idx in range(target_pairs):
                indices = [primary_image_indices[port_idx]]
                if global_image_indices:
                    indices.extend(global_image_indices)
                image_groups.append(indices)

        exec_configs = channel_configs
        exec_prompts = dispatch_prompts
        exec_image_groups = image_groups

        skip_save_mask = [False] * self.IMAGE_OUTPUT_COUNT
        output_positions = list(range(self.IMAGE_OUTPUT_COUNT))
        if split_mode:
            output_positions = list(range(len(dispatch_prompts)))

        if output_positions:
            updated_ports = output_positions
        elif exec_image_groups:
            updated_ports = list(range(len(exec_image_groups)))
        else:
            updated_ports = [0]

        if output_positions:
            updated_ports = output_positions
        elif exec_image_groups:
            updated_ports = list(range(len(exec_image_groups)))
        else:
            updated_ports = [0]

        edit_result = self._run_edit(
            api_key_clean,
            model_value,
            exec_prompts,
            aspect_value,
            image_size_value,
            provided_images,
            match_reference_size,
            exec_configs,
            relay_clean,
            image_groups=exec_image_groups,
            output_positions=output_positions,
            seed=seed_value,
        )
        return self._format_output(edit_result, updated_ports, skip_save_mask)

    def _run_edit(
        self,
        api_key: str,
        model_value: str,
        prompts: List[str],
        aspect_value: str,
        image_size_value: str,
        images: List[torch.Tensor],
        match_reference_size: bool,
        channel_configs: List[dict],
        relay_base_url: str,
        image_groups: Optional[List[List[int]]] = None,
        output_positions: Optional[List[int]] = None,
        seed: int = 0,
    ):
        base_files = self._collect_files(images)
        if not base_files:
            raise ValueError("At least one image is required for editing.")

        endpoint = build_endpoint(relay_base_url, EDIT_ENDPOINT_PATH)

        def clone_files(entries):
            return [(field, (meta[0], meta[1], meta[2])) for field, meta in entries]

        def files_for_indexes(indexes: Optional[List[int]]):
            if not indexes:
                return base_files
            selected = []
            for idx in indexes:
                if idx < 0 or idx >= len(base_files):
                    raise ValueError(f"Image index {idx} is out of range for provided references.")
                selected.append(base_files[idx])
            return selected

        def single_call(channel_config: dict, prompt_value: str, extra: Optional[dict] = None):
            current_key = channel_config["key"]
            aspect_for_call = channel_config.get("aspect") or aspect_value
            image_indexes = extra.get("image_indexes") if extra else None
            selected_entries = files_for_indexes(image_indexes)
            payload = {
                "model": model_value,
                "prompt": prompt_value,
                "aspect_ratio": aspect_for_call,
                "response_format": "url",
            }

            if image_size_value != "Auto":
                payload["image_size"] = image_size_value.lower()

            # 精简日志：只显示关键信息
            prompt_preview = prompt_value[:20] + "..." if len(prompt_value) > 20 else prompt_value
            print(f"[CY图片编辑] 请求: model={model_value}, prompt=\"{prompt_preview}\", seed={seed}")

            headers = {"Authorization": f"Bearer {current_key}"}
            res = make_request(
                "post",
                endpoint,
                headers=headers,
                data=payload,
                files=clone_files(selected_entries),
                timeout=REQUEST_TIMEOUT,
            )
            res_json = res.json()
            
            # 统计返回图片数量
            img_count = 0
            if "candidates" in res_json:
                candidates = res_json.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    img_count = sum(1 for p in parts if 'inlineData' in p)
            else:
                entries = extract_image_entries(res_json)
                if entries:
                    img_count = len(entries)
            print(f"[CY图片编辑] 返回: {img_count}张图片")

            target_w = target_h = None
            strict_mode = False
            if match_reference_size and images:
                ref_index = image_indexes[0] if image_indexes else 0
                target_h = images[ref_index].shape[1]
                target_w = images[ref_index].shape[2]
                strict_mode = True

            return download_process(res_json, target_w, target_h, strict_mode)

        extras_payload = None
        multi_output_mode = bool(image_groups)
        if image_groups:
            extras_payload = [{"image_indexes": group} for group in image_groups]

        dispatch_result = self._dispatch_requests(
            single_call,
            channel_configs,
            prompts,
            extras=extras_payload,
            merge=not multi_output_mode,
        )

        if multi_output_mode:
            outputs = [None] * len(self.RETURN_TYPES)
            for idx, item in enumerate(dispatch_result):
                port_idx = output_positions[idx] if output_positions and idx < len(output_positions) else idx
                if port_idx >= len(outputs):
                    break
                if isinstance(item, tuple) and item and item[0] is not None:
                    outputs[port_idx] = item[0]
            if not any(entry is not None for entry in outputs):
                raise RuntimeError("Failed to collect any API responses for multi-output edit.")
            return tuple(outputs)

        return dispatch_result

    @staticmethod
    def _collect_files(images: List[torch.Tensor]):
        files = []
        for idx, img in enumerate(images, start=1):
            files.append(preprocess_image_file(img, f"image_{idx}.png"))
        return files

    @staticmethod
    def _collect_channel_configs(primary_key: str, count: int):
        key_value = (primary_key or "").strip()
        if not key_value:
            return []
        count = max(1, int(count or 1))
        return [{"key": key_value, "aspect": None} for _ in range(count)]

    @staticmethod
    def _split_prompts(prompt: str, max_segments: int = 5):
        if not prompt:
            return []
        parts = [p.strip() for p in re.split(r"(?:\r?\n){2,}", prompt) if p.strip()]
        if not parts:
            return []
        if len(parts) > max_segments:
            print(f"[WARN] 仅保留前 {max_segments} 段提示词，多余的段落将被忽略。")
        return parts[:max_segments]

    def _dispatch_requests(
        self,
        func,
        channel_configs: List[dict],
        prompts: List[str],
        extras: Optional[List[Optional[dict]]] = None,
        merge: bool = True,
    ):
        if not channel_configs:
            raise ValueError("没有可用的 Key 无法发起请求。")

        if len(channel_configs) != len(prompts):
            raise ValueError("提示词数量与 Key 数量不匹配。")

        if extras is not None and len(extras) != len(prompts):
            raise ValueError("Prompt and extras counts do not match for dispatch.")

        tasks = []
        for idx, (config, prompt) in enumerate(zip(channel_configs, prompts)):
            extra = extras[idx] if extras else None
            tasks.append((config, prompt, extra))

        results = [None] * len(tasks)

        failures = []
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {
                executor.submit(func, config, prompt, extra): idx for idx, (config, prompt, extra) in enumerate(tasks)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    # 如果 API 返回 None（没有生成图片），记录但不报错
                    if result is None:
                        print(f"[WARN] API request #{idx + 1} 未返回图片，将跳过")
                    results[idx] = result
                except Exception as exc:  # noqa: BLE001
                    failures.append({"idx": idx, "exc": exc})
                    print(f"[WARN] API request #{idx + 1} failed: {exc}")

        # 过滤掉 None 结果
        valid_results = [r for r in results if r is not None]
        
        # 统计成功和失败的请求
        success_count = len(valid_results)
        total_count = len(tasks)
        
        if success_count < total_count:
            print(f"[CY图片编辑] 部分请求失败: {success_count}/{total_count} 个请求成功")
        
        # 如果所有请求都失败了，才抛出异常
        if not valid_results:
            if failures:
                raise failures[0]["exc"]
            else:
                raise RuntimeError("所有 API 请求都未返回图片")

        return self._merge_results(valid_results) if merge else results

    @staticmethod
    def _merge_results(results):
        filtered = [item for item in results if item is not None]
        if not filtered:
            raise RuntimeError("Failed to collect any API responses.")

        if len(filtered) == 1:
            return filtered[0]

        tensors = []
        shapes = set()
        for item in filtered:
            if isinstance(item, tuple) and item:
                tensor = item[0]
                tensors.append(tensor)
                shapes.add((tensor.shape[1], tensor.shape[2]))

        if not tensors:
            return filtered[-1]

        if len(shapes) > 1:
            raise ValueError(
                "Received images with different resolutions from parallel requests. "
                "请保持宽高比一致或分开运行不同宽高比的任务。"
            )

        combined = torch.cat(tensors, dim=0)
        return (combined,)

    @staticmethod
    def _get_input_value(source: dict, *names, default=None):
        for name in names:
            if not name:
                continue
            if name in source and source[name] is not None:
                return source[name]
        return default

    def _format_output(self, result, updated_ports=None, skip_mask=None):
        """格式化输出为正确的元组格式"""
        skip_flags = skip_mask or [False] * len(self.RETURN_TYPES)
        outputs = [None] * len(self.RETURN_TYPES)
        refreshed_order = list(updated_ports or [])

        def normalize_value(value):
            if isinstance(value, (tuple, list)) and len(value) == 1:
                inner = value[0]
                if isinstance(inner, torch.Tensor):
                    return inner
            return value

        def assign_value(port_index: int, value):
            value = normalize_value(value)
            if value is not None and port_index < len(outputs):
                outputs[port_index] = value

        if isinstance(result, tuple) and len(result) == len(self.RETURN_TYPES):
            for idx, value in enumerate(result):
                assign_value(idx, value)
        elif isinstance(result, (tuple, list)):
            seq = list(result)
            if refreshed_order:
                for seq_idx, port_idx in enumerate(refreshed_order):
                    if seq_idx >= len(seq):
                        break
                    assign_value(port_idx, seq[seq_idx])
            elif seq:
                assign_value(0, seq[0])
        elif result is not None:
            assign_value(0, result)

        for idx, skip in enumerate(skip_flags):
            if skip and idx < len(outputs):
                outputs[idx] = None

        return tuple(outputs)


NODE_CLASS_MAPPINGS = {"CYImageEdit": CYImageEdit}
NODE_DISPLAY_NAME_MAPPINGS = {"CYImageEdit": CYImageEdit.DISPLAY_NAME}
