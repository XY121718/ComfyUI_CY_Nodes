import { app } from "../../scripts/app.js";
import { CY_NODE_TUTORIALS } from "./cy_node_tutorials.js";

const EXTENSION_NAME = "CY.BananaPro.Fold";
const TARGET_NODES = ["CYTextToImage", "CYImageEdit"];

const LINK_BUTTON_TEXT = "直达星核AI";
const LINK_BUTTON_URL = "https://api.xheai.cc";
const TUTORIAL_BUTTON_TEXT = "📘 使用教程";
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

const TOP_BUTTON_HEIGHT = 18;
const TUTORIAL_BUTTON_Y = 6;
const LINK_BUTTON_Y = 6;
const TUTORIAL_BUTTON_WIDTH = 118;
const LINK_BUTTON_WIDTH = 70;
const LINK_BUTTON_RIGHT_MARGIN = 10;

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

function getTutorialButtonRect(node) {
    return {
        x: Math.max(8, (node.size[0] - TUTORIAL_BUTTON_WIDTH) / 2),
        y: TUTORIAL_BUTTON_Y,
        width: TUTORIAL_BUTTON_WIDTH,
        height: TOP_BUTTON_HEIGHT,
    };
}

function getLinkButtonRect(node) {
    return {
        x: node.size[0] - LINK_BUTTON_WIDTH - LINK_BUTTON_RIGHT_MARGIN,
        y: LINK_BUTTON_Y,
        width: LINK_BUTTON_WIDTH,
        height: TOP_BUTTON_HEIGHT,
    };
}

function isPointInsideRect(pos, rect) {
    return pos[0] >= rect.x
        && pos[0] <= rect.x + rect.width
        && pos[1] >= rect.y
        && pos[1] <= rect.y + rect.height;
}

