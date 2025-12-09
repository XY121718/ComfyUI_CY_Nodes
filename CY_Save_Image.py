import json
import os
from typing import List, Optional

import numpy as np
import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths
from comfy.cli_args import args


def _ensure_tensor_batch(images):
    if images is None:
        return []
    if isinstance(images, torch.Tensor):
        if len(images.shape) == 3:
            return [images]
        return list(images)
    if isinstance(images, (list, tuple)):
        collected = []
        for item in images:
            if isinstance(item, torch.Tensor):
                collected.append(item)
        return collected
    return []


class CYOptionalSave:
    DISPLAY_NAME = "初阳图像保存"
    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "初阳"

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.compress_level = 4
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": (
                    "IMAGE",
                    {"tooltip": "允许传入 None。若为 None 则跳过保存。"},
                ),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "ComfyUI",
                        "tooltip": "默认命名前缀，也作为覆盖写入的文件名。",
                    },
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    def save_images(
        self,
        images=None,
        filename_prefix="ComfyUI",
        prompt=None,
        extra_pnginfo=None,
    ):
        tensor_list = _ensure_tensor_batch(images)
        if not tensor_list:
            return {"ui": {"images": []}}

        first = tensor_list[0]
        height = first.shape[1]
        width = first.shape[2]

        full_output_folder, filename, counter, subfolder, computed_prefix = folder_paths.get_save_image_path(
            filename_prefix, self.output_dir, width, height
        )

        results = []
        for batch_number, image in enumerate(tensor_list):
            array = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))

            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for key, value in extra_pnginfo.items():
                        metadata.add_text(key, json.dumps(value))
            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            target_name = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, target_name), pnginfo=metadata, compress_level=self.compress_level)
            results.append(
                {
                    "filename": target_name,
                    "subfolder": subfolder,
                    "type": self.type,
                }
            )
            counter += 1

        return {"ui": {"images": results}}


NODE_CLASS_MAPPINGS = {
    "CYOptionalSave": CYOptionalSave,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CYOptionalSave": "初阳图像保存",
}
