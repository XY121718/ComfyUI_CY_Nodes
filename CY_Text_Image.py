import base64
import configparser
import io
import json
import random
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
from PIL import Image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_RELAY_BASE_URL = "https://api.xheai.cc"
GENERATION_ENDPOINT_PATH = "/v1/images/generations"
CHAT_ENDPOINT_PATH = "/v1/chat/completions"
REQUEST_TIMEOUT = 600  # 10分钟，等待生图返回

# 需要走 chat/completions 接口的模型
CHAT_API_MODELS = {"gemini-3-pro-image-preview-4k"}
CATEGORY = "初阳"
DEFAULT_PROMPT = "a banana"
CONFIG_PATH = Path(__file__).with_name("config.ini")
CONFIG = configparser.ConfigParser()
if CONFIG_PATH.exists():
    CONFIG.read(CONFIG_PATH, encoding="utf-8")
else:
    CONFIG["DEFAULT"] = {}
    with CONFIG_PATH.open("w", encoding="utf-8") as fp:
        CONFIG.write(fp)

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
    "nano-banana": "nano-banana",
    "nano-banana-2": "nano-banana-2",
    "nano-banana-2-2k": "nano-banana-2-2k",
    "nano-banana-2-4k": "nano-banana-2-4k",
    "「CS」gemini-3-pro-image-preview-4k": "gemini-3-pro-image-preview-4k",
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


def normalize_base_url(candidate: Optional[str]) -> str:
    base = (candidate or "").strip()
    if not base:
        return DEFAULT_RELAY_BASE_URL.rstrip("/")
    return base.rstrip("/").rstrip("\\")


def build_endpoint(base_url: str, path: str) -> str:
    base = normalize_base_url(base_url)
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def resolve_image_size(image_size: str, aspect_ratio: str):
    if image_size not in IMAGE_SIZE_MAP:
        return None
    mapping = IMAGE_SIZE_MAP[image_size]
    return mapping.get(aspect_ratio)


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


def download_process(response_json):
    if "error" in response_json:
        raise Exception(f"API Error: {response_json['error']}")

    image_objects = []

    entries = extract_image_entries(response_json)

    if entries:
        for item in entries:
            if "b64_json" in item:
                try:
                    img = Image.open(io.BytesIO(base64.b64decode(item["b64_json"]))).convert("RGB")
                    image_objects.append(img)
                except Exception as e:
                    print(f"[WARN] Base64 图片解码失败: {e}")
            elif "url" in item:
                try:
                    img = download_image_with_retry(item["url"])
                    image_objects.append(img)
                except Exception as e:
                    print(f"[WARN] 图片下载最终失败: {e}")
    elif "choices" in response_json:
        content = response_json["choices"][0]["message"]["content"]

        b64_matches = re.findall(r"data:image/\w+;base64,([a-zA-Z0-9+/=]+)", content)
        for b64_str in b64_matches:
            try:
                img = Image.open(io.BytesIO(base64.b64decode(b64_str))).convert("RGB")
                image_objects.append(img)
            except Exception as e:
                print(f"[WARN] Base64 图片解码失败: {e}")

        if not image_objects:
            urls = re.findall(r"(https?://[^\s)\]\"']+)", content)
            for url in urls:
                try:
                    img = download_image_with_retry(url)
                    image_objects.append(img)
                except Exception as e:
                    print(f"[WARN] 图片下载最终失败: {e}")
    else:
        raise Exception("No images were returned by the API.")

    final_tensors = []
    base_w = base_h = None

    for i, img in enumerate(image_objects):
        if i == 0:
            base_w, base_h = img.size
        else:
            img = img.resize((base_w, base_h), Image.LANCZOS)

        img_np = np.array(img).astype(np.float32) / 255.0
        final_tensors.append(torch.from_numpy(img_np))

    if not final_tensors:
        raise Exception("No image tensors were created from the API response.")

    return (torch.stack(final_tensors),)


