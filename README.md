# ComfyUI CY Nodes 🍌

基于 Gemini API 的 ComfyUI 图像生成和编辑节点，支持文生图、图片编辑、批量生成等功能。

![节点预览](https://img.shields.io/badge/ComfyUI-Custom_Nodes-blue)
![版本](https://img.shields.io/badge/version-1.0.0-green)

---

## ✨ 功能特点

- 🎨 **文生图** - 通过文字描述生成高质量图片
- 🖼️ **图片编辑** - 对现有图片进行 AI 编辑和修改
- 🔄 **批量生成** - 支持同时生成多张图片，提高效率
- 🔑 **自动创建令牌** - 一键生成 API Key（支持 api.xheai.cc）
- 💾 **API Key 自动保存** - 首次输入后自动保存，无需重复填写
- 📐 **多种宽高比** - 支持 1:1、4:3、16:9、9:16 等多种比例
- 🎯 **多种尺寸** - 支持 1K、2K、4K 等多种分辨率

---

## 📦 包含节点

| 节点名称 | 类名 | 功能说明 |
|---------|------|---------|
| **CY文生图** | `CYTextToImage` | 文字描述 → 生成图片 |
| **CY图片编辑** | `CYImageEdit` | 输入图片 + 描述 → 编辑后的图片 |
| **CY保存图片** | `CYSaveImage` | 保存生成的图片到本地 |

---

## 🚀 安装方法

### 方式一：通过 ComfyUI Manager（推荐）

1. 打开 ComfyUI Manager
2. 搜索 `CY Nodes` 或 `ComfyUI_CY_Nodes`
3. 点击 **Install** 安装
4. 重启 ComfyUI

### 方式二：Git 克隆

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/你的用户名/ComfyUI_CY_Nodes.git
```

### 方式三：下载 ZIP

1. 点击 GitHub 页面的 **Code → Download ZIP**
2. 解压到 `ComfyUI/custom_nodes/ComfyUI_CY_Nodes`
3. 重启 ComfyUI

---

## 📖 使用教程

### 🔑 第一步：获取 API Key

你需要一个支持 Gemini API 的中转服务 Key：

| 中转服务 | 网址 | 特点 |
|---------|------|------|
| **星核AI** | https://api.xheai.cc | ✅ 支持自动创建令牌 |

### 🎨 第二步：使用 CY文生图

1. 在节点面板搜索 `CY文生图` 并添加到画布
2. 填写 **Key1**（必填）- 你的 API Key
3. 在 **提示词** 输入框中描述你想生成的图片
4. 选择 **模型**、**宽高比**、**图像尺寸**
5. 连接输出到 **预览图片** 节点
6. 点击 **Queue Prompt** 开始生成

### 🖼️ 第三步：使用 CY图片编辑

1. 在节点面板搜索 `CY图片编辑` 并添加到画布
2. 填写 **Key1**（必填）
3. 将要编辑的图片连接到 **输入1**
4. 在 **提示词** 中描述你想要的修改
5. 运行即可获得编辑后的图片

### ✅ 自动创建令牌功能（推荐）

如果你使用 **api.xheai.cc** 中转服务：

1. 选择中转网址为 `https://api.xheai.cc`
2. 在 **总Key** 中填入你的主 Key
3. 点击 **✅ 点击自动创建令牌** 按钮
4. 系统会自动生成一个临时 Key 并填入 Key1

> 💡 这样可以避免主 Key 泄露，更加安全！

---

## ⚙️ 参数说明

### CY文生图 参数

| 参数名 | 类型 | 说明 |
|-------|------|------|
| 提示词 | 文本 | 描述你想生成的图片内容 |
| 中转网址 | 下拉框 | 选择 API 中转服务地址 |
| 总Key | 文本 | 用于自动创建令牌（选填） |
| Key1 | 文本 | API Key（必填） |
| 模型 | 下拉框 | 选择使用的 AI 模型 |
| 默认宽高比 | 下拉框 | 1:1, 4:3, 16:9, 9:16 等 |
| 图像尺寸 | 下拉框 | 1K, 2K 等分辨率 |
| 生成张数 | 数字 | 同时生成的图片数量 (1-10) |
| 种子 | 数字 | 随机种子，用于复现结果 |

### CY图片编辑 参数

| 参数名 | 类型 | 说明 |
|-------|------|------|
| 输入1-8 | 图像 | 要编辑的原始图片（支持多张） |
| 提示词 | 文本 | 描述你想要的编辑效果 |
| 匹配参考尺寸 | 开关 | 输出图片是否保持原图尺寸 |
| 按行拆分提示词 | 开关 | 多行提示词分别处理 |

---

## 🔧 配置文件

首次使用时，节点会自动创建以下配置文件：

- `config.ini` - 保存 API Key
- `master_key.ini` - 保存总 Key

> ⚠️ 这些文件包含敏感信息，请勿分享！

---

## ❓ 常见问题

### Q: 提示 "请在总Key随便填入一个有效Key"
A: 点击自动创建令牌前，需要先在"总Key"输入框填入你的主 API Key。

### Q: 生成失败，提示 401 错误
A: API Key 无效或已过期，请检查 Key1 是否正确填写。

### Q: 如何更新节点？
A: 通过 ComfyUI Manager 点击 Update，或在命令行执行 `git pull`。

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Google Gemini API](https://ai.google.dev/)
- [星核AI](https://api.xheai.cc)
