# ComfyUI CY Nodes

基于 Gemini / Nano Banana 系列接口的 ComfyUI 自定义节点，提供文生图、图生图编辑和可选保存三个节点。

![ComfyUI](https://img.shields.io/badge/ComfyUI-Custom_Nodes-blue)
![Version](https://img.shields.io/badge/version-1.0.1-green)

## 最近更新

### 2026-03-22 | v1.0.1

- 新增节点顶部 `使用教程` 入口与站内教程弹窗
- 新增 `检查更新`、`直达星核AI`、`在线生图` 相关入口
- 修复图生图在 `api.xheai.cc` 下的请求格式兼容问题
- 修复顶部按钮遮挡和更新弹窗版本显示不正确的问题
- 已实测 `CY文生图` 与 `CY图片编辑` 可以正常返回图片

完整历史请查看：

- [CHANGELOG.md](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/CHANGELOG.md)
- [BUG_FIX_LOG.md](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/BUG_FIX_LOG.md)

---

## 节点概览

本插件当前包含 3 个节点：

| 节点名 | 类名 | 作用 |
|---|---|---|
| `CY文生图` | `CYTextToImage` | 根据提示词生成图片，支持并发生成和按行拆分提示词 |
| `CY图片编辑` | `CYImageEdit` | 对输入图片进行编辑，支持多图参考、最多 5 路输出 |
| `初阳图像保存` | `CYOptionalSave` | 保存图片到 ComfyUI 输出目录，允许空输入 |

---

## 当前功能

### 1. CY文生图

- 支持中转地址选择：
  - `https://api.xheai.cc`
  - `https://ai.aicy168.top`
- 支持模型：
  - `gemini-3-pro-image-preview`
  - `gemini-3.1-flash-image-preview`
  - `nano-banana`
  - `nano-banana-2`
  - `nano-banana-2-2k`
  - `nano-banana-2-4k`
- 支持宽高比：
  - `1:1`
  - `4:3`
  - `3:4`
  - `16:9`
  - `9:16`
  - `2:3`
  - `3:2`
  - `21:9`
  - `4:5`
  - `5:4`
- 支持图像尺寸：
  - `1K`
  - `2K`
  - `4K`
- 支持 `生成张数` 并发生成，范围 `1-10`
- 支持 `按行拆分提示词`
  - 使用空行分隔不同提示词
  - 最多处理 5 段
- 支持种子输入
- 自动保存 `Key1`、中转地址和总 Key

### 2. CY图片编辑

- 支持 1 到 8 张输入图
- 支持最多 5 路输出口：`输出1` 到 `输出5`
- 支持多图参考编辑
- 支持 `匹配参考尺寸`
- 支持 `按行拆分提示词`
  - 最多处理 5 段
  - 在拆分模式下，`输入1-输入5` 分别对应 `输出1-输出5`
  - `输入6-输入8` 会作为所有任务共享参考图追加到每一路编辑请求中
- 输入图过大时会自动压缩到最长边不超过 `1536px`
- 返回解析同时兼容：
  - OpenAI 风格 `data[].url / data[].b64_json`
  - Gemini 风格 `candidates[].content.parts[].inlineData`

### 3. 初阳图像保存

- 接收 `IMAGE`
- 支持批量保存
- 允许传入空值，空值时直接跳过
- 自动写入 PNG 元数据：
  - prompt
  - extra_pnginfo
- 输出到 ComfyUI 默认 `output` 目录

---

## 安装

### 方式一：ComfyUI Manager

1. 打开 ComfyUI Manager
2. 搜索 `ComfyUI_CY_Nodes` 或 `CY Nodes`
3. 点击安装
4. 重启 ComfyUI

### 方式二：Git 克隆

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/XY121718/ComfyUI_CY_Nodes.git
```

### 方式三：下载 ZIP

1. 从 GitHub 下载 ZIP
2. 解压到 `ComfyUI/custom_nodes/ComfyUI_CY_Nodes`
3. 重启 ComfyUI

本插件不需要额外安装第三方依赖，默认使用 ComfyUI 环境内已有库。

---

## UI 扩展功能

插件前端脚本位于 [web/cy_banana_ui.js](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/web/cy_banana_ui.js)。

当前提供这些附加 UI 功能：

- 为 `CY文生图` 和 `CY图片编辑` 在节点顶部中间显示“使用教程”按钮
- 在节点右上角显示“在线生图”按钮，点击跳转 [cmagic.xheai.cc](https://cmagic.xheai.cc)
- 教程弹窗内提供“检查更新”和“直达星核AI”按钮
- 为 `CY文生图` 和 `CY图片编辑` 添加“创建令牌”按钮
- 当中转地址为 `https://api.xheai.cc` 时显示“创建令牌”按钮和总 Key 输入
- 自动调整提示词输入框高度
- 更新弹窗显示：
  - 插件版本号
  - 当前本地提交
  - GitHub 最新提交
- 点击“检查更新”时会从 GitHub 检查当前分支的新提交，并可一键覆盖更新插件
- 更新时会保留这些本地配置：
  - `config.ini`
  - `config_v2.ini`
  - `master_key.ini`

`创建令牌` 调用的是：

```text
POST /api/open/token
```

这个按钮只对 `api.xheai.cc` 生效。

“检查更新”不是后台自动轮询，而是用户点击时主动检查一次 GitHub 远程版本。

---

## 快速开始

### 1. 配置 Key

两个核心字段：

- `Key1`
  - 实际请求使用的 API Key
  - 必填
- `总Key（创建令牌用）`
  - 仅在需要点击“创建令牌”按钮时填写
  - 只对 `api.xheai.cc` 有意义

插件会把已输入的 Key 自动保存到本目录下：

- `config.ini`
- `master_key.ini`

### 2. 最简单的文生图流程

```text
CY文生图 -> Preview Image
CY文生图 -> 初阳图像保存
```

### 3. 最简单的图生图流程

```text
LoadImage -> CY图片编辑 -> Preview Image
LoadImage -> CY图片编辑 -> 初阳图像保存
```

---

## 节点说明

## CY文生图

### 输入参数

| 参数 | 类型 | 说明 |
|---|---|---|
| 提示词 | STRING | 生成图片的描述 |
| 中转网址 | COMBO | 当前支持 `api.xheai.cc` 和 `ai.aicy168.top` |
| 总Key | STRING | 用于自动创建令牌，可留空 |
| Key1 | STRING | 实际请求使用的 API Key，必填 |
| 模型 | COMBO | 选择生成模型 |
| 默认宽高比 | COMBO | 输出图片比例 |
| 图像尺寸 | COMBO | `1K / 2K / 4K` |
| 生成张数 | INT | 并发请求数，范围 `1-10` |
| 按行拆分提示词 | BOOLEAN | 开启后按空行拆分提示词，最多 5 段 |
| 种子 | INT | 范围 `0-2147483647` |

### 使用说明

- `生成张数 > 1` 时，不能同时开启 `按行拆分提示词`
- 拆分提示词使用的是“空行分段”，不是单个换行
- 文生图节点输出类型是单个 `IMAGE`，但内部可以承载一批图片
- 如果你把输出接到保存节点，保存节点会把这一批图片全部写出

### 示例

单图生成：

```text
一位赛博朋克风格的女性角色，短发，霓虹雨夜街道，电影级光影，超清细节
```

按行拆分：

```text
一只橘猫坐在窗台上

一只黑狗在草地上奔跑

一只白兔在花园里
```

---

## CY图片编辑

### 输入参数

| 参数 | 类型 | 说明 |
|---|---|---|
| 输入1-输入8 | IMAGE | 输入参考图，至少需要 1 张 |
| 提示词 | STRING | 编辑要求 |
| 中转网址 | COMBO | 当前支持 `api.xheai.cc` 和 `ai.aicy168.top` |
| 总Key | STRING | 用于自动创建令牌，可留空 |
| Key1 | STRING | 实际请求使用的 API Key，必填 |
| 模型 | COMBO | 选择编辑模型 |
| 默认宽高比 | COMBO | 输出比例 |
| 图像尺寸 | COMBO | `1K / 2K / 4K` |
| 匹配参考尺寸 | BOOLEAN | 开启后按参考图尺寸回缩输出 |
| 按行拆分提示词 | BOOLEAN | 最多拆分 5 段 |
| 种子 | INT | 当前用于日志和流程控制，不直接作为接口字段发送 |

### 输出说明

| 输出口 | 说明 |
|---|---|
| 输出1 | 编辑结果 1 |
| 输出2 | 编辑结果 2 |
| 输出3 | 编辑结果 3 |
| 输出4 | 编辑结果 4 |
| 输出5 | 编辑结果 5 |

### 普通模式

- 只要接入至少 1 张图片即可
- 多张输入图会一起作为参考图发给接口
- 节点会尝试从接口响应中收集多张图并映射到输出口

### 按行拆分模式

在这个模式下：

- 最多支持 5 段提示词
- 第 1 段提示词使用 `输入1`
- 第 2 段提示词使用 `输入2`
- 第 3 段提示词使用 `输入3`
- 第 4 段提示词使用 `输入4`
- 第 5 段提示词使用 `输入5`
- `输入6-输入8` 会附加到每一段任务里作为共享参考图

如果你开启了拆分模式，但缺少某一路对应输入图，节点会直接报错。

### 实际兼容性说明

这是当前最重要的一条：

- 很多中转文档把 `/v1/images/edits` 写成 OpenAI 风格的 `multipart/form-data`
- 但针对 `https://api.xheai.cc/v1/images/edits` 的当前实测结果，`multipart/form-data` 会返回：
  - `Model name not specified`
  - 或 `contents is required`
- 当前插件已经改为使用 `application/json` 请求图生图：
  - `model`
  - `prompt`
  - `aspect_ratio`
  - `image_size`
  - `image`
- 其中 `image` 实际发送的是 base64 字符串
  - 单图时发送单个字符串
  - 多图时发送数组

这不是 README 的推测，而是对当前中转接口的实测兼容结果。

如果你切换到别的中转站，而对方只接受严格的 OpenAI multipart 图生图格式，那么当前版本可能需要再做兼容分支。

### 编辑示例

背景替换：

```text
把背景改成海边日落，保留人物主体和原始姿势
```

去字：

```text
去掉画面中的所有文字，保持原构图不变
```

多图融合：

```text
把图1中的人物自然融合到图2的场景中，参考图3的色调
```

---

## 初阳图像保存

### 输入参数

| 参数 | 类型 | 说明 |
|---|---|---|
| images | IMAGE | 要保存的图片，可以为空 |
| filename_prefix | STRING | 文件名前缀，默认 `ComfyUI` |

### 保存行为

- 空输入时直接跳过，不报错
- 批量图像会全部保存
- 文件名格式类似：

```text
ComfyUI_00001_.png
```

- 默认输出目录是 ComfyUI 的 `output` 目录

---

## 配置文件

插件会在当前目录下自动维护两个配置文件：

| 文件 | 作用 |
|---|---|
| `config.ini` | 保存 `Key1` 和中转地址 |
| `master_key.ini` | 保存总 Key |

这两个文件都包含敏感信息，不要上传到公开仓库。

---

## 常见问题

### 1. 为什么图生图接口文档写的是 form-data，但实际不通？

因为当前线上实现和文档不一致。我们已经直接验证过：

- Apifox 按文档发 `form-data` 会失败
- 本地脚本按文档发 `form-data` 会失败
- 插件按 `JSON + base64` 发可以成功

### 2. 为什么文生图能用，图生图却不通？

因为这两个接口不是同一条适配链。文生图当前走的是图片生成接口，图生图当前在该中转上表现出另一套实际入参要求。

### 3. 图生图为什么会自动压缩输入图？

当前编辑节点会把输入图最长边限制到 `1536px`，这是插件的上传前预处理逻辑，用来控制请求体大小和兼容性。

### 4. 按行拆分提示词为什么不生效？

请确认：

- 你用的是空行分隔，不是单个换行
- 段数没有超过 5
- 对于图生图拆分模式，`输入1-输入N` 已按段数接好

### 5. 保存节点为什么没有输出文件？

如果传入的是空图，保存节点会直接跳过，这属于设计行为，不是错误。

### 6. 创建令牌按钮为什么没显示？

只有当中转地址是 `https://api.xheai.cc` 时，这个按钮才会显示。

---

## 推荐工作流

### 文生图

```text
CY文生图 -> Preview Image
CY文生图 -> 初阳图像保存
```

### 文生图批量候选

```text
CY文生图(生成张数=4) -> Preview Image
CY文生图(生成张数=4) -> 初阳图像保存
```

### 图生图编辑

```text
LoadImage -> CY图片编辑 -> Preview Image
LoadImage -> CY图片编辑 -> 初阳图像保存
```

### 多图参考编辑

```text
LoadImage(主体) ----\
LoadImage(场景) -----> CY图片编辑 -> Preview Image
LoadImage(色调参考) -/
```

---

## 维护说明

如果你继续维护这个插件，建议优先关注以下文件：

- [CY_Text_Image.py](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/CY_Text_Image.py)
- [CY_Edit_Image.py](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/CY_Edit_Image.py)
- [CY_Save_Image.py](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/CY_Save_Image.py)
- [web/cy_banana_ui.js](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/web/cy_banana_ui.js)

---

## 许可证

MIT License
