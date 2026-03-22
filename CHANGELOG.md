# 更新日志

本文件用于记录插件每次发布的新增功能、修复内容和优化项。

建议阅读方式：

- 想快速知道最近改了什么：看最上面的最新版本
- 想确认某个问题是否修过：配合 [BUG_FIX_LOG.md](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/BUG_FIX_LOG.md) 一起看
- 想了解完整功能说明：查看 [README.md](E:/CY_AI/CY_ComfyUI%20cjks/ComfyUI/custom_nodes/ComfyUI_CY_Nodes/README.md)

---

## 2026-03-22 | v1.0.1

### 新增

- 为 `CY文生图`、`CY图片编辑` 新增节点顶部 `使用教程` 入口
- 新增站内教程弹窗，支持：
  - 教程目录
  - 分步阅读
  - 上一步 / 下一步 / 返回目录 / 关闭
- 教程弹窗头部新增：
  - `检查更新`
  - `直达星核AI`
- 节点右上角新增 `在线生图` 按钮，点击跳转 [cmagic.xheai.cc](https://cmagic.xheai.cc)
- 新增插件更新检查能力：
  - 可检查 GitHub 远程分支最新提交
  - 可一键下载并覆盖当前插件
  - 自动保留本地配置文件

### 修复

- 修复图生图 `/v1/images/edits` 在 `api.xheai.cc` 下请求格式不兼容的问题
- 修复顶部按钮与节点标题、输出口、右上角标识互相遮挡的问题
- 修复部分顶部按钮可见但点击不生效的问题
- 修复更新弹窗把 Git 提交哈希误显示为“版本号”的问题
- 修复旧版 README 中的乱码、过时说明和错误接口行为描述

### 优化

- 教程弹窗改为更适合阅读的浅色风格
- 放大教程标题、目录、摘要、正文等主要字号
- 优化教程内容层级，减少卡片堆叠造成的阅读压力
- 将文案内容拆分到独立教程配置文件，方便后续单独修改
- 更新弹窗现在同时显示：
  - 当前插件版本
  - 当前本地提交
  - GitHub 最新提交

### 兼容性说明

- `https://api.xheai.cc/v1/images/edits` 当前实测可用的是 `application/json + base64 image`
- 该链路当前并不真正兼容文档中标注的 OpenAI `multipart/form-data` 图生图请求格式

### 实测结果

- 使用 ComfyUI 嵌入 Python 对两个核心节点做了真实接口测试
- `CY文生图`：
  - 中转：`https://api.xheai.cc`
  - 模型：`nano-banana-2`
  - 比例：`4:3`
  - 尺寸：`1K`
  - 结果：成功返回 1 张图片
- `CY图片编辑`：
  - 中转：`https://api.xheai.cc`
  - 模型：`nano-banana-2`
  - 比例：`4:3`
  - 尺寸：`1K`
  - 结果：成功返回 1 张图片

### 更新提醒

- `检查更新` 是用户点击时主动检查，不是后台自动轮询
- 更新来源基于当前插件配置的 GitHub 仓库和分支
- 更新时会保留这些本地文件：
  - `config.ini`
  - `config_v2.ini`
  - `master_key.ini`
