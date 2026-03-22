import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "CY.BananaPro.Fold";
const TARGET_NODES = ["CYTextToImage", "CYImageEdit"];

const LINK_BUTTON_TEXT = "直达星核AI";
const LINK_BUTTON_URL = "https://api.xheai.cc";
const TOKEN_API_PATH = "/api/open/token";
const SUPPORTED_RELAY_URLS = ["https://api.xheai.cc"];
const RELAY_MODEL_BLACKLIST = {
    "https://api.xheai.cc": ["nano-banana-2-2k", "nano-banana-2-4k"],
};
const FLASH_EXTRA_ASPECT_MODEL = "gemini-3.1-flash-image-preview";
const FLASH_EXTRA_ASPECTS = ["1:4", "4:1", "1:8", "8:1"];

const WIDGET_NAME_PROMPT = "提示词";
const WIDGET_NAME_RELAY = "中转网址";
const WIDGET_NAME_MODEL = "模型";
const WIDGET_NAME_MASTER_KEY = "总Key";
const WIDGET_NAME_KEY1 = "Key1";
const WIDGET_NAME_CREATE_TOKEN = "创建令牌";
const WIDGET_NAME_CONCURRENCY = "生成张数";
const WIDGET_NAME_ASPECT = "默认宽高比";
const WIDGET_NAME_SIZE = "图像尺寸";
const PROMPT_DEFAULT_ROWS = 8;

function normalizeRelayUrl(value) {
    return (value || "").trim().replace(/[\\/]+$/, "");
}

function getRelayBlacklist(relayUrl) {
    return RELAY_MODEL_BLACKLIST[normalizeRelayUrl(relayUrl)] || [];
}

function findWidgetByName(node, name) {
    return node.widgets?.find((widget) => widget.name === name) || null;
}

function findRelayWidget(node) {
    const byName = findWidgetByName(node, WIDGET_NAME_RELAY);
    if (byName) return byName;

    return node.widgets?.find((widget) => {
        const values = widget?.options?.values;
        return Array.isArray(values)
            && values.includes("https://api.xheai.cc")
            && values.includes("https://ai.aicy168.top");
    }) || null;
}

function findModelWidget(node) {
    const byName = findWidgetByName(node, WIDGET_NAME_MODEL);
    if (byName) return byName;

    return node.widgets?.find((widget) => {
        const values = widget?.options?.values;
        return Array.isArray(values)
            && values.includes("nano-banana-2")
            && values.includes("nano-banana-2-2k")
            && values.includes("nano-banana-2-4k");
    }) || null;
}

function findAspectWidget(node) {
    const byName = findWidgetByName(node, WIDGET_NAME_ASPECT);
    if (byName) return byName;

    return node.widgets?.find((widget) => {
        const values = widget?.options?.values;
        return Array.isArray(values)
            && values.includes("1:1")
            && values.includes("4:3")
            && values.includes("16:9")
            && values.includes("21:9");
    }) || null;
}

function wrapWidgetCallback(widget, key, callback) {
    if (!widget || widget[key]) return;
    widget[key] = true;
    const oldCallback = widget.callback;
    widget.callback = function (...args) {
        if (oldCallback) {
            oldCallback.apply(this, args);
        }
        callback(...args);
    };
}

