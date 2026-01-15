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

    // 创建令牌配置
    const TOKEN_API_PATH = "/api/open/token";
    const SUPPORTED_RELAY_URLS = ["https://api.xheai.cc", "http://localhost:3000"];

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

        // 自动聚焦确定按钮，按回车可关闭
        okBtn.focus();
    }

    // 创建令牌
    async function createToken(node, group = null) {
        const relayWidget = node.widgets.find(w => w.name === "中转网址");
        const masterKeyWidget = node.widgets.find(w => w.name === "总Key");
        const modelWidget = node.widgets.find(w => w.name === "模型");
        const key1Widget = node.widgets.find(w => w.name === "Key1");

        if (!masterKeyWidget?.value?.trim()) {
            showMessage("请先填写总Key", false);
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
                // 需要选择分组
                showGroupSelector(result.data.groups || [], async (selectedGroup) => {
                    await createToken(node, selectedGroup);
                });
            } else if (result.success && result.data?.key) {
                // 成功获取令牌
                if (key1Widget) {
                    key1Widget.value = result.data.key;
                    if (key1Widget.inputEl) {
                        key1Widget.inputEl.value = result.data.key;
                    }
                }
                showMessage("令牌创建成功！已自动填入Key1", true);
            } else {
                showMessage("创建失败: " + (result.message || "未知错误"), false);
            }
        } catch (e) {
            showMessage("请求失败: " + e.message, false);
        }
    }

    // 添加创建令牌按钮
    function addCreateTokenButton(node) {
        if (node.__cyTokenButtonAdded) return;
        node.__cyTokenButtonAdded = true;

        // 查找中转网址和总Key的位置
        const relayWidget = node.widgets.find(w => w.name === "中转网址");
        const masterKeyWidget = node.widgets.find(w => w.name === "总Key");

        if (!relayWidget || !masterKeyWidget) return;

        // 创建按钮 widget
        const tokenButton = node.addWidget("button", "创建令牌", "创建令牌", async () => {
            await createToken(node);
        });

        tokenButton.options = tokenButton.options || {};
        tokenButton.options.serialize = false;

        // 移动按钮到总Key后面
        const btnIndex = node.widgets.indexOf(tokenButton);
        const masterKeyIndex = node.widgets.indexOf(masterKeyWidget);
        if (btnIndex > -1 && masterKeyIndex > -1 && btnIndex !== masterKeyIndex + 1) {
            node.widgets.splice(btnIndex, 1);
            node.widgets.splice(masterKeyIndex + 1, 0, tokenButton);
        }

        // 根据中转网址显示/隐藏按钮和总Key
        const updateVisibility = () => {
            // 下拉框可能用 value 或 inputEl.value
            const currentValue = relayWidget.value || relayWidget.inputEl?.value || "";
            const isSupported = SUPPORTED_RELAY_URLS.some(url => currentValue.includes(url) || url.includes(currentValue));
            console.log("[CY] 中转网址:", currentValue, "支持创建令牌:", isSupported);
            masterKeyWidget.hidden = !isSupported;
            tokenButton.hidden = !isSupported;
            node.setDirtyCanvas?.(true, true);
            node.graph?.setDirtyCanvas(true, true);
        };

        // 初始化可见性
        setTimeout(updateVisibility, 100);
        setTimeout(updateVisibility, 500);

        // 监听中转网址变化 - combo widget 使用 callback
        const originalCallback = relayWidget.callback;
        relayWidget.callback = function (value) {
            if (originalCallback) originalCallback.call(this, value);
            setTimeout(updateVisibility, 50);
        };

        // 也监听 onChange（某些版本的 ComfyUI）
        if (!relayWidget._cyOnChangeSet) {
            relayWidget._cyOnChangeSet = true;
            const originalOnChange = relayWidget.onChange;
            relayWidget.onChange = function (value) {
                if (originalOnChange) originalOnChange.call(this, value);
                setTimeout(updateVisibility, 50);
            };
        }

        // 遮罩总Key输入框
        setTimeout(() => {
            if (masterKeyWidget.inputEl) {
                masterKeyWidget.inputEl.type = "password";
                masterKeyWidget.inputEl.autocomplete = "off";
            }
        }, 300);
    }

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

                    // 为 CYTextToImage 和 CYImageEdit 添加创建令牌按钮
                    if (node.comfyClass === "CYTextToImage" || node.comfyClass === "CYImageEdit") {
                        setTimeout(() => addCreateTokenButton(node), 200);
                    }
                    
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
