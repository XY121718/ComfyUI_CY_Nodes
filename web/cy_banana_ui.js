(function () {
    const EXTENSION_NAME = "CY.BananaPro.Fold";
    const KEY_WIDGET_NAMES = ["Key2", "Key3", "Key4", "Key5"];
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

    function registerExtension(app) {
        app.registerExtension({
            name: EXTENSION_NAME,
            nodeCreated(node) {
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