function showGroupSelector(groups, onSelect) {
    const overlay = document.createElement("div");
    overlay.style.cssText = [
        "position:fixed",
        "inset:0",
        "background:rgba(0,0,0,0.6)",
        "z-index:99999",
        "display:flex",
        "align-items:center",
        "justify-content:center",
    ].join(";");

    const modal = document.createElement("div");
    modal.style.cssText = [
        "background:#2a2a2a",
        "border-radius:12px",
        "padding:24px",
        "min-width:320px",
        "max-width:90vw",
        "color:#fff",
        "box-shadow:0 8px 32px rgba(0,0,0,0.4)",
    ].join(";");

    const title = document.createElement("h3");
    title.textContent = "选择分组";
    title.style.cssText = "margin:0 0 16px;font-size:18px;font-weight:600;";
    modal.appendChild(title);

    const hint = document.createElement("p");
    hint.textContent = "该模型存在多个分组，请选择一个：";
    hint.style.cssText = "margin:0 0 16px;font-size:14px;color:#aaa;";
    modal.appendChild(hint);

    const list = document.createElement("div");
    list.style.cssText = "display:flex;flex-direction:column;gap:8px;";

    groups.forEach((group) => {
        const button = document.createElement("button");
        button.textContent = group;
        button.style.cssText = [
            "display:block",
            "width:100%",
            "padding:12px 16px",
            "background:#3a3a3a",
            "border:1px solid #4a4a4a",
            "color:#fff",
            "border-radius:8px",
            "cursor:pointer",
            "font-size:14px",
            "text-align:left",
        ].join(";");
        button.onmouseover = () => {
            button.style.background = "#4a9eff";
            button.style.borderColor = "#4a9eff";
        };
        button.onmouseout = () => {
            button.style.background = "#3a3a3a";
            button.style.borderColor = "#4a4a4a";
        };
        button.onclick = () => {
            document.body.removeChild(overlay);
            onSelect(group);
        };
        list.appendChild(button);
    });

    modal.appendChild(list);

    const cancelButton = document.createElement("button");
    cancelButton.textContent = "取消";
    cancelButton.style.cssText = [
        "margin-top:16px",
        "padding:10px 20px",
        "background:transparent",
        "border:1px solid #555",
        "color:#aaa",
        "border-radius:6px",
        "cursor:pointer",
        "font-size:14px",
    ].join(";");
    cancelButton.onclick = () => document.body.removeChild(overlay);
    modal.appendChild(cancelButton);

    overlay.appendChild(modal);
    overlay.onclick = (event) => {
        if (event.target === overlay) {
            document.body.removeChild(overlay);
        }
    };
    document.body.appendChild(overlay);
}

function showMessage(message, isSuccess = true) {
    const overlay = document.createElement("div");
    overlay.style.cssText = [
        "position:fixed",
        "inset:0",
        "background:rgba(0,0,0,0.5)",
        "z-index:99999",
        "display:flex",
        "align-items:center",
        "justify-content:center",
    ].join(";");

    const modal = document.createElement("div");
    modal.style.cssText = [
        "background:#2a2a2a",
        "border-radius:12px",
        "padding:24px 32px",
        "min-width:280px",
        "max-width:90vw",
        "color:#fff",
        "box-shadow:0 8px 32px rgba(0,0,0,0.4)",
        "text-align:center",
    ].join(";");

    const icon = document.createElement("div");
    icon.textContent = isSuccess ? "✅" : "❌";
    icon.style.cssText = "font-size:48px;margin-bottom:16px;";
    modal.appendChild(icon);

    const text = document.createElement("p");
    text.textContent = message;
    text.style.cssText = [
        "margin:0 0 20px",
        "font-size:16px",
        "line-height:1.5",
        `color:${isSuccess ? "#4ade80" : "#f87171"}`,
    ].join(";");
    modal.appendChild(text);

    const okButton = document.createElement("button");
    okButton.textContent = "确定";
    okButton.style.cssText = [
        "padding:10px 32px",
        `background:${isSuccess ? "#4a9eff" : "#666"}`,
        "border:none",
        "color:#fff",
        "border-radius:6px",
        "cursor:pointer",
        "font-size:14px",
    ].join(";");
    okButton.onclick = () => document.body.removeChild(overlay);
    modal.appendChild(okButton);

    overlay.appendChild(modal);
    overlay.onclick = (event) => {
        if (event.target === overlay) {
            document.body.removeChild(overlay);
        }
    };
    document.body.appendChild(overlay);
    okButton.focus();
}

function updateModelOptionsByRelay(node) {
    const relayWidget = findRelayWidget(node);
    const modelWidget = findModelWidget(node);
    if (!relayWidget || !modelWidget) return;

    const currentValues = modelWidget.options?.values;
    if (!Array.isArray(currentValues)) return;

    if (!Array.isArray(modelWidget.__cyOriginalValues)) {
        modelWidget.__cyOriginalValues = [...currentValues];
    }

    const blacklist = new Set(getRelayBlacklist(relayWidget.value));
    const nextValues = modelWidget.__cyOriginalValues.filter((value) => !blacklist.has(value));
    if (!nextValues.length) return;

    modelWidget.options.values = nextValues;

    if (!nextValues.includes(modelWidget.value)) {
        modelWidget.value = nextValues[0];
        if (modelWidget.inputEl) {
            modelWidget.inputEl.value = nextValues[0];
        }
    }

    node.setDirtyCanvas?.(true, true);
}

