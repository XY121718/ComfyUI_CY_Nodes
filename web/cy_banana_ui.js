import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "CY.BananaPro.Fold";
const TEXT_TO_IMAGE_NODES = ["CYTextToImage", "CYImageEdit"];

const LINK_BUTTON_TEXT = "直达星核AI";
const LINK_BUTTON_URL = "https://api.xheai.cc";
const TOKEN_API_PATH = "/api/open/token";
const SUPPORTED_RELAY_URLS = ["https://api.xheai.cc"];

const PROMPT_WIDGET_NAME = "提示词";
const PROMPT_DEFAULT_ROWS = 8;

// 显示分组选择弹窗
function showGroupSelector(groups, onSelect) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.6); z-index: 99999;
        display: flex; align-items: center; justify-content: center;
    `;

    const modal = document.createElement('div');
    modal.style.cssText = `
        background: #2a2a2a; border-radius: 12px; padding: 24px;
        min-width: 320px; max-width: 90vw; color: #fff;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    `;

    const title = document.createElement('h3');
    title.textContent = '选择分组';
    title.style.cssText = 'margin: 0 0 16px; font-size: 18px; font-weight: 600;';
    modal.appendChild(title);

    const hint = document.createElement('p');
    hint.textContent = '该模型存在多个分组，请选择一个：';
    hint.style.cssText = 'margin: 0 0 16px; font-size: 14px; color: #aaa;';
    modal.appendChild(hint);

    const list = document.createElement('div');
    list.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';

    groups.forEach(group => {
        const btn = document.createElement('button');
        btn.textContent = group;
        btn.style.cssText = `
            display: block; width: 100%; padding: 12px 16px;
            background: #3a3a3a; border: 1px solid #4a4a4a;
            color: #fff; border-radius: 8px; cursor: pointer;
            font-size: 14px; text-align: left;
            transition: all 0.2s;
        `;
        btn.onmouseover = () => {
            btn.style.background = '#4a9eff';
            btn.style.borderColor = '#4a9eff';
        };
        btn.onmouseout = () => {
            btn.style.background = '#3a3a3a';
            btn.style.borderColor = '#4a4a4a';
        };
        btn.onclick = () => {
            document.body.removeChild(overlay);
            onSelect(group);
        };
        list.appendChild(btn);
    });

    modal.appendChild(list);

    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = '取消';
    cancelBtn.style.cssText = `
        margin-top: 16px; padding: 10px 20px;
        background: transparent; border: 1px solid #555;
        color: #aaa; border-radius: 6px; cursor: pointer;
        font-size: 14px;
    `;
    cancelBtn.onclick = () => document.body.removeChild(overlay);
    modal.appendChild(cancelBtn);

    overlay.appendChild(modal);
    overlay.onclick = (e) => {
        if (e.target === overlay) document.body.removeChild(overlay);
    };
    document.body.appendChild(overlay);
}

