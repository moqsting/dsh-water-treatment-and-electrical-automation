/**
 * dsh-open-workbench —— 浏览器侧插件（client bundle）。
 * 在侧边栏底部（sidebar.footer.action 槽位）注册一个“工作台”按钮：
 * 点击后探测本机运行中的整合包工作台（127.0.0.1:8618~8628），找到则在新标签页打开，
 * 未找到则提示先启动工作台。
 */
window.__ModuleLoader__.load({
  id: "dsh-open-workbench",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    let react = require("react");
    const e = react.createElement;

    /** 探测运行中的工作台端口。 */
    async function findWorkbench() {
      for (let port = 8618; port <= 8628; port++) {
        try {
          const ctrl = new AbortController();
          const timer = setTimeout(() => ctrl.abort(), 800);
          const r = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: ctrl.signal });
          clearTimeout(timer);
          if (r.ok) {
            const j = await r.json().catch(() => null);
            if (j && j.name === "integration-pack-workbench") return port;
          }
        } catch { /* 该端口未运行，继续 */ }
      }
      return null;
    }

    function OpenButton(props) {
      const wide = props && props.wide;
      return e(
        "button",
        {
          title: "打开工作台",
          "aria-label": "打开工作台",
          onClick: async () => {
            try {
              const port = await findWorkbench();
              if (port) {
                window.open(`http://127.0.0.1:${port}`, "_blank");
              } else {
                window.alert("工作台未运行。请先双击桌面快捷方式“水处理·电气自动化工作台”，或运行 ui\\start.pyw。");
              }
            } catch (err) {
              window.alert("打开工作台失败：" + (err && err.message ? err.message : String(err)));
            }
          },
          style: {
            display: "flex",
            alignItems: "center",
            gap: 6,
            border: "none",
            background: "transparent",
            color: "inherit",
            opacity: 0.72,
            cursor: "pointer",
            padding: "6px 10px",
            borderRadius: 8,
            fontSize: 13,
            lineHeight: 1,
            width: wide ? "100%" : "auto",
            justifyContent: wide ? "flex-start" : "center",
          },
          onMouseEnter: (ev) => {
            ev.currentTarget.style.opacity = "1";
            ev.currentTarget.style.background = "rgba(127, 127, 127, 0.14)";
          },
          onMouseLeave: (ev) => {
            ev.currentTarget.style.opacity = "0.72";
            ev.currentTarget.style.background = "transparent";
          },
        },
        e(
          "svg",
          {
            width: 16,
            height: 16,
            viewBox: "0 0 24 24",
            fill: "none",
            stroke: "currentColor",
            strokeWidth: 2,
            strokeLinecap: "round",
            strokeLinejoin: "round",
            "aria-hidden": true,
          },
          e("rect", { key: "r", x: 3, y: 4, width: 18, height: 16, rx: 2 }),
          e("line", { key: "l1", x1: 3, y1: 9, x2: 21, y2: 9 }),
          e("circle", { key: "c", cx: 8, cy: 14, r: 1.5 }),
          e("circle", { key: "c2", cx: 13, cy: 14, r: 1.5 }),
        ),
        wide ? e("span", { key: "t" }, "工作台") : null,
      );
    }

    const inject = ["slots"];
    function apply(ctx) {
      ctx.slots.inject("sidebar.footer.action", () =>
        ctx.slots.register({ name: "sidebar.footer.action", id: "open-workbench-button" }, OpenButton),
      );
    }

    exports.inject = inject;
    exports.apply = apply;
    return module.exports;
  },
});