function updateAspectOptionsByModel(node) {
    const modelWidget = findModelWidget(node);
    const aspectWidget = findAspectWidget(node);
    if (!modelWidget || !aspectWidget) return;

    const currentValues = aspectWidget.options?.values;
    if (!Array.isArray(currentValues)) return;

    if (!Array.isArray(aspectWidget.__cyOriginalValues)) {
        aspectWidget.__cyOriginalValues = [...currentValues];
    }

    const allowExtra = modelWidget.value === FLASH_EXTRA_ASPECT_MODEL;
    const nextValues = aspectWidget.__cyOriginalValues.filter((value) => {
        if (!FLASH_EXTRA_ASPECTS.includes(value)) {
            return true;
        }
        return allowExtra;
    });
    if (!nextValues.length) return;

    aspectWidget.options.values = nextValues;

    if (!nextValues.includes(aspectWidget.value)) {
        aspectWidget.value = nextValues[0];
        if (aspectWidget.inputEl) {
            aspectWidget.inputEl.value = nextValues[0];
        }
    }

    node.setDirtyCanvas?.(true, true);
}

async function createToken(node, group = null) {
    const relayWidget = findRelayWidget(node);
    const masterKeyWidget = findWidgetByName(node, WIDGET_NAME_MASTER_KEY);
    const modelWidget = findModelWidget(node);
    const key1Widget = findWidgetByName(node, WIDGET_NAME_KEY1);

    if (!relayWidget || !masterKeyWidget || !modelWidget || !key1Widget) {
        showMessage("未找到创建令牌所需控件。", false);
        return;
    }

    if (!masterKeyWidget.value?.trim()) {
        showMessage("请先填写总Key。", false);
        return;
    }

    const baseUrl = normalizeRelayUrl(relayWidget.value || SUPPORTED_RELAY_URLS[0]);
    const tokenApiUrl = `${baseUrl}${TOKEN_API_PATH}`;
    const body = { model: modelWidget.value || "gemini-3-pro-image-preview" };
    if (group) {
        body.group = group;
    }

    try {
        const response = await fetch(tokenApiUrl, {
            method: "POST",
            headers: {
                Authorization: `Bearer ${masterKeyWidget.value.trim()}`,
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });
        const result = await response.json();

        if (result.data?.need_select) {
            showGroupSelector(result.data.groups || [], (selectedGroup) => {
                createToken(node, selectedGroup);
            });
            return;
        }

        if (result.success && result.data?.key) {
            key1Widget.value = result.data.key;
            if (key1Widget.inputEl) {
                key1Widget.inputEl.value = result.data.key;
            }
            showMessage("令牌创建成功，已自动填入 Key1。", true);
            return;
        }

        showMessage(`创建失败: ${result.message || "未知错误"}`, false);
    } catch (error) {
        showMessage(`请求失败: ${error.message}`, false);
    }
}

function addCreateTokenButton(node) {
    if (node.widgets?.find((widget) => widget.name === WIDGET_NAME_CREATE_TOKEN)) {
        return;
    }

    const relayWidget = findRelayWidget(node);
    const masterKeyWidget = findWidgetByName(node, WIDGET_NAME_MASTER_KEY);
    if (!relayWidget || !masterKeyWidget) {
        return;
    }

    const button = node.addWidget("button", WIDGET_NAME_CREATE_TOKEN, WIDGET_NAME_CREATE_TOKEN, () => {
        createToken(node);
    });
    button.label = "✅ 点击自动创建令牌";
    button.options = { serialize: false };

    const refresh = () => {
        const relayUrl = normalizeRelayUrl(relayWidget.value);
        const supported = SUPPORTED_RELAY_URLS.includes(relayUrl);
        masterKeyWidget.hidden = !supported;
        button.hidden = !supported;
        updateModelOptionsByRelay(node);
        updateAspectOptionsByModel(node);
    };

    wrapWidgetCallback(relayWidget, "__cyRelayWrapped", refresh);
    setTimeout(refresh, 0);
}

function setupPromptWidget(node) {
    const promptWidget = findWidgetByName(node, WIDGET_NAME_PROMPT);
    if (!promptWidget?.inputEl || node.__cyPromptSetup) {
        return;
    }

    node.__cyPromptSetup = true;
    promptWidget.inputEl.style.resize = "none";
    promptWidget.inputEl.rows = PROMPT_DEFAULT_ROWS;

    if (node.size?.[1] < 300) {
        node.size[1] = 420;
    }
}

function addLinkButton(node) {
    if (node.__cyLinkButton) {
        return;
    }
    node.__cyLinkButton = true;

    const oldDrawForeground = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
        if (oldDrawForeground) {
            oldDrawForeground.apply(this, arguments);
        }
        const x = this.size[0] - 80;
        const y = -25;
        const width = 70;
        const height = 18;
        ctx.fillStyle = "#4a9eff";
        ctx.beginPath();
        ctx.roundRect(x, y, width, height, 3);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = "10px Arial";
        ctx.textAlign = "center";
        ctx.fillText(LINK_BUTTON_TEXT, x + width / 2, y + height / 2 + 4);
    };

    const oldMouseDown = node.onMouseDown;
    node.onMouseDown = function (event, pos) {
        if (pos[0] >= this.size[0] - 80 && pos[1] <= 0) {
            window.open(LINK_BUTTON_URL, "_blank");
            return true;
        }
        return oldMouseDown ? oldMouseDown.apply(this, arguments) : undefined;
    };
}