// 显示消息弹窗（成功/失败）
function showMessage(message, isSuccess = true) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.5); z-index: 99999;
        display: flex; align-items: center; justify-content: center;
    `;

    const modal = document.createElement('div');
    modal.style.cssText = `
        background: #2a2a2a; border-radius: 12px; padding: 24px 32px;
        min-width: 280px; max-width: 90vw; color: #fff;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        text-align: center;
    `;

    const icon = document.createElement('div');
    icon.textContent = isSuccess ? '✅' : '❌';
    icon.style.cssText = 'font-size: 48px; margin-bottom: 16px;';
    modal.appendChild(icon);

    const text = document.createElement('p');
    text.textContent = message;
    text.style.cssText = `
        margin: 0 0 20px; font-size: 16px; line-height: 1.5;
        color: ${isSuccess ? '#4ade80' : '#f87171'};
    `;
    modal.appendChild(text);

    const okBtn = document.createElement('button');
    okBtn.textContent = '确定';
    okBtn.style.cssText = `
        padding: 10px 32px; background: ${isSuccess ? '#4a9eff' : '#666'};
        border: none; color: #fff; border-radius: 6px;
        cursor: pointer; font-size: 14px;
    `;
    okBtn.onclick = () => document.body.removeChild(overlay);
    modal.appendChild(okBtn);

    overlay.appendChild(modal);
    overlay.onclick = (e) => {
        if (e.target === overlay) document.body.removeChild(overlay);
    };
    document.body.appendChild(overlay);
    okBtn.focus();
}

// 创建令牌
async function createToken(node, group = null) {
    const relayWidget = node.widgets.find(w => w.name === "中转网址");
    const masterKeyWidget = node.widgets.find(w => w.name === "总Key");
    const modelWidget = node.widgets.find(w => w.name === "模型");
    const key1Widget = node.widgets.find(w => w.name === "Key1");

    if (!masterKeyWidget?.value?.trim()) {
        showMessage("请在总Key随便填入一个有效Key", false);
        return;
    }

    const baseUrl = relayWidget?.value || SUPPORTED_RELAY_URLS[0];
    const tokenApiUrl = baseUrl.replace(/\/+$/, '') + TOKEN_API_PATH;
    const model = modelWidget?.value || "gemini-3-pro-image-preview";

    try {
        const body = { model };
        if (group) body.group = group;

        const resp = await fetch(tokenApiUrl, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${masterKeyWidget.value.trim()}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(body)
        });

        const result = await resp.json();

        if (result.data?.need_select) {
            showGroupSelector(result.data.groups || [], (g) => createToken(node, g));
        } else if (result.success && result.data?.key) {
            if (key1Widget) {
                key1Widget.value = result.data.key;
                if (key1Widget.inputEl) key1Widget.inputEl.value = result.data.key;
            }
            showMessage("令牌创建成功！已自动填入Key1", true);
        } else {
            showMessage("创建失败: " + (result.message || "未知错误"), false);
        }
    } catch (e) {
        showMessage("请求失败: " + e.message, false);
    }
}

// --- 核心修复：添加按钮逻辑 ---
// 关键：不使用 splice！直接 addWidget 把按钮放在数组最后，不会破坏后端的索引映射
function addCreateTokenButton(node) {
    // 检查是否已经添加过按钮
    if (node.widgets.find(w => w.name === "创建令牌")) return;

    const relayWidget = node.widgets.find(w => w.name === "中转网址");
    const masterKeyWidget = node.widgets.find(w => w.name === "总Key");

    if (!relayWidget || !masterKeyWidget) return;

    // 创建按钮 widget - 直接添加到末尾，不使用 splice
    const tokenButton = node.addWidget("button", "创建令牌", "创建令牌", () => {
        createToken(node);
    });

    // 设置按钮显示的文字
    tokenButton.label = "✅ 点击自动创建令牌";

    // 必须为 false，防止被保存到工作流JSON里影响后端
    tokenButton.options = { serialize: false };

    // 动态可见性控制
    const updateVisibility = () => {
        const val = relayWidget?.value || "";
        const isSupported = SUPPORTED_RELAY_URLS.some(url => val.includes(url));
        if (masterKeyWidget) masterKeyWidget.hidden = !isSupported;
        tokenButton.hidden = !isSupported;
    };

    // 监听中转网址变化
    if (relayWidget && !relayWidget.__cyCallbackWrapped) {
        relayWidget.__cyCallbackWrapped = true;
        const oldCallback = relayWidget.callback;
        relayWidget.callback = function () {
            if (oldCallback) oldCallback.apply(this, arguments);
            updateVisibility();
        };
    }

    setTimeout(updateVisibility, 100);
}

// --- 核心修复：提示词高度逻辑 ---
// 使用固定高度赋值，而不是累加，防止刷新时高度无限增长
function setupPromptWidget(node) {
    const promptWidget = node.widgets.find(w => w.name === PROMPT_WIDGET_NAME);
    if (!promptWidget || !promptWidget.inputEl || node.__cyPromptSetup) return;

    node.__cyPromptSetup = true;
    const textarea = promptWidget.inputEl;
    textarea.style.resize = "none";
    textarea.rows = PROMPT_DEFAULT_ROWS;

    // 修复：不要直接累加 size，而是设定一个固定合理的基础高度
    // 如果是新创建的节点（没有保存的高度信息），再进行调整
    if (node.size[1] < 300) {
        node.size[1] = 420;
    }
}

// 添加右上角链接按钮
function addLinkButton(node) {
    if (node.__cyLinkButton) return;
    node.__cyLinkButton = true;

    const oldDraw = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
        if (oldDraw) oldDraw.apply(this, arguments);
        const x = this.size[0] - 80, y = -25, w = 70, h = 18;
        ctx.fillStyle = "#4a9eff";
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 3);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = "10px Arial";
        ctx.textAlign = "center";
        ctx.fillText(LINK_BUTTON_TEXT, x + w / 2, y + h / 2 + 4);
    };

    const oldDown = node.onMouseDown;
    node.onMouseDown = function (e, pos) {
        if (pos[0] >= this.size[0] - 80 && pos[1] <= 0) {
            window.open(LINK_BUTTON_URL, "_blank");
            return true;
        }
        return oldDown ? oldDown.apply(this, arguments) : undefined;
    };
}

// 注册扩展
app.registerExtension({
    name: EXTENSION_NAME,

    async nodeCreated(node) {
        if (!TEXT_TO_IMAGE_NODES.includes(node.comfyClass)) return;

        addLinkButton(node);

        // 放在 setTimeout 确保 Python 端的 Widget 加载完毕
        setTimeout(() => {
            addCreateTokenButton(node);
            setupPromptWidget(node);

            // Key1 设置：修改标签名称和遮罩
            const key1 = node.widgets.find(w => w.name === "Key1");
            if (key1) {
                // 修改显示的标签名称
                key1.label = "Key1（必填，用于生成图片）";
                if (key1.inputEl) {
                    key1.inputEl.type = "password";
                    key1.inputEl.autocomplete = "off";
                }
            }

            // 总Key 设置：修改标签名称和遮罩
            const master = node.widgets.find(w => w.name === "总Key");
            if (master) {
                // 修改显示的标签名称
                master.label = "总Key（选填，用于自动生成Key1）";
                if (master.inputEl) {
                    master.inputEl.type = "password";
                    master.inputEl.autocomplete = "off";
                }
            }

            // 修复复制节点时"生成张数"变成NaN的问题
            if (node.comfyClass === "CYTextToImage") {
                const concurrencyWidget = node.widgets?.find(w => w.name === "生成张数");
                if (concurrencyWidget && (isNaN(concurrencyWidget.value) || concurrencyWidget.value === null || concurrencyWidget.value === undefined)) {
                    concurrencyWidget.value = 1;
                    if (concurrencyWidget.inputEl) {
                        concurrencyWidget.inputEl.value = "1";
                    }
                }
            }
        }, 100);
    }
});

console.log("✅ CY Banana UI 扩展已加载");
