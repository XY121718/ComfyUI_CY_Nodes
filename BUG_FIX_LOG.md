# BUG 修复日志

## 2026-03-22: 教程弹窗、顶部按钮与版本显示问题（已修复）

### 问题现象
- 节点顶部新增教程入口后，按钮位置反复和节点标题、输出口、右上角标识发生遮挡
- 右上角外链按钮在不同节点高度下容易被端口或标签挡住，甚至出现“看得见点不到”
- 教程弹窗初版层次过多、字体偏小，长时间阅读容易眼花
- 更新弹窗把 Git 提交短哈希直接显示成“当前版本 / 最新版本”，用户无法直观看到插件版本号

### 根本原因
- 顶部按钮绘制层和节点实际可点击区域没有完全对齐，导致按钮布局一变就容易遮挡或失去命中
- 教程弹窗初版强调块和卡片层级过多，更像控制面板，不适合阅读型内容
- 更新弹窗直接使用 `local_commit` / `remote_commit` 填充“版本”字段，缺少 `plugin_version` 的单独展示

### 修复方案
- 重新整理节点顶部按钮布局：
  - 顶部中间保留 `使用教程`
  - 右上角改为 `在线生图`
  - `在线生图` 跳转到 `https://cmagic.xheai.cc`
- 将 `检查更新`、`直达星核AI` 收纳到教程弹窗头部，避免继续挤占节点顶部空间
- 教程弹窗改为更适合阅读的浅色方案，并放大标题、目录、正文等关键字号
- 更新弹窗改为同时显示：
  - 插件版本号
  - 当前本地提交
  - GitHub 最新提交

### 验证结果
- `web/cy_banana_ui.js` 通过 `node --check`
- 教程弹窗可正常打开，头部按钮可点击
- 更新弹窗现在显示 `1.0.1` 这样的插件版本号，不再把提交哈希误显示为版本
- `在线生图` 按钮跳转地址已更新为 `https://cmagic.xheai.cc`

### 额外说明
- 更新检查仍然是“用户点击时主动检查”，不是后台自动轮询
- GitHub 更新比对仍然保留提交级精度，只是展示上增加了更直观的版本号

---

## 2026-03-22: 图生图 `/v1/images/edits` 请求格式不兼容（已修复）

### 问题现象
- `CY图片编辑` 节点调用 `https://api.xheai.cc/v1/images/edits` 时返回 400 或 500
- 典型报错：
  - `Model name not specified, model name cannot be empty`
  - `contents is required`
- Apifox 按文档使用 `multipart/form-data` 发送同样失败
- 文生图正常，但图生图始终报错，容易误判为节点封装错误或中转站异常

### 根本原因
当前 `api.xheai.cc` 这条图生图链路的**实际线上行为**和文档标注不一致：

- 文档标注：`/v1/images/edits` 使用 OpenAI 风格 `multipart/form-data`
- 实际测试：该格式无法被正确解析
- 当前可用格式：`application/json` + base64 图片字段

也就是说，这个接口虽然统一返回 OpenAI 风格结果，但在当前中转实现上，请求侧并不真正兼容文档中的 OpenAI multipart 图生图格式。

### 修复方案
将 `CY_Edit_Image.py` 中图生图请求由 `multipart/form-data` 改为 JSON 请求：

```python
payload = {
    "model": model_value,
    "prompt": prompt_value,
    "aspect_ratio": aspect_for_call,
    "image_size": image_size_value,
    "image": image_payloads[0] if len(image_payloads) == 1 else image_payloads,
}

headers = {
    "Authorization": f"Bearer {current_key}",
    "Content-Type": "application/json",
}

res = make_request(
    "post",
    endpoint,
    headers=headers,
    json=payload,
    timeout=REQUEST_TIMEOUT,
)
```

其中：

- 单图编辑时，`image` 发送单个 base64 字符串
- 多图编辑时，`image` 发送 base64 数组

### 验证结果
- 脱离 ComfyUI 直接请求接口，JSON + base64 可返回 `200`
- 使用 ComfyUI 嵌入 Python 直接调用 `CYImageEdit._run_edit()`，成功返回图片
- Apifox 按文档 `form-data` 请求仍会复现相同错误，因此确认不是节点自身导致

### 额外处理
- 在 `make_request()` 中保留错误响应体打印，便于后续排查中转兼容性问题
- 同步重写 `README.md`，补充本次兼容性说明和使用文档修正

### 排查要点
遇到类似图生图问题时，优先检查：

1. 文档声明的请求格式是否和线上实际实现一致
2. 同一路径是否“返回兼容 OpenAI”，但“请求并不兼容 OpenAI”
3. 中转是否对文生图和图生图走了不同适配链
4. 是否可以通过独立脚本脱离 ComfyUI 复现问题，先排除节点执行链因素

---

## 2026-02-09: 文生图节点宽高比不生效

### 问题现象
- CY文生图节点选择 16:9、4:3 等宽高比，生成的图片始终是 1:1
- CY图片编辑节点宽高比选择正常

### 根本原因
文生图节点发送了**多余参数** `size` 和 `n`，导致 API 忽略 `aspect_ratio` 参数

| 参数 | 图片编辑（正常） | 文生图（异常） |
|------|-----------------|----------------|
| size | ❌ 无 | ⚠️ "1152x864" |
| n    | ❌ 无 | ⚠️ 1 |

### 修复方案
移除 `CY_Text_Image.py` 中的 `size` 和 `n` 参数，保持与官方 API 示例一致：

```python
# ✅ 正确格式
payload = {
    "model": model_value,
    "prompt": prompt_value,
    "aspect_ratio": aspect_for_call,
    "image_size": image_size_value.lower(),  # "1k"
    "response_format": "url",
}
```

### 排查要点
遇到类似问题时检查：
1. 对比正常节点和异常节点的 **payload 参数差异**
2. 参照官方 API 文档，**移除未定义的多余参数**
3. 不同 API 端点可能需要**不同的请求格式**（JSON vs form-data）

---

## 2026-02-09: 并发请求返回损坏数据（已修复）

### 问题现象
- 并发生成多张图片时，部分请求返回 URL 为空
- Base64 数据损坏（不以 `iVBOR` 或 `/9j/4` 开头）
- 日志显示：`[WARN] API 返回数据异常: URL 为空，Base64 解码失败`

### 根本原因
**API 服务器无法正确处理同一 Key 的并发请求**。使用 `ThreadPoolExecutor` 同时发起多个请求时，部分响应数据会被损坏。

调试日志显示：
```
[ThreadPoolExecutor-0_0] 图片1: url=False, b64_len=2364  ❌ 损坏
[ThreadPoolExecutor-0_1] 图片1: url=True, b64_len=0     ✅ 正常
```

### 修复方案
保持**并发执行**，但添加**交错延迟**（参考 Gemini_Imagen_Generator_V2）：

```python
def call_with_delay(task_tuple):
    idx, config, prompt, extra = task_tuple
    # 交错延迟：每个任务间隔 0.5 秒，避免同时发起请求
    if idx > 0:
        delay = min(idx * 0.5, 2.0)  # 最多延迟 2 秒
        time.sleep(delay)
    return idx, func(config, prompt, extra)

# 并发执行，但有交错延迟
with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
    futures = {executor.submit(call_with_delay, task): task[0] for task in tasks}
    ...
```

### 效果
- 请求不再完全同时发送，而是间隔 0.5 秒依次发送
- 保持并发的速度优势，同时避免 API 处理冲突
