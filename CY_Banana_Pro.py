import base64
import configparser
import io
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import numpy as np
import requests
import torch
import urllib3
from PIL import Image, ImageOps

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

RELAY_BASE_URL = "https://ai.aicy168.top"
API_ENDPOINT = f"{RELAY_BASE_URL}/v1/images/generations"
EDIT_ENDPOINT = f"{RELAY_BASE_URL}/v1/images/edits"
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
    "nano-banana": "nano-banana",
    "nano-banana-2": "nano-banana-2",
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


def _extract_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return url.rstrip("/")

def smart_resize(image, target_width, target_height):
    """Resize and center-crop while preserving quality."""
    return ImageOps.fit(image, (target_width, target_height), method=Image.LANCZOS)


def tensor_to_pil(image_tensor):
    if len(image_tensor.shape) > 3:
        image_tensor = image_tensor[0]
    array = np.clip(image_tensor.cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(array)

def preprocess_reference_image(image_tensor, max_side=1568):
    """Prepare reference images by limiting size and converting to JPEG base64."""
    pil = tensor_to_pil(image_tensor)
    w, h = pil.size
    if w > max_side or h > max_side:
        ratio = min(max_side / w, max_side / h)
        pil = pil.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buffered = io.BytesIO()
    pil.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def preprocess_image_file(image_tensor, filename, max_side=1568):
    """Prepare PNG bytes for the edit endpoint while preserving transparency."""
    pil = tensor_to_pil(image_tensor)
    w, h = pil.size
    if w > max_side or h > max_side:
        ratio = min(max_side / w, max_side / h)
        pil = pil.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buffered = io.BytesIO()
    pil.save(buffered, format="PNG")
    buffered.seek(0)
    return ("image", (filename, buffered.getvalue(), "image/png"))


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
            sleep_time = min(backoff ** attempt, 20)
            time.sleep(sleep_time)
    if last_error:
        raise last_error
    raise RuntimeError("Unknown request failure")


def poll_task_result(task_id, api_key, retries=2, delay=5):
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


def download_process(response_json, target_w=None, target_h=None, strict_mode=False):
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
                except:
                    pass
            elif "url" in item:
                try:
                    res = requests.get(item["url"], timeout=60, verify=False)
                    if res.status_code == 200:
                        image_objects.append(Image.open(io.BytesIO(res.content)).convert("RGB"))
                except:
                    pass
    elif "choices" in response_json:
        content = response_json["choices"][0]["message"]["content"]

        b64_matches = re.findall(r'data:image/\w+;base64,([a-zA-Z0-9+/=]+)', content)
        for b64_str in b64_matches:
            try:
                img = Image.open(io.BytesIO(base64.b64decode(b64_str))).convert("RGB")
                image_objects.append(img)
            except:
                pass

        if not image_objects:
            urls = re.findall(r'(https?://[^\s)\]"]+)', content)
            for url in urls:
                try:
                    res = requests.get(url, timeout=60, verify=False)
                    if res.status_code == 200:
                        image_objects.append(Image.open(io.BytesIO(res.content)).convert("RGB"))
                except:
                    pass
    else:
        raise Exception("No images were returned by the API.")

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
        raise Exception("No image tensors were created from the API response.")

    return (torch.stack(final_tensors),)


class CYGeminiRelay:
    DISPLAY_NAME = "Banana Pro"
    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "IMAGE")
    RETURN_NAMES = ("输出1", "输出2", "输出3", "输出4", "输出5")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def __init__(self):
        self._cached_outputs = [None] * len(self.RETURN_TYPES)

    IMAGE_INPUT_NAMES = [f"输入{i}" for i in range(1, 9)]
    IMAGE_LEGACY_NAMES = [f"image_{i}" for i in range(1, 9)]

    MODEL_MAP = DEFAULT_MODEL_MAP
    MODEL_OPTIONS = list(MODEL_MAP.keys())
    ASPECT_OPTIONS = list(ASPECT_DISPLAY_MAP.keys())
    ASPECT_OVERRIDE_OPTIONS = ["使用全局"] + ASPECT_OPTIONS
    IMAGE_SIZE_OPTIONS = [size for size in IMAGE_SIZE_DISPLAY_MAP.keys() if size != "Auto"]

    @classmethod
    def INPUT_TYPES(cls):
        optional_inputs = {}
        for idx, name in enumerate(cls.IMAGE_INPUT_NAMES):
            optional_inputs[name] = (
                "IMAGE",
                {"forceInput": idx != 0, "label": name},
            )

        for idx in range(2, 6):
            key_label = f"Key{idx}"
            optional_inputs[key_label] = (
                "STRING",
                {
                    "multiline": False,
                    "default": CONFIG["DEFAULT"].get(f"api_key_{idx}", ""),
                    "label": key_label,
                    "fold_group": "extra_keys",
                    "fold_label": "额外 Key",
                    "fold_collapsed": True,
                },
            )
            optional_inputs[f"宽高比（Key{idx}）"] = (
                cls.ASPECT_OVERRIDE_OPTIONS,
                {
                    "default": cls.ASPECT_OVERRIDE_OPTIONS[0],
                    "label": f"宽高比（Key{idx}）",
                    "fold_group": "extra_aspect",
                    "fold_label": "独立宽高比",
                    "fold_collapsed": True,
                },
            )

        for idx in range(len(cls.RETURN_TYPES)):
            optional_inputs[f"刷新输出{idx + 1}"] = (
                "BOOLEAN",
                {"default": False, "label": f"刷新输出{idx + 1}", "display": "button", "label_on": "刷新", "label_off": "刷新"},
            )

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
                "匹配参考尺寸": (
                    "BOOLEAN",
                    {"default": False, "label": "匹配参考尺寸", "label_on": "开启", "label_off": "关闭"},
                ),
                "按行拆分提示词": (
                    "BOOLEAN",
                    {"default": False, "label": "按行拆分提示词", "label_on": "开启", "label_off": "关闭"},
                ),
                "刷新": (
                    "BOOLEAN",
                    {"default": False, "label": "刷新", "label_on": "开启", "label_off": "关闭"},
                ),
            },
            "optional": optional_inputs,
        }

    def run(self, **inputs):
        self._assert_allowed_relay()
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
            saved = CONFIG["DEFAULT"].get(field_name, "").strip()
            return saved

        prompt = self._get_input_value(inputs, "提示词", "prompt", default=DEFAULT_PROMPT)
        split_mode = bool(self._get_input_value(inputs, "按行拆分提示词", "enable_prompt_split", default=False))
        refresh_mode = bool(self._get_input_value(inputs, "刷新", "refresh_mode", default=False))

        if not refresh_mode:
            self._reset_cached_outputs()

        api_key_clean = resolve_key("api_key", "Key1", "api_key")
        if not api_key_clean:
            raise ValueError("Key1 是必填项。")

        model_select = self._get_input_value(inputs, "模型", "model_select", default=self.MODEL_OPTIONS[0])
        aspect_ratio = self._get_input_value(inputs, "默认宽高比", "aspect_ratio", default=self.ASPECT_OPTIONS[0])
        image_size = self._get_input_value(inputs, "图像尺寸", "image_size", default=self.IMAGE_SIZE_OPTIONS[0])
        match_reference_size = bool(
            self._get_input_value(inputs, "匹配参考尺寸", "match_reference_size", default=False)
        )

        extra_api_keys = []
        extra_aspects = []
        for idx in range(2, 6):
            extra_api_keys.append(resolve_key(f"api_key_{idx}", f"Key{idx}", f"api_key_{idx}"))
            extra_aspects.append(
                self._get_input_value(
                    inputs,
                    f"宽高比（Key{idx}）",
                    f"aspect_ratio_key_{idx}",
                    default=self.ASPECT_OVERRIDE_OPTIONS[0],
                )
            )

        if cfg_dirty:
            with CONFIG_PATH.open("w", encoding="utf-8") as fp:
                CONFIG.write(fp)

        model_value = resolve_display_value(model_select, self.MODEL_MAP, "model")
        aspect_value = resolve_display_value(aspect_ratio, ASPECT_DISPLAY_MAP, "aspect ratio")
        image_size_value = resolve_display_value(image_size, IMAGE_SIZE_DISPLAY_MAP, "image size")
        resolved_size = resolve_image_size(image_size_value, aspect_value) if image_size_value != "Auto" else None
        prompt_segments = self._split_prompts(prompt) if split_mode else []
        prompt_list = prompt_segments if prompt_segments else [prompt]

        extra_channel_args = (
            (extra_api_keys[0], extra_aspects[0]),
            (extra_api_keys[1], extra_aspects[1]),
            (extra_api_keys[2], extra_aspects[2]),
            (extra_api_keys[3], extra_aspects[3]),
        )
        channel_configs = self._collect_channel_configs(
            api_key_clean,
            extra_channel_args,
        )
        if not channel_configs:
            raise ValueError("Key1 是必填项。")

        if split_mode:
            needed_channels = len(prompt_list)
            if needed_channels > len(channel_configs):
                raise ValueError(
                    f"{needed_channels} 条提示词需要 {needed_channels} 个 Key，但只提供了 {len(channel_configs)} 个。"
                )
            configs_to_use = channel_configs[:needed_channels]
            dispatch_prompts = prompt_list
        else:
            configs_to_use = [channel_configs[0]]
            dispatch_prompts = [prompt_list[0]]

        provided_images = []
        primary_image_indices = [None] * 5
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
                if idx < 5:
                    primary_image_indices[idx] = image_idx
                else:
                    global_image_indices.append(image_idx)

        image_groups = None
        if provided_images and split_mode:
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

        exec_configs = configs_to_use
        exec_prompts = dispatch_prompts
        exec_image_groups = image_groups
        output_positions = None

        if refresh_mode:
            refresh_indices = self._collect_refresh_requests(inputs)
            refresh_indices = [idx for idx in refresh_indices if idx < len(dispatch_prompts)]
            has_cache = self._has_cached_outputs()
            if not refresh_indices:
                if has_cache:
                    return tuple(self._cached_outputs)
                self._reset_cached_outputs()
                refresh_mode = False
            else:
                exec_configs = [configs_to_use[idx] for idx in refresh_indices]
                exec_prompts = [dispatch_prompts[idx] for idx in refresh_indices]
                if image_groups:
                    exec_image_groups = [image_groups[idx] for idx in refresh_indices]
                else:
                    exec_image_groups = image_groups
                output_positions = refresh_indices

        if not refresh_mode:
            output_positions = list(range(len(self.RETURN_TYPES)))

        if provided_images:
            if not exec_configs:
                raise ValueError("没有需要刷新的输出，至少选择一个有效端口。")

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
                image_groups=exec_image_groups,
                output_positions=output_positions,
            )
            return self._ensure_port_tuple(edit_result, updated_ports=updated_ports, use_cache_fallback=refresh_mode)

        updated_ports = output_positions if output_positions else [0]

        generation_result = self._run_generation(
            api_key_clean,
            model_value,
            dispatch_prompts,
            aspect_value,
            image_size_value,
            resolved_size,
            1,
            configs_to_use,
        )
        return self._ensure_port_tuple(generation_result, updated_ports=updated_ports, use_cache_fallback=refresh_mode)

    def _assert_allowed_relay(self):
        """Ensure all API endpoints still point to the official relay."""
        allowed_base = _extract_base_url(RELAY_BASE_URL)
        endpoints = (API_ENDPOINT, EDIT_ENDPOINT, TASK_ENDPOINT)
        for endpoint in endpoints:
            current_base = _extract_base_url(endpoint)
            if current_base != allowed_base:
                raise ValueError(
                    f"当前中转站 {current_base} 不受支持，请使用 {allowed_base}。"
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

        return self._dispatch_requests(single_call, channel_configs, prompts)

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
        image_groups: Optional[List[List[int]]] = None,
        output_positions: Optional[List[int]] = None,
    ):
        base_files = self._collect_files(images)
        if not base_files:
            raise ValueError("At least one image is required for editing.")

        def clone_files(entries):
            # Duplicate the file tuples so each request has its own payload reference
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
                "response_format": DEFAULT_RESPONSE_VALUE,
            }

            if image_size_value != "Auto":
                payload["image_size"] = image_size_value

            headers = {"Authorization": f"Bearer {current_key}"}
            res = make_request_with_retry(
                "post",
                EDIT_ENDPOINT,
                headers=headers,
                data=payload,
                files=clone_files(selected_entries),
                timeout=REQUEST_TIMEOUT,
            )
            res_json = ensure_image_payload(res.json(), current_key)

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
            single_call, channel_configs, prompts, extras=extras_payload, merge=not multi_output_mode
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
    def _collect_channel_configs(primary_key: str, extras: tuple):
        channels = []

        def add_channel(key_value: str, aspect_selection: Optional[str], label: str):
            if not key_value or not key_value.strip():
                if aspect_selection and aspect_selection != CYGeminiRelay.ASPECT_OVERRIDE_OPTIONS[0]:
                    raise ValueError(f"{label} 设置了独立宽高比但没有提供对应的 Key。")
                return
            channels.append(
                {
                    "key": key_value.strip(),
                    "aspect": CYGeminiRelay._normalize_aspect_override(aspect_selection),
                }
            )

        add_channel(primary_key, None, "Key 1")
        for idx, (key, aspect) in enumerate(extras, start=2):
            add_channel(key, aspect, f"Key {idx}")
        return channels

    def _collect_refresh_requests(self, inputs: dict):
        indices = []
        for idx in range(len(self.RETURN_TYPES)):
            flag = self._get_input_value(inputs, f"刷新输出{idx + 1}", default=False)
            if bool(flag):
                indices.append(idx)
        return indices

    @staticmethod
    def _normalize_aspect_override(selection: Optional[str]):
        if not selection or selection in {"", CYGeminiRelay.ASPECT_OVERRIDE_OPTIONS[0], "Use Global"}:
            return None
        return resolve_display_value(selection, ASPECT_DISPLAY_MAP, "aspect ratio override")

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
        """Use distinct Keys to fire concurrent requests and merge their outputs."""
        if not channel_configs:
            raise ValueError("没有可用的 Key 无法发起请求。")

        if len(channel_configs) != len(prompts):
            raise ValueError("提示词数量与 Key 数量不匹配。")

        if extras is not None and len(extras) != len(prompts):
            raise ValueError("Prompt and metadata counts do not match for dispatch.")

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
                    config, prompt, extra = tasks[idx]
                    failures.append({"idx": idx, "key": config["key"], "prompt": prompt, "exc": exc})
                    print(f"[WARN] API request #{idx + 1} failed: {exc}")

        if failures and len(failures) < len(tasks):
            print(f"[INFO] Retrying {len(failures)} failed requests sequentially...")
            retry_failures = []
            for failure in failures:
                idx = failure["idx"]
                config = channel_configs[idx]
                prompt = failure["prompt"]
                try:
                    extra = tasks[idx][2]
                    results[idx] = func(config, prompt, extra)
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
                "Please keep aspect ratios consistent, enable Match Reference Size, "
                "or run separate nodes per ratio so outputs share the same width/height."
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

    def _ensure_port_tuple(self, result, updated_ports=None, use_cache_fallback=True):
        if not hasattr(self, "_cached_outputs"):
            self._cached_outputs = [None] * len(self.RETURN_TYPES)

        refreshed = set(updated_ports or [])
        if len(result) == len(self.RETURN_TYPES):
            outputs = list(result)
        else:
            outputs = [None] * len(self.RETURN_TYPES)
            if result and isinstance(result, tuple) and result[0] is not None:
                outputs[0] = result[0]

        final_outputs = []
        for idx, value in enumerate(outputs):
            if value is not None:
                self._cached_outputs[idx] = value
                final_outputs.append(value)
            else:
                if use_cache_fallback or idx not in refreshed:
                    final_outputs.append(self._cached_outputs[idx])
                else:
                    final_outputs.append(None)
        return tuple(final_outputs)

    def _reset_cached_outputs(self):
        self._cached_outputs = [None] * len(self.RETURN_TYPES)

    def _has_cached_outputs(self):
        return any(entry is not None for entry in getattr(self, "_cached_outputs", []))
