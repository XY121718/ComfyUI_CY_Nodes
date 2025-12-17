import base64
import configparser
import io
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import numpy as np
import requests
import torch
from PIL import Image

CATEGORY = "初阳"
DEFAULT_PROMPT = "请在这里输入你的提示词"
DEFAULT_RELAY_BASE_URL = "https://api.xheai.cc"
REQUEST_TIMEOUT = 600

CONFIG_PATH = Path(__file__).with_name("config_v2.ini")
CONFIG = configparser.ConfigParser()
if CONFIG_PATH.exists():
    CONFIG.read(CONFIG_PATH, encoding="utf-8")
else:
    CONFIG["gemini_v2"] = {"api_key": ""}
    with CONFIG_PATH.open("w", encoding="utf-8") as fp:
        CONFIG.write(fp)

ASPECT_OPTIONS = ["Auto", "1:1", "9:16", "16:9", "21:9", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4"]
IMAGE_SIZE_OPTIONS = ["Auto", "1K", "2K", "4K"]


class CYBananaV2:
    """
    CY Gemini文生图节点 - 支持图像尺寸选择
    """

    DISPLAY_NAME = "CY_Banana_V2 ⚡"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("图像输出", "文本输出")
    FUNCTION = "generate_images"
    OUTPUT_NODE = True
    CATEGORY = CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        api_key_default = CONFIG.get("gemini_v2", "api_key", fallback="")

        return {
            "required": {
                "提示词": ("STRING", {
                    "multiline": True,
                    "default": DEFAULT_PROMPT,
                    "label": "提示词",
                    "dynamicPrompts": False,
                }),
                "中转网址": ("STRING", {
                    "default": DEFAULT_RELAY_BASE_URL,
                    "label": "中转网址",
                }),
                "Key1": ("STRING", {
                    "default": api_key_default,
                    "label": "Key1（必填）",
                }),
                "模型": ("STRING", {
                    "default": "gemini-3-pro-image-preview",
                    "label": "模型",
                }),
                "批次数量": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 8,
                    "label": "批次数量",
                }),
                "默认宽高比": (ASPECT_OPTIONS, {
                    "default": "Auto",
                    "label": "默认宽高比",
                }),
                "图像尺寸": (IMAGE_SIZE_OPTIONS, {
                    "default": "Auto",
                    "label": "图像尺寸",
                }),
            },
            "optional": {
                "seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 102400,
                    "label": "随机种子",
                }),
                "top_p": ("FLOAT", {
                    "default": 0.95,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "label": "Top-P",
                }),
                "并发线程": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": 8,
                    "label": "并发线程",
                    "tooltip": "并发线程数，建议2-4",
                }),
                "请求超时": ("INT", {
                    "default": 180,
                    "min": 30,
                    "max": 600,
                    "label": "请求超时",
                    "tooltip": "单个请求超时时间(秒)",
                }),
                "输入图像1": ("IMAGE",),
                "输入图像2": ("IMAGE",),
                "输入图像3": ("IMAGE",),
                "输入图像4": ("IMAGE",),
                "输入图像5": ("IMAGE",),
            }
        }

    def tensor_to_base64(self, tensor: torch.Tensor) -> str:
        """将tensor转换为base64"""
        img_array = (tensor[0].cpu().numpy() * 255).astype(np.uint8)
        img = Image.fromarray(img_array)
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def base64_to_tensor_single(self, b64_str: str) -> np.ndarray:
        """将单个base64转换为numpy数组"""
        try:
            img_data = base64.b64decode(b64_str)
            img = Image.open(io.BytesIO(img_data)).convert('RGB')
            img_array = np.array(img).astype(np.float32) / 255.0
            return img_array
        except Exception as e:
            print(f"⚠️ 图片解码失败: {str(e)}")
            return np.zeros((64, 64, 3), dtype=np.float32)

    def base64_to_tensor_parallel(self, base64_strings: List[str]) -> torch.Tensor:
        """并发解码多张图片"""
        if not base64_strings:
            return torch.zeros((1, 64, 64, 3), dtype=torch.float32)

        with ThreadPoolExecutor(max_workers=min(4, len(base64_strings))) as executor:
            future_to_index = {executor.submit(self.base64_to_tensor_single, b64): i
                              for i, b64 in enumerate(base64_strings)}

            results = [None] * len(base64_strings)
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    print(f"⚠️ 图片{index + 1}解码异常: {str(e)}")
                    results[index] = np.zeros((64, 64, 3), dtype=np.float32)

            images = [r for r in results if r is not None]

        return torch.from_numpy(np.stack(images))

    def create_request_data(self, prompt: str, seed: int, aspect_ratio: str,
                            image_size: str, top_p: float = 0.65,
                            input_images: List[torch.Tensor] = None) -> Dict:
        """构建请求数据"""
        if seed != -1:
            np.random.seed(seed)
            random.seed(seed)
            style_variations = [
                "detailed, high quality",
                "masterpiece, ultra detailed",
                "photorealistic, stunning",
                "artistic, beautiful composition",
                "vibrant colors, sharp focus"
            ]
            style = style_variations[seed % len(style_variations)]
            final_prompt = f"{prompt}, {style}"
        else:
            final_prompt = prompt

        parts = [{"text": final_prompt}]

        if input_images:
            for image_tensor in input_images:
                if image_tensor is not None:
                    base64_image = self.tensor_to_base64(image_tensor)
                    parts.append({
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64_image
                        }
                    })

        generation_config = {
            "responseModalities": ["IMAGE", "TEXT"],
            "temperature": 0.8,
            "topP": top_p,
            "maxOutputTokens": 8192,
        }

        image_config = {}
        if aspect_ratio and aspect_ratio != "Auto":
            image_config["aspectRatio"] = aspect_ratio
        else:
            image_config["aspectRatio"] = "1:1"

        if image_size and image_size != "Auto":
            image_config["imageSize"] = image_size

        generation_config["imageConfig"] = image_config

        if seed != -1:
            generation_config["seed"] = seed

        request_data = {
            "contents": [{
                "role": "user",
                "parts": parts
            }],
            "generationConfig": generation_config
        }

        return request_data

    def send_request(self, api_key: str, request_data: Dict, model_type: str,
                     api_base_url: str, timeout: int = 180) -> Dict:
        """发送API请求"""
        endpoint = "generateContent"

        if "generativelanguage.googleapis.com" in api_base_url:
            url = f"{api_base_url.rstrip('/')}/v1beta/models/{model_type}:{endpoint}?key={api_key}"
            headers = {'Content-Type': 'application/json'}
        else:
            url = f"{api_base_url.rstrip('/')}/v1beta/models/{model_type}:{endpoint}"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
            }

        session = requests.Session()
        session.headers.update(headers)

        try:
            response = session.post(url, json=request_data, timeout=timeout)
            if response.status_code != 200:
                raise Exception(f"API返回 {response.status_code}: {response.text[:200]}")
            return response.json()
        except requests.exceptions.Timeout:
            raise Exception(f"请求超时({timeout}秒)")
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络错误: {str(e)[:100]}")
        finally:
            session.close()

    def extract_content(self, response_data: Dict) -> Tuple[List[str], str]:
        """提取响应中的图像和文本"""
        base64_images = []
        text_content = ""

        candidates = response_data.get('candidates', [])
        if not candidates:
            raise ValueError("API响应中没有candidates字段")

        content = candidates[0].get('content', {})
        if content is None or content.get('parts') is None:
            return base64_images, text_content

        parts = content.get('parts', [])

        for part in parts:
            if 'text' in part:
                text_content += part['text']
            elif 'inlineData' in part and 'data' in part['inlineData']:
                base64_images.append(part['inlineData']['data'])

        if not base64_images and text_content:
            patterns = [
                r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)',
                r'!\[.*?\]\(data:image/[^;]+;base64,([A-Za-z0-9+/=]+)\)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text_content)
                if matches:
                    base64_images.extend(matches)

        return base64_images, text_content.strip()

    def generate_single_image(self, args):
        """生成单张图片(用于并发)"""
        i, current_seed, api_key, prompt, model_type, aspect_ratio, image_size, top_p, \
            input_images, api_base_url, timeout = args

        task_start = time.time()

        try:
            request_data = self.create_request_data(prompt, current_seed, aspect_ratio,
                                                    image_size, top_p, input_images)
            request_start = time.time()
            response_data = self.send_request(api_key, request_data, model_type, api_base_url, timeout)
            request_time = time.time() - request_start

            base64_images, text_content = self.extract_content(response_data)
            task_time = time.time() - task_start

            print(f"批次 {i + 1} ✅ 完成 - 生成 {len(base64_images)} 张图片 - 耗时 {task_time:.2f}s")

            return {
                'index': i,
                'success': True,
                'images': base64_images,
                'text': text_content,
                'seed': current_seed,
                'time': task_time,
                'request_time': request_time
            }
        except Exception as e:
            task_time = time.time() - task_start
            error_msg = str(e)[:200]
            print(f"批次 {i + 1} ❌ 失败 - 耗时 {task_time:.2f}s - 错误: {error_msg}")
            return {
                'index': i,
                'success': False,
                'error': error_msg,
                'seed': current_seed,
                'time': task_time
            }


    def generate_images(self, **kwargs):
        """主生成函数"""
        prompt = kwargs.get("提示词", DEFAULT_PROMPT)
        api_base_url = kwargs.get("中转网址", DEFAULT_RELAY_BASE_URL)
        model_type = kwargs.get("模型", "gemini-3-pro-image-preview")
        batch_size = kwargs.get("批次数量", 1)
        aspect_ratio = kwargs.get("默认宽高比", "Auto")
        image_size = kwargs.get("图像尺寸", "Auto")
        api_key = kwargs.get("Key1", "")
        seed = kwargs.get("seed", -1)
        top_p = kwargs.get("top_p", 0.95)
        max_workers = kwargs.get("并发线程", 2)
        request_timeout = kwargs.get("请求超时", 180)

        # 获取输入图像
        input_images = []
        for i in range(1, 6):
            img = kwargs.get(f"输入图像{i}")
            if img is not None:
                input_images.append(img)

        # 检查API Key
        if not api_key:
            api_key = CONFIG.get("gemini_v2", "api_key", fallback="")

        if not api_key or api_key in ["your-api-key-here", "your-api-key-here-v2", ""]:
            error_msg = "❌ 请填写 API Key"
            return (torch.zeros((1, 64, 64, 3), dtype=torch.float32), error_msg)

        # 保存API Key到配置
        if api_key != CONFIG.get("gemini_v2", "api_key", fallback=""):
            if "gemini_v2" not in CONFIG:
                CONFIG["gemini_v2"] = {}
            CONFIG["gemini_v2"]["api_key"] = api_key
            with CONFIG_PATH.open("w", encoding="utf-8") as fp:
                CONFIG.write(fp)

        start_time = time.time()

        # 设置种子
        if seed == -1:
            base_seed = random.randint(0, 102400)
        else:
            base_seed = seed

        all_b64_images = []
        all_texts = []

        print(f"\n{'=' * 50}")
        print(f"🎨 CY_Banana_V2 ⚡")
        print(f"{'=' * 50}")
        print(f"批次: {batch_size} 张 | 比例: {aspect_ratio} | 尺寸: {image_size}")
        print(f"并发: {min(max_workers, batch_size)} 线程 | 超时: {request_timeout}秒")
        print(f"{'=' * 50}\n")

        # 并发生成
        if batch_size > 1:
            tasks = []
            for i in range(batch_size):
                current_seed = base_seed + i if seed != -1 else -1
                tasks.append((i, current_seed, api_key, prompt, model_type, aspect_ratio,
                              image_size, top_p, input_images, api_base_url, request_timeout))

            results = []
            actual_workers = min(max_workers, batch_size)

            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                future_to_index = {executor.submit(self.generate_single_image, task): task[0]
                                   for task in tasks}

                for future in as_completed(future_to_index):
                    try:
                        result = future.result(timeout=request_timeout + 30)
                        results.append(result)
                    except TimeoutError:
                        index = future_to_index[future]
                        results.append({
                            'index': index,
                            'success': False,
                            'error': '结果获取超时',
                            'time': 0
                        })
                    except Exception as e:
                        index = future_to_index[future]
                        results.append({
                            'index': index,
                            'success': False,
                            'error': str(e),
                            'time': 0
                        })

            results.sort(key=lambda x: x['index'])

            for result in results:
                if result['success']:
                    all_b64_images.extend(result['images'])
                    if result.get('text'):
                        all_texts.append(f"[批次 {result['index'] + 1}] {result['text']}")
                else:
                    all_texts.append(f"[批次 {result['index'] + 1}] ❌ {result.get('error', '未知错误')}")
        else:
            # 单张生成
            current_seed = base_seed if seed != -1 else -1
            try:
                request_data = self.create_request_data(prompt, current_seed, aspect_ratio,
                                                        image_size, top_p, input_images)
                response_data = self.send_request(api_key, request_data, model_type,
                                                  api_base_url, request_timeout)
                base64_images, text_content = self.extract_content(response_data)

                if base64_images:
                    all_b64_images.extend(base64_images)
                    print(f"✅ 成功生成 {len(base64_images)} 张图片")

                if text_content:
                    all_texts.append(text_content)

            except Exception as e:
                error_msg = f"❌ 生成失败: {str(e)}"
                print(error_msg)
                all_texts.append(error_msg)

        total_time = time.time() - start_time

        if not all_b64_images:
            error_text = f"⚠️ 未生成任何图像\n总耗时: {total_time:.2f}s\n\n" + "\n".join(all_texts)
            return (torch.zeros((1, 64, 64, 3), dtype=torch.float32), error_text)

        print(f"\n🖼️ 解码 {len(all_b64_images)} 张图片...")
        image_tensor = self.base64_to_tensor_parallel(all_b64_images)

        actual_count = len(all_b64_images)
        ratio_text = "自动" if aspect_ratio == "Auto" else aspect_ratio
        size_text = "自动" if image_size == "Auto" else image_size
        success_info = f"✅ 成功生成 {actual_count} 张图像 (比例: {ratio_text}, 尺寸: {size_text})"
        time_info = f"总耗时: {total_time:.2f}s"

        combined_text = f"{success_info}\n{time_info}"
        if all_texts:
            combined_text += "\n\n" + "\n".join(all_texts)

        print(f"\n{'=' * 50}")
        print(f"✅ 完成! 生成 {actual_count} 张图片")
        print(f"{'=' * 50}\n")

        return (image_tensor, combined_text)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "CYBananaV2": CYBananaV2
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CYBananaV2": CYBananaV2.DISPLAY_NAME
}