class CYTextToImage:
    DISPLAY_NAME = "CY文生图"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("图像输出",)
    IMAGE_OUTPUT_COUNT = 1
    MAX_CONCURRENCY = 5
    FUNCTION = "run"
    CATEGORY = CATEGORY

    MODEL_MAP = DEFAULT_MODEL_MAP
    MODEL_OPTIONS = list(MODEL_MAP.keys())
    ASPECT_OPTIONS = list(ASPECT_DISPLAY_MAP.keys())
    IMAGE_SIZE_OPTIONS = [size for size in IMAGE_SIZE_DISPLAY_MAP.keys() if size != "Auto"]

    def __init__(self):
        self._cached_outputs = [None] * len(self.RETURN_TYPES)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "提示词": ("STRING", {"multiline": True, "default": DEFAULT_PROMPT, "label": "提示词", "dynamicPrompts": False, "rows": 8}),
                RELAY_FIELD_LABEL: (
                    "STRING",
                    {
                        "multiline": False,
                        "label": RELAY_FIELD_LABEL,
                        "default": CONFIG["DEFAULT"].get(RELAY_CONFIG_FIELD, DEFAULT_RELAY_BASE_URL),
                        "tooltip": "示例：https://api.xheai.cc",
                    },
                ),
                "Key1": (
                    "STRING",
                    {"multiline": False, "label": "Key1（必填）", "default": CONFIG["DEFAULT"].get("api_key", "")},
                ),
                "模型": (cls.MODEL_OPTIONS, {"default": cls.MODEL_OPTIONS[0], "label": "模型"}),
                "默认宽高比": (cls.ASPECT_OPTIONS, {"default": cls.ASPECT_OPTIONS[0], "label": "默认宽高比"}),
                "图像尺寸": (cls.IMAGE_SIZE_OPTIONS, {"default": cls.IMAGE_SIZE_OPTIONS[0], "label": "图像尺寸"}),
                "并发通道": (
                    "INT",
                    {
                        "default": 1,
                        "label": "并发通道",
                        "tooltip": "1=单通道，2-5=多通道",
                        "min": 1,
                        "max": cls.MAX_CONCURRENCY,
                        "step": 1,
                    },
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
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": "randomize",
                        "tooltip": "随机种子，每次生成后自动随机",
                    },
                ),
            },
            "optional": {},
        }

    @classmethod
    def IS_CHANGED(cls, **inputs):
        return inputs.get("种子", random.random())

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
        concurrency_raw = self._get_input_value(inputs, "并发通道", "concurrency_channels", default=1)
        try:
            concurrency_value = int(concurrency_raw)
        except (TypeError, ValueError):
            concurrency_value = 1
        concurrency_value = max(1, min(self.MAX_CONCURRENCY, concurrency_value))

        if concurrency_value > 1 and split_mode:
            raise ValueError("并发通道与按行拆分提示词不可同时开启。")

        self._reset_cached_outputs()

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

        model_select = self._get_input_value(inputs, "模型", "model_select", default=self.MODEL_OPTIONS[0])
        aspect_ratio = self._get_input_value(inputs, "默认宽高比", "aspect_ratio", default=self.ASPECT_OPTIONS[0])
        image_size = self._get_input_value(inputs, "图像尺寸", "image_size", default=self.IMAGE_SIZE_OPTIONS[0])

        if cfg_dirty:
            with CONFIG_PATH.open("w", encoding="utf-8") as fp:
                CONFIG.write(fp)

        model_value = resolve_display_value(model_select, self.MODEL_MAP, "model")
        aspect_value = resolve_display_value(aspect_ratio, ASPECT_DISPLAY_MAP, "aspect ratio")
        image_size_value = resolve_display_value(image_size, IMAGE_SIZE_DISPLAY_MAP, "image size")
        resolved_size = resolve_image_size(image_size_value, aspect_value) if image_size_value != "Auto" else None
        prompt_segments = self._split_prompts(prompt) if split_mode else []
        prompt_list = prompt_segments if prompt_segments else [prompt]

        if split_mode:
            dispatch_prompts = prompt_list
        else:
            dispatch_prompts = [prompt_list[0]] * concurrency_value

        channel_configs = self._collect_channel_configs(api_key_clean, len(dispatch_prompts))
        if not channel_configs:
            raise ValueError("Key1 是必填项。")

        generation_result = self._run_generation(
            api_key_clean,
            model_value,
            dispatch_prompts,
            aspect_value,
            image_size_value,
            resolved_size,
            1,
            channel_configs,
            relay_clean,
        )

        image_output = None
        if isinstance(generation_result, tuple):
            if generation_result:
                image_output = generation_result[0]
        elif generation_result is not None:
            image_output = generation_result

        if image_output is None:
            image_output = generation_result

        return (image_output,)

    def _run_generation(
        self,
        api_key: str,
        model_value: str,
        prompts: List[str],
        aspect_value: str,
        image_size_value: str,
        resolved_size: Optional[str],
        count: int,
        channel_configs: List[dict],
        relay_base_url: str,
    ):
        # 根据模型选择接口
        use_chat_api = model_value in CHAT_API_MODELS
        if use_chat_api:
            endpoint = build_endpoint(relay_base_url, CHAT_ENDPOINT_PATH)
        else:
            endpoint = build_endpoint(relay_base_url, GENERATION_ENDPOINT_PATH)

        def single_call(channel_config: dict, prompt_value: str, extra: Optional[dict] = None):
            current_key = channel_config["key"]
            aspect_for_call = channel_config.get("aspect") or aspect_value
            headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}

            if use_chat_api:
                # Chat completions 接口格式
                payload = {
                    "model": model_value,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt_value,
                        }
                    ],
                }
            else:
                # Images generations 接口格式
                payload = {
                    "model": model_value,
                    "prompt": prompt_value,
                    "aspect_ratio": aspect_for_call,
                    "response_format": "url",
                    "n": count,
                }
                if image_size_value != "Auto":
                    payload["image_size"] = image_size_value
                    if resolved_size:
                        payload["size"] = resolved_size

            res = make_request("post", endpoint, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            res_json = res.json()
            return download_process(res_json)

        image_result = self._dispatch_requests(single_call, channel_configs, prompts, merge=True)
        return image_result

    @staticmethod
    def _collect_channel_configs(primary_key: str, count: int):
        key_value = (primary_key or "").strip()
        if not key_value:
            return []
        count = max(1, int(count or 1))
        return [{"key": key_value, "aspect": None} for _ in range(count)]

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
                    results[idx] = future.result()
                except Exception as exc:  # noqa: BLE001
                    failures.append({"idx": idx, "exc": exc})
                    print(f"[WARN] API request #{idx + 1} failed: {exc}")

        if failures:
            raise failures[0]["exc"]

        return self._merge_results(results) if merge else results

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
                "Please keep aspect ratios consistent."
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

    def _ensure_port_tuple(self, result, updated_ports=None, use_cache_fallback=True, skip_mask=None):
        skip_flags = skip_mask or [False] * len(self.RETURN_TYPES)

        outputs = list(self._cached_outputs)
        refreshed_order = list(updated_ports or [])
        refreshed_set = set(refreshed_order)

        def normalize_value(value):
            if isinstance(value, (tuple, list)) and len(value) == 1:
                inner = value[0]
                if isinstance(inner, torch.Tensor):
                    return inner
            return value

        def assign_value(port_index: int, value):
            value = normalize_value(value)
            if value is not None:
                outputs[port_index] = value
            elif not use_cache_fallback and port_index in refreshed_set:
                outputs[port_index] = None

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
            if skip:
                outputs[idx] = None

        self._cached_outputs = outputs
        return tuple(outputs)

    def _reset_cached_outputs(self):
        self._cached_outputs = [None] * len(self.RETURN_TYPES)

    def _has_cached_outputs(self):
        return any(entry is not None for entry in self._cached_outputs)



NODE_CLASS_MAPPINGS = {"CYTextToImage": CYTextToImage}
NODE_DISPLAY_NAME_MAPPINGS = {"CYTextToImage": CYTextToImage.DISPLAY_NAME}
