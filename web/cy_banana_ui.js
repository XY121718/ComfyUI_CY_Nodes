(function () {
    const EXTENSION_NAME = "CY.BananaPro.Fold";
    const KEY_WIDGET_NAMES = ["Key2", "Key3", "Key4", "Key5"];
    const TEXT_TO_IMAGE_NODES = ["CYTextToImage", "CYImageEdit", "CYBananaV2"];
    const RATIO_WIDGET_NAMES = [
        "\u5bbd\u9ad8\u6bd4\uff08Key2\uff09",
        "\u5bbd\u9ad8\u6bd4\uff08Key3\uff09",
        "\u5bbd\u9ad8\u6bd4\uff08Key4\uff09",
        "\u5bbd\u9ad8\u6bd4\uff08Key5\uff09",
    ];
    const REFRESH_WIDGET_NAMES = [
        "\u5237\u65b0\u8f93\u51fa1",
        "\u5237\u65b0\u8f93\u51fa2",
        "\u5237\u65b0\u8f93\u51fa3",
        "\u5237\u65b0\u8f93\u51fa4",
        "\u5237\u65b0\u8f93\u51fa5",
    ];
    const KEY1_WIDGET_NAME = "Key1\uff08\u5fc5\u586b\uff09";
    const REFRESH_WIDGET_NAME = "\u5237\u65b0";
    const EXTRA_KEY_LABEL = "\u989d\u5916 Key";
    const ASPECT_LABEL = "\u72ec\u7acb\u5bbd\u9ad8\u6bd4";

    // 提示词输入框配置
    const PROMPT_WIDGET_NAME = "提示词";
    const PROMPT_DEFAULT_ROWS = 8;

    // 右上角按钮配置
    const LINK_BUTTON_TEXT = "直达星核AI";
    const LINK_BUTTON_URL = "https://api.xheai.cc";

    function setWidgetsHidden(widgets, hidden) {
        widgets.forEach((widget) => {
            if (widget) {
                widget.hidden = hidden;
            }
        });
    }

    function createFold(node, label, widgets) {
        if (!widgets.length) {
            return;
        }
        const indexes = widgets
            .map((widget) => node.widgets.indexOf(widget))
            .filter((idx) => idx >= 0);
        if (!indexes.length) {
            return;
        }

        const insertIndex = Math.min(...indexes);
        let collapsed = true;
        setWidgetsHidden(widgets, true);

        const toggle = node.addWidget("button", `${label}(\u5c55\u5f00)`, "\u5c55\u5f00", () => {
            collapsed = !collapsed;
            setWidgetsHidden(widgets, collapsed);
            toggle.name = collapsed ? `${label}(\u5c55\u5f00)` : `${label}(\u6298\u53e0)`;
            toggle.value = collapsed ? "\u5c55\u5f00" : "\u6298\u53e0";
            node.graph?.setDirtyCanvas(true, true);
        });
        if (!toggle) {
            return;
        }

        toggle.options = toggle.options || {};
        toggle.options.serialize = false;
        toggle.name = `${label}(\u5c55\u5f00)`;
        toggle.value = "\u5c55\u5f00";

        const currentIndex = node.widgets.indexOf(toggle);
        if (currentIndex > -1 && currentIndex !== insertIndex) {
            node.widgets.splice(currentIndex, 1);
            node.widgets.splice(insertIndex, 0, toggle);
        }
    }

    function enhanceRefreshToggle(refreshToggle, refreshOutputs) {
        if (!refreshToggle || !refreshOutputs.length) {
            return;
        }

        const applyVisibility = () => {
            const enabled = Boolean(refreshToggle.value);
            setWidgetsHidden(refreshOutputs, !enabled);
        };

        const originalCallback = refreshToggle.callback;
        refreshToggle.callback = function (...args) {
            const result = originalCallback ? originalCallback.apply(this, args) : undefined;
            setTimeout(applyVisibility, 0);
            return result;
        };

        applyVisibility();
    }

    function maskKeyWidget(widget) {
        if (!widget || !widget.inputEl || widget.inputEl.__cyMasked) {
            return;
        }
        widget.inputEl.type = "password";
        widget.inputEl.autocomplete = "off";
        widget.inputEl.__cyMasked = true;
    }

    function maskKeyWidgets(widgets) {
        widgets.forEach(maskKeyWidget);
    }

    // 添加右上角链接按钮
    function addLinkButton(node) {
        if (node.__cyLinkButtonAdded) return;
        node.__cyLinkButtonAdded = true;

        const btnWidth = 70;
        const btnHeight = 18;
        const btnPadding = 8;

        // 保存原始的 onDrawForeground
        const originalDrawForeground = node.onDrawForeground;
        node.onDrawForeground = function(ctx) {
            if (originalDrawForeground) {
                originalDrawForeground.call(this, ctx);
            }

            // 计算按钮位置（右上角，标题栏内）
            const x = this.size[0] - btnWidth - btnPadding;
            const y = -LiteGraph.NODE_TITLE_HEIGHT + (LiteGraph.NODE_TITLE_HEIGHT - btnHeight) / 2;

            // 绘制按钮背景
            ctx.fillStyle = "#4a9eff";
            ctx.beginPath();
            ctx.roundRect(x, y, btnWidth, btnHeight, 3);
            ctx.fill();

            // 绘制按钮文字
            ctx.fillStyle = "#ffffff";
            ctx.font = "11px Arial";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(LINK_BUTTON_TEXT, x + btnWidth / 2, y + btnHeight / 2);
        };

        // 保存原始的 onMouseDown
        const originalMouseDown = node.onMouseDown;
        node.onMouseDown = function(e, localPos, graphCanvas) {
            const x = this.size[0] - btnWidth - btnPadding;
            const y = -LiteGraph.NODE_TITLE_HEIGHT + (LiteGraph.NODE_TITLE_HEIGHT - btnHeight) / 2;

            // 检查是否点击了按钮区域
            if (localPos[0] >= x && localPos[0] <= x + btnWidth &&
                localPos[1] >= y && localPos[1] <= y + btnHeight) {
                window.open(LINK_BUTTON_URL, "_blank");
                return true; // 阻止事件继续传播
            }

            if (originalMouseDown) {
                return originalMouseDown.call(this, e, localPos, graphCanvas);
            }
        };
    }

    // 设置提示词输入框样式和高度
    function setupPromptWidget(node) {
        if (!Array.isArray(node.widgets)) return;
        
        // 防止重复设置
        if (node.__cyPromptSetup) return;
        node.__cyPromptSetup = true;

        // 查找提示词 widget（支持多种可能的名称）
        const promptWidget = node.widgets.find(w => 
            w?.name === PROMPT_WIDGET_NAME || 
            w?.name === "prompt" ||
            (w?.options?.multiline && w?.inputEl?.tagName === "TEXTAREA")
        );
        if (!promptWidget || !promptWidget.inputEl) return;

        const textarea = promptWidget.inputEl;
        textarea.style.resize = "none"; // 禁止手动拖拽textarea
        textarea.rows = PROMPT_DEFAULT_ROWS;
        
        // 只对新创建的节点增加高度（通过检查节点是否已有足够高度）
        // 计算需要增加的高度：(目标行数 - 当前行数) * 每行高度
        const currentRows = 3; // ComfyUI默认约3行
        const extraHeight = (PROMPT_DEFAULT_ROWS - currentRows) * 20;
        const minHeight = 400; // 设置后的最小高度阈值
        
        // 如果节点高度已经足够大，说明是从保存的工作流加载的，不需要再增加
        if (node.size && node.size[1] < minHeight) {
            requestAnimationFrame(() => {
                node.size[1] += extraHeight;
                node.setDirtyCanvas?.(true, true);
                node.graph?.setDirtyCanvas(true, true);
            });
        }
    }

    function registerExtension(app) {
        app.registerExtension({
            name: EXTENSION_NAME,
            nodeCreated(node) {
                // 处理文生图和图片编辑节点
                if (TEXT_TO_IMAGE_NODES.includes(node.comfyClass)) {
                    // 添加右上角链接按钮
                    addLinkButton(node);
                    
                    if (!node.__cyKeyMaskReady) {
                        node.__cyKeyMaskReady = true;
                        setTimeout(() => {
                            if (Array.isArray(node.widgets)) {
                                // Key1 遮罩
                                const key1Widget = node.widgets.find(w => w?.name === "Key1");
                                maskKeyWidget(key1Widget);
                                
                                // 设置提示词输入框
                                setupPromptWidget(node);
                            }
                        }, 300);
                    }
                    return;
                }

                if (node.comfyClass !== "CYGeminiRelay" || node.__cyBananaFoldReady) {
                    return;
                }
                node.__cyBananaFoldReady = true;
                if (!Array.isArray(node.widgets) || !node.widgets.length) {
                    return;
                }

                const widgetLookup = new Map();
                node.widgets.forEach((widget) => {
                    if (widget?.name) {
                        widgetLookup.set(widget.name, widget);
                    }
                });
                const getWidgets = (names) => names.map((name) => widgetLookup.get(name)).filter(Boolean);

                const extraKeys = getWidgets(KEY_WIDGET_NAMES);
                createFold(node, EXTRA_KEY_LABEL, extraKeys);
                maskKeyWidgets(extraKeys);

                createFold(node, ASPECT_LABEL, getWidgets(RATIO_WIDGET_NAMES));
                enhanceRefreshToggle(widgetLookup.get(REFRESH_WIDGET_NAME), getWidgets(REFRESH_WIDGET_NAMES));
                maskKeyWidget(widgetLookup.get(KEY1_WIDGET_NAME));
            },
        });
    }

    function tryRegister() {
        const comfyApp = window.comfyAPI?.app?.app;
        if (!comfyApp || typeof comfyApp.registerExtension !== "function") {
            return false;
        }
        registerExtension(comfyApp);
        return true;
    }

    if (!tryRegister()) {
        const timer = setInterval(() => {
            if (tryRegister()) {
                clearInterval(timer);
            }
        }, 500);
    }
})();
