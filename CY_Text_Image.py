import base64
import configparser
import io
import re
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

RELAY_BASE_URL = "https://api.xheai.cc"
API_ENDPOINT = f"{RELAY_BASE_URL}/v1/images/generations"
TASK_ENDPOINT = f"{RELAY_BASE_URL}/v1/images/tasks"
REQUEST_TIMEOUT = 300
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
    "Nano-Banana-1": "Nano-Banana-1",
    "Nano-Banana-Pro": "Nano-Banana-Pro",
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

RESPONSE_DISPLAY_MAP = {
    "URL": "url",
    "Base64": "b64_json",
}
DEFAULT_RESPONSE_OPTION = next(iter(RESPONSE_DISPLAY_MAP))
DEFAULT_RESPONSE_VALUE = RESPONSE_DISPLAY_MAP[DEFAULT_RESPONSE_OPTION]

IMAGE_SIZE_DISPLAY_MAP = {
    "Auto": "Auto",
    "1K": "1K",
    "2K": "2K",
    "4K": "4K",
}


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


def extract_task_id(response_json):
    if isinstance(response_json, list):
        for item in response_json:
            if isinstance(item, dict):
                match = extract_task_id(item)
                if match:
                    return match
        return None
    if not isinstance(response_json, dict):
        return None
    if "task_id" in response_json:
        return response_json["task_id"]
    data_block = response_json.get("data")
    if isinstance(data_block, dict) and "task_id" in data_block:
        return data_block["task_id"]
    return None


def make_request_with_retry(method, url, max_retries=5, timeout=REQUEST_TIMEOUT, backoff=2, **kwargs):
    kwargs.setdefault("verify", False)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as exc:
            last_error = exc
            if 400 <= exc.response.status_code < 500:
                raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        if attempt < max_retries:
            sleep_time = min(backoff**attempt, 20)
            time.sleep(sleep_time)
    if last_error:
        raise last_error
    raise RuntimeError("Unknown request failure")


def poll_task_result(task_id, api_key, retries=4, delay=5):
    url = f"{TASK_ENDPOINT}/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    last_response = None
    for attempt in range(1, retries + 1):
        res = make_request_with_retry("get", url, headers=headers, timeout=REQUEST_TIMEOUT)
        last_response = res.json()
        entries = extract_image_entries(last_response)
        status = last_response.get("data", {}).get("status") or last_response.get("status")
        if entries:
            return last_response
        if status and str(status).upper() == "FAILURE":
            raise Exception(f"Task {task_id} failed: {last_response}")
        if attempt < retries:
            time.sleep(min(delay * attempt, 20))
    return last_response


def ensure_image_payload(response_json, api_key, max_polls=4):
    entries = extract_image_entries(response_json)
    if entries:
        return response_json
    task_id = extract_task_id(response_json)
    if not task_id:
        return response_json
    return poll_task_result(task_id, api_key, retries=max_polls)


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
                except Exception:
                    pass
            elif "url" in item:
                try:
                    res = requests.get(item["url"], timeout=60, verify=False)
                    if res.status_code == 200:
                        image_objects.append(Image.open(io.BytesIO(res.content)).convert("RGB"))
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
                    res = requests.get(url, timeout=60, verify=False)
                    if res.status_code == 200:
                        image_objects.append(Image.open(io.BytesIO(res.content)).convert("RGB"))
                except Exception:
                    pass
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
    RETURN_NAMES = ("输出1",)
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
                "提示词": ("STRING", {"multiline": True, "default": DEFAULT_PROMPT, "label": "提示词"}),
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
            },
            "optional": {},
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
        concurrency_raw = self._get_input_value(inputs, "并发通道", "concurrency_channels", default=1)
        try:
            concurrency_value = int(concurrency_raw)
        except (TypeError, ValueError):
            concurrency_value = 1
        concurrency_value = max(1, min(self.MAX_CONCURRENCY, concurrency_value))

        if concurrency_value > 1 and split_mode:
            raise ValueError("并发通道与按行拆分提示词不可同时开启。")

        self._reset_cached_outputs()

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

        default_output_positions = [0]

        generation_result = self._run_generation(
            api_key_clean,
            model_value,
            dispatch_prompts,
            aspect_value,
            image_size_value,
            resolved_size,
            1,
            channel_configs,
        )
        return self._ensure_port_tuple(
            generation_result, updated_ports=default_output_positions, use_cache_fallback=False
        )

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
        multi_output: bool = False,
    ):
        def single_call(channel_config: dict, prompt_value: str, extra: Optional[dict] = None):
            current_key = channel_config["key"]
            aspect_for_call = channel_config.get("aspect") or aspect_value
            payload = {
                "model": model_value,
                "prompt": prompt_value,
                "aspect_ratio": aspect_for_call,
                "response_format": DEFAULT_RESPONSE_VALUE,
                "n": count,
            }

            if image_size_value != "Auto":
                payload["image_size"] = image_size_value
                if resolved_size:
                    payload["size"] = resolved_size

            headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
            res = make_request_with_retry("post", API_ENDPOINT, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            res_json = ensure_image_payload(res.json(), current_key)
            return download_process(res_json)

        return self._dispatch_requests(single_call, channel_configs, prompts, merge=True)

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

        if failures and len(failures) < len(tasks):
            print(f"[INFO] Retrying {len(failures)} failed requests sequentially...")
            retry_failures = []
            for failure in failures:
                idx = failure["idx"]
                try:
                    extra = tasks[idx][2]
                    results[idx] = func(channel_configs[idx], prompts[idx], extra)
                    print(f"[OK] Retry #{idx + 1} succeeded.")
                except Exception as retry_exc:  # noqa: BLE001
                    retry_failures.append({"idx": idx, "exc": retry_exc})
                    print(f"[ERR] Retry #{idx + 1} failed again: {retry_exc}")
            failures = retry_failures

        if not any(results) and failures:
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