function maskKeyWidgets(node) {
    const key1Widget = findWidgetByName(node, WIDGET_NAME_KEY1);
    if (key1Widget?.inputEl) {
        key1Widget.label = "Key1（必填，用于生成图片）";
        key1Widget.inputEl.type = "password";
        key1Widget.inputEl.autocomplete = "off";
    }

    const masterKeyWidget = findWidgetByName(node, WIDGET_NAME_MASTER_KEY);
    if (masterKeyWidget?.inputEl) {
        masterKeyWidget.label = "总Key（选填，用于自动生成Key1）";
        masterKeyWidget.inputEl.type = "password";
        masterKeyWidget.inputEl.autocomplete = "off";
    }
}

function fixConcurrencyWidget(node) {
    if (node.comfyClass !== "CYTextToImage") {
        return;
    }

    const concurrencyWidget = findWidgetByName(node, WIDGET_NAME_CONCURRENCY);
    if (!concurrencyWidget) {
        return;
    }

    if (Number.isNaN(concurrencyWidget.value) || concurrencyWidget.value == null) {
        concurrencyWidget.value = 1;
        if (concurrencyWidget.inputEl) {
            concurrencyWidget.inputEl.value = "1";
        }
    }
}

function bindModelAspectFilter(node) {
    const modelWidget = findModelWidget(node);
    if (!modelWidget) {
        return;
    }

    wrapWidgetCallback(modelWidget, "__cyModelWrapped", () => {
        updateAspectOptionsByModel(node);
    });
}

function refreshComboWidget(node, widgetName, marker) {
    const widget = findWidgetByName(node, widgetName);
    if (!widget || widget[marker]) {
        return;
    }

    widget[marker] = true;
    wrapWidgetCallback(widget, `${marker}_wrapped`, (value) => {
        widget.value = value;
        node.setDirtyCanvas?.(true, true);
    });
}

app.registerExtension({
    name: EXTENSION_NAME,

    async nodeCreated(node) {
        if (!TARGET_NODES.includes(node.comfyClass)) {
            return;
        }

        addLinkButton(node);

        setTimeout(() => {
            addCreateTokenButton(node);
            setupPromptWidget(node);
            maskKeyWidgets(node);
            fixConcurrencyWidget(node);
            bindModelAspectFilter(node);
            refreshComboWidget(node, WIDGET_NAME_ASPECT, "__cyAspectFixed");
            refreshComboWidget(node, WIDGET_NAME_SIZE, "__cySizeFixed");
            updateModelOptionsByRelay(node);
            updateAspectOptionsByModel(node);
        }, 100);
    },
});

console.log("✅ CY Banana UI 扩展已加载");