function drawTopButton(ctx, rect, label, background) {
    ctx.fillStyle = background;
    ctx.beginPath();
    ctx.roundRect(rect.x, rect.y, rect.width, rect.height, 3);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "10px Arial";
    ctx.textAlign = "center";
    ctx.fillText(label, rect.x + rect.width / 2, rect.y + rect.height / 2 + 4);
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

function createTutorialSection(title, items, background, accent) {
    if (!Array.isArray(items) || !items.length) {
        return null;
    }

    const box = document.createElement("div");
    box.style.cssText = [
        `background:${background}`,
        `border-left:4px solid ${accent}`,
        "border-radius:12px",
        "padding:14px 16px",
        "margin-top:14px",
    ].join(";");

    const heading = document.createElement("div");
    heading.textContent = title;
    heading.style.cssText = [
        `color:${accent}`,
        "font-size:13px",
        "font-weight:700",
        "margin-bottom:10px",
    ].join(";");
    box.appendChild(heading);

    items.forEach((item) => {
        const row = document.createElement("div");
        row.textContent = item;
        row.style.cssText = "color:#f3f4f6;font-size:14px;line-height:1.7;margin-bottom:8px;";
        box.appendChild(row);
    });

    return box;
}

function showTutorialModal(nodeType) {
    const tutorial = CY_NODE_TUTORIALS[nodeType];
    if (!tutorial) {
        showMessage("未找到该节点的教程内容。", false);
        return;
    }

    const overlay = document.createElement("div");
    overlay.style.cssText = [
        "position:fixed",
        "inset:0",
        "background:rgba(8,12,20,0.76)",
        "backdrop-filter:blur(4px)",
        "z-index:99999",
        "display:flex",
        "align-items:center",
        "justify-content:center",
        "padding:28px",
    ].join(";");

    const modal = document.createElement("div");
    modal.style.cssText = [
        "width:min(860px, 92vw)",
        "max-height:88vh",
        "overflow:hidden",
        "border-radius:22px",
        "background:#0f1724",
        "border:1px solid rgba(148,163,184,0.14)",
        "box-shadow:0 24px 80px rgba(0,0,0,0.45)",
        "display:flex",
        "flex-direction:column",
        "color:#fff",
    ].join(";");

    const header = document.createElement("div");
    header.style.cssText = [
        "padding:24px 28px 20px",
        "border-bottom:1px solid rgba(148,163,184,0.14)",
        "background:linear-gradient(180deg, rgba(30,41,59,0.96), rgba(17,24,39,0.96))",
    ].join(";");

    const tag = document.createElement("div");
    tag.textContent = "✨ 节点步骤教程";
    tag.style.cssText = "font-size:12px;font-weight:700;color:#93c5fd;letter-spacing:0.06em;margin-bottom:10px;";
    header.appendChild(tag);

    const title = document.createElement("div");
    title.textContent = tutorial.title;
    title.style.cssText = "font-size:30px;font-weight:800;line-height:1.2;margin-bottom:8px;";
    header.appendChild(title);

    const subtitle = document.createElement("div");
    subtitle.textContent = tutorial.subtitle;
    subtitle.style.cssText = "font-size:17px;color:#cbd5e1;line-height:1.75;";
    header.appendChild(subtitle);

    const contentWrap = document.createElement("div");
    contentWrap.style.cssText = "flex:1;overflow:auto;padding:24px 28px 28px;background:#111827;";

    const footer = document.createElement("div");
    footer.style.cssText = [
        "padding:16px 28px 24px",
        "border-top:1px solid rgba(148,163,184,0.12)",
        "display:flex",
        "justify-content:space-between",
        "align-items:center",
        "gap:16px",
        "flex-wrap:wrap",
    ].join(";");

    const status = document.createElement("div");
    status.style.cssText = "font-size:13px;color:#94a3b8;";
    footer.appendChild(status);

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;align-items:center;gap:10px;flex-wrap:wrap;";

    const prevButton = document.createElement("button");
    prevButton.type = "button";
    prevButton.textContent = "⬅ 上一步";
    prevButton.style.cssText = [
        "padding:10px 16px",
        "border-radius:12px",
        "border:1px solid rgba(148,163,184,0.18)",
        "background:#1e293b",
        "color:#e2e8f0",
        "cursor:pointer",
    ].join(";");

    const nextButton = document.createElement("button");
    nextButton.type = "button";
    nextButton.textContent = "下一步 ➜";
    nextButton.style.cssText = [
        "padding:10px 16px",
        "border-radius:12px",
        "border:none",
        "background:linear-gradient(135deg, #3b82f6, #2563eb)",
        "color:#fff",
        "cursor:pointer",
        "font-weight:700",
    ].join(";");

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.textContent = "关闭";
    closeButton.style.cssText = [
        "padding:10px 18px",
        "border-radius:12px",
        "border:1px solid rgba(148,163,184,0.18)",
        "background:rgba(15,23,42,0.92)",
        "color:#f8fafc",
        "cursor:pointer",
    ].join(";");

    actions.appendChild(prevButton);
    actions.appendChild(nextButton);
    actions.appendChild(closeButton);
    footer.appendChild(actions);

    let currentStepIndex = null;

    const closeModal = () => {
        if (overlay.parentNode) {
            overlay.parentNode.removeChild(overlay);
        }
    };

    const updateFooter = () => {
        if (currentStepIndex == null) {
            status.textContent = `当前在目录页，共 ${tutorial.steps.length} 个步骤。`;
            prevButton.disabled = true;
            nextButton.disabled = false;
            prevButton.style.opacity = "0.45";
            nextButton.style.opacity = "1";
            nextButton.style.cursor = "pointer";
            nextButton.textContent = "开始阅读 ➜";
        } else {
            status.textContent = `正在查看第 ${currentStepIndex + 1} 步 / 共 ${tutorial.steps.length} 步`;
            prevButton.disabled = currentStepIndex === 0;
            nextButton.disabled = currentStepIndex === tutorial.steps.length - 1;
            prevButton.style.opacity = currentStepIndex === 0 ? "0.45" : "1";
            nextButton.style.opacity = currentStepIndex === tutorial.steps.length - 1 ? "0.55" : "1";
            nextButton.style.cursor = currentStepIndex === tutorial.steps.length - 1 ? "default" : "pointer";
            nextButton.textContent = currentStepIndex === tutorial.steps.length - 1 ? "已到最后一步" : "下一步 ➜";
        }

        prevButton.style.cursor = prevButton.disabled ? "default" : "pointer";
    };

    const renderDirectory = () => {
        currentStepIndex = null;
        contentWrap.innerHTML = "";

        const introCard = document.createElement("div");
        introCard.style.cssText = [
            "background:#172033",
            "border:1px solid rgba(96,165,250,0.18)",
            "border-radius:16px",
            "padding:18px 20px",
            "margin-bottom:20px",
        ].join(";");

        const introTitle = document.createElement("div");
        introTitle.textContent = "🌟 先看这段，能更快上手";
        introTitle.style.cssText = "font-size:19px;font-weight:800;color:#eaf2ff;margin-bottom:10px;";
        introCard.appendChild(introTitle);

        const introText = document.createElement("div");
        introText.textContent = tutorial.intro || "";
        introText.style.cssText = "font-size:17px;line-height:1.85;color:#cbd5e1;";
        introCard.appendChild(introText);
        contentWrap.appendChild(introCard);

        const listTitle = document.createElement("div");
        listTitle.textContent = "📚 教程目录";
        listTitle.style.cssText = "font-size:22px;font-weight:800;margin-bottom:14px;color:#ffffff;";
        contentWrap.appendChild(listTitle);

        tutorial.steps.forEach((step, index) => {
            const item = document.createElement("button");
            item.type = "button";
            item.style.cssText = [
                "width:100%",
                "text-align:left",
                "background:#182132",
                "border:1px solid rgba(148,163,184,0.12)",
                "border-radius:14px",
                "padding:16px 18px",
                "margin-bottom:10px",
                "cursor:pointer",
                "transition:border-color 0.15s ease, background 0.15s ease",
            ].join(";");
            item.onmouseover = () => {
                item.style.borderColor = "rgba(96,165,250,0.5)";
                item.style.background = "#1c2740";
            };
            item.onmouseout = () => {
                item.style.borderColor = "rgba(148,163,184,0.12)";
                item.style.background = "#182132";
            };
            item.onclick = () => {
                renderStep(index);
                updateFooter();
            };

            const topRow = document.createElement("div");
            topRow.style.cssText = "display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:8px;flex-wrap:wrap;";

            const headingWrap = document.createElement("div");
            headingWrap.style.cssText = "display:flex;align-items:center;gap:10px;min-width:0;";

            const stepNo = document.createElement("div");
            stepNo.textContent = String(index + 1).padStart(2, "0");
            stepNo.style.cssText = "font-size:13px;font-weight:800;color:#93c5fd;background:rgba(37,99,235,0.18);border-radius:999px;padding:6px 9px;flex:0 0 auto;";
            headingWrap.appendChild(stepNo);

            const heading = document.createElement("div");
            heading.textContent = `${step.emoji} ${step.title}`;
            heading.style.cssText = "font-size:21px;font-weight:800;color:#f8fafc;line-height:1.5;";
            headingWrap.appendChild(heading);

            topRow.appendChild(headingWrap);

            const badge = document.createElement("div");
            badge.textContent = "点击查看";
            badge.style.cssText = "font-size:14px;color:#93c5fd;background:rgba(37,99,235,0.12);padding:7px 12px;border-radius:999px;white-space:nowrap;";
            topRow.appendChild(badge);

            item.appendChild(topRow);

            const summary = document.createElement("div");
            summary.textContent = step.summary;
            summary.style.cssText = "font-size:17px;line-height:1.8;color:#aebfd4;padding-left:42px;";
            item.appendChild(summary);

            contentWrap.appendChild(item);
        });
    };

    const renderStep = (index) => {
        const step = tutorial.steps[index];
        if (!step) {
            renderDirectory();
            updateFooter();
            return;
        }

        currentStepIndex = index;
        contentWrap.innerHTML = "";

        const topBar = document.createElement("div");
        topBar.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px;flex-wrap:wrap;";

        const crumb = document.createElement("div");
        crumb.textContent = `${step.emoji} 第 ${index + 1} 步 / 共 ${tutorial.steps.length} 步`;
        crumb.style.cssText = "font-size:16px;font-weight:700;color:#93c5fd;";
        topBar.appendChild(crumb);

        const backButton = document.createElement("button");
        backButton.type = "button";
        backButton.textContent = "↩ 返回目录";
        backButton.style.cssText = [
            "padding:8px 14px",
            "border-radius:999px",
            "border:1px solid rgba(148,163,184,0.18)",
            "background:rgba(30,41,59,0.9)",
            "color:#e2e8f0",
            "cursor:pointer",
            "font-size:15px",
        ].join(";");
        backButton.onclick = () => {
            renderDirectory();
            updateFooter();
        };
        topBar.appendChild(backButton);
        contentWrap.appendChild(topBar);

        const hero = document.createElement("div");
        hero.style.cssText = [
            "background:#172033",
            "border:1px solid rgba(96,165,250,0.16)",
            "border-radius:18px",
            "padding:20px 20px 16px",
            "margin-bottom:18px",
        ].join(";");

        const heroTitle = document.createElement("div");
        heroTitle.textContent = `${step.emoji} ${step.title}`;
        heroTitle.style.cssText = "font-size:28px;font-weight:800;line-height:1.3;margin-bottom:12px;color:#ffffff;";
        hero.appendChild(heroTitle);

        const heroSummary = document.createElement("div");
        heroSummary.textContent = step.summary;
        heroSummary.style.cssText = "font-size:18px;line-height:1.85;color:#cbd5e1;";
        hero.appendChild(heroSummary);
        contentWrap.appendChild(hero);

        const article = document.createElement("div");
        article.style.cssText = [
            "background:#111827",
            "border:1px solid rgba(148,163,184,0.12)",
            "border-radius:16px",
            "padding:18px 18px 6px",
            "margin-bottom:14px",
        ].join(";");

        const articleTitle = document.createElement("div");
        articleTitle.textContent = "正文说明";
        articleTitle.style.cssText = "font-size:17px;font-weight:800;color:#93c5fd;margin-bottom:14px;";
        article.appendChild(articleTitle);

        (step.content || []).forEach((paragraph, paragraphIndex) => {
            const row = document.createElement("div");
            row.style.cssText = "display:flex;align-items:flex-start;gap:12px;margin-bottom:14px;";

            const marker = document.createElement("div");
            marker.textContent = `${paragraphIndex + 1}`;
            marker.style.cssText = "width:26px;height:26px;line-height:26px;text-align:center;border-radius:999px;background:rgba(37,99,235,0.16);color:#93c5fd;font-size:14px;font-weight:800;flex:0 0 auto;margin-top:2px;";
            row.appendChild(marker);

            const text = document.createElement("div");
            text.textContent = paragraph;
            text.style.cssText = "font-size:18px;line-height:1.9;color:#e5edf7;";
            row.appendChild(text);

            article.appendChild(row);
        });
        contentWrap.appendChild(article);

        const tipsSection = createTutorialSection("✨ 实用提示", step.tips, "rgba(16,185,129,0.10)", "#6ee7b7");
        if (tipsSection) {
            contentWrap.appendChild(tipsSection);
        }

        const warningSection = createTutorialSection("⚠️ 注意事项", step.warnings, "rgba(245,158,11,0.10)", "#fbbf24");
        if (warningSection) {
            contentWrap.appendChild(warningSection);
        }

        updateFooter();
    };

    prevButton.onclick = () => {
        if (currentStepIndex == null) {
            return;
        }
        renderStep(Math.max(0, currentStepIndex - 1));
    };

    nextButton.onclick = () => {
        if (currentStepIndex == null) {
            renderStep(0);
            return;
        }
        if (currentStepIndex < tutorial.steps.length - 1) {
            renderStep(currentStepIndex + 1);
        }
    };

    closeButton.onclick = closeModal;

    overlay.onclick = (event) => {
        if (event.target === overlay) {
            closeModal();
        }
    };

    modal.appendChild(header);
    modal.appendChild(contentWrap);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    renderDirectory();
    updateFooter();
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

function addTopActionButtons(node) {
    if (node.__cyTopButtons) {
        return;
    }
    node.__cyTopButtons = true;

    const oldDrawForeground = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
        if (oldDrawForeground) {
            oldDrawForeground.apply(this, arguments);
        }

        if (CY_NODE_TUTORIALS[this.comfyClass]) {
            drawTopButton(ctx, getTutorialButtonRect(this), TUTORIAL_BUTTON_TEXT, "#16a34a");
        }

        drawTopButton(ctx, getLinkButtonRect(this), LINK_BUTTON_TEXT, "#4a9eff");
    };

    const oldMouseDown = node.onMouseDown;
    node.onMouseDown = function (event, pos) {
        if (CY_NODE_TUTORIALS[this.comfyClass] && isPointInsideRect(pos, getTutorialButtonRect(this))) {
            showTutorialModal(this.comfyClass);
            return true;
        }

        if (isPointInsideRect(pos, getLinkButtonRect(this))) {
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
        masterKeyWidget.label = "总Key（选填，用于自动生成 Key1）";
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

        addTopActionButtons(node);

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
