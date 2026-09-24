(function (global) {
  "use strict";

  var taskStarts = {};
  var sessionStart = Date.now();

  function emit(type, payload) {
    var message = {
      source: "learnplay-sdk",
      type: type,
      payload: payload || {},
      ts: Date.now(),
    };
    try {
      if (global.parent && global.parent !== global) {
        global.parent.postMessage(message, "*");
      }
    } catch (e) {
      /* ignore */
    }
    try {
      global.dispatchEvent(new CustomEvent("learnplay:" + type, { detail: message }));
    } catch (e2) {
      /* ignore */
    }
  }

  var sessionClosed = false;

  var LearnPlay = {
    score: function (delta) {
      var value = Number(delta) || 0;
      emit("score", { delta: value });
      return value;
    },
    answer: function (opts) {
      opts = opts || {};
      var correct = !!opts.correct;
      emit("answer", {
        correct: correct,
        taskId: opts.taskId || null,
        points: opts.points || 0,
      });
      if (opts.points) {
        emit("score", { delta: correct ? Number(opts.points) : 0 });
      }
      return correct;
    },
    taskStart: function (taskId) {
      var id = taskId || "default";
      taskStarts[id] = Date.now();
      emit("task_time", { taskId: id, phase: "start" });
    },
    taskEnd: function (taskId) {
      var id = taskId || "default";
      var start = taskStarts[id] || sessionStart;
      var durationMs = Date.now() - start;
      emit("task_time", { taskId: id, phase: "end", durationMs: durationMs });
      delete taskStarts[id];
      return durationMs;
    },
    complete: function (extra) {
      if (sessionClosed) {
        return;
      }
      sessionClosed = true;
      emit("complete", Object.assign({ durationMs: Date.now() - sessionStart }, extra || {}));
    },
    levelComplete: function (level, totalLevels) {
      emit("level_complete", {
        level: Number(level) || 0,
        totalLevels: Number(totalLevels) || 0,
      });
    },
    /** Report how far a learner has gotten (solved stages / total). */
    progress: function (opts) {
      opts = opts || {};
      var level = Number(opts.level) || 0;
      var total = Number(opts.totalLevels || opts.total) || 0;
      var percent =
        opts.percent != null
          ? Number(opts.percent)
          : total > 0
            ? Math.round((level / total) * 100)
            : 0;
      emit("level_complete", {
        level: level,
        totalLevels: total,
        percent: percent,
        solved: !!opts.solved,
      });
    },
    /** Named checkpoint inside a game (concept, badge, stage id). */
    milestone: function (opts) {
      opts = opts || {};
      emit("milestone", {
        id: opts.id || "",
        label: opts.label || "",
        level: Number(opts.level) || 0,
        totalLevels: Number(opts.totalLevels || opts.total) || 0,
      });
    },
    /**
     * Report a solved stage. Pass {complete:true} when the learner finishes the game.
     * Does not mark the session solved unless complete is set (so a failed final
     * attempt can still show Level 4/5 instead of Solved).
     */
    stage: function (done, total, extra) {
      extra = extra || {};
      var level = Number(done) || 0;
      var tot = Number(total) || 0;
      this.progress({
        level: level,
        totalLevels: tot,
        percent: extra.percent,
      });
      if (extra.label || extra.id) {
        this.milestone({
          id: extra.id || String(extra.label || "stage"),
          label: extra.label || extra.id || "",
          level: level,
          totalLevels: tot,
        });
      }
      if (extra.points) {
        this.score(Number(extra.points) || 0);
      }
      if (extra.correct != null || extra.points) {
        this.answer({
          correct: extra.correct != null ? !!extra.correct : true,
          taskId: extra.id || extra.label || null,
        });
      }
      if (extra.complete) {
        this.complete({
          levelsCompleted: extra.levelsCompleted != null ? extra.levelsCompleted : level,
          totalLevels: tot,
          score: extra.score,
        });
      }
    },
    t: function (text) {
      return translatePhrase(text, currentLang);
    },
    setPrefs: function (opts) {
      applyPrefs(opts || {}, false);
    },
    classConfig: "",
  };

  global.LearnPlay = LearnPlay;

  var lastHeight = 0;
  var sizeTimer = 0;
  var currentTheme = "light";
  var currentLang = "en";
  var prefsReady = false;
  var toolbar = null;
  var skipHostEcho = false;
  var applyingPrefs = false;

  function contentHeight() {
    var doc = global.document;
    if (!doc) return 0;
    var el = doc.documentElement;
    var body = doc.body;
    var values = [
      el && el.scrollHeight,
      el && el.offsetHeight,
      body && body.scrollHeight,
      body && body.offsetHeight,
    ];
    var max = 0;
    for (var i = 0; i < values.length; i++) {
      var n = Number(values[i]) || 0;
      if (n > max) max = n;
    }
    return max;
  }

  LearnPlay.fit = function () {
    var height = contentHeight();
    if (!height || Math.abs(height - lastHeight) < 2) {
      return height;
    }
    lastHeight = height;
    emit("resize", { height: height });
    return height;
  };

  function scheduleFit() {
    if (typeof global.setTimeout !== "function") {
      LearnPlay.fit();
      return;
    }
    if (sizeTimer) {
      global.clearTimeout(sizeTimer);
    }
    sizeTimer = global.setTimeout(function () {
      LearnPlay.fit();
    }, 60);
  }

  function i18nPack() {
    return global.LEARNPLAY_I18N || { langs: [], codes: ["en"], chrome: {}, phrases: {} };
  }

  function langIndex(code) {
    var codes = i18nPack().codes || ["en"];
    var i = codes.indexOf(code);
    return i >= 0 ? i : 0;
  }

  function phraseRow(trimmed) {
    var phrases = i18nPack().phrases || {};
    if (phrases[trimmed]) return phrases[trimmed];
    var keys = Object.keys(phrases);
    for (var i = 0; i < keys.length; i++) {
      var row = phrases[keys[i]];
      if (row && row.indexOf(trimmed) >= 0) return row;
    }
    return null;
  }

  function translatePhrase(text, lang) {
    if (text == null) return text;
    var raw = String(text);
    var trimmed = raw.trim();
    if (!trimmed) return raw;
    var row = phraseRow(trimmed);
    if (!row) return raw;
    var next = row[langIndex(lang)] || row[0] || trimmed;
    return raw.replace(trimmed, next);
  }

  function chromeCopy(lang) {
    var all = i18nPack().chrome || {};
    return all[lang] || all.en || { appearance: "Appearance", light: "Light", dark: "Dark", language: "Language" };
  }

  var THEME_CSS = [
    'html[data-lp-theme="dark"]{color-scheme:dark;',
    "--bg:#0b1220;--bg-soft:#111827;--card:#151d2e;--panel:#151d2e;--text:#e8eef8;--ink:#e8eef8;--ink2:#b7c4d8;",
    "--muted:#9aa8bd;--border:#2a364a;--line:rgba(62,200,232,.22);--accent:#3ec8e8;--accent-soft:#11313a;",
    "--good:#3dba7a;--bad:#e05b74;--viz-bg:#0b1220;--viz-panel:#151d2e;--viz-text:#e8eef8;--viz-accent:#3ec8e8;",
    "--viz-muted:#9aa8bd}",
    'html[data-lp-theme="light"]{color-scheme:light;',
    "--bg:#f7f8fa;--bg-soft:#eef2f6;--card:#fff;--panel:#fff;--text:#1f2937;--ink:#172033;--ink2:#445468;",
    "--muted:#5b6b80;--border:#d1d5db;--line:rgba(23,32,51,.12);--accent:#0a7396;--accent-soft:#dceaf4;",
    "--good:#237a4b;--bad:#c4334a;--viz-bg:#f7f8fa;--viz-panel:#fff;--viz-text:#1f2937;--viz-accent:#0a7396;",
    "--viz-muted:#5b6b80}",
    "html[data-lp-theme] body,html[data-lp-theme] .app,html[data-lp-theme] main,html[data-lp-theme] .wrap{",
    "background:var(--bg);color:var(--text)}",
    "html[data-lp-theme] .card,html[data-lp-theme] .panel,html[data-lp-theme] .metric,html[data-lp-theme] .box,",
    "html[data-lp-theme] .col,html[data-lp-theme] .control,html[data-lp-theme] .embedcard,html[data-lp-theme] .mission,",
    "html[data-lp-theme] .level,html[data-lp-theme] .challenge,html[data-lp-theme] .math,html[data-lp-theme] .explain-box{",
    "background:var(--card);color:var(--text);border-color:var(--border)}",
    "html[data-lp-theme] button,html[data-lp-theme] input,html[data-lp-theme] select,html[data-lp-theme] textarea{",
    "background:var(--card);color:var(--text);border-color:var(--border)}",
    "html[data-lp-theme] button.primary,html[data-lp-theme] .primary{background:var(--accent);color:#041018;border-color:var(--accent)}",
    "html[data-lp-theme] .muted,html[data-lp-theme] .sub,html[data-lp-theme] .tiny,html[data-lp-theme] .label,",
    "html[data-lp-theme] .meta{color:var(--muted)}",
    "html[data-lp-theme] a{color:var(--accent)}",
    "html[data-lp-theme] .item,html[data-lp-theme] .opt,html[data-lp-theme] .drop,",
    "html[data-lp-theme] .slot,html[data-lp-theme] header,html[data-lp-theme] .topbar,",
    "html[data-lp-theme] .hud,html[data-lp-theme] .sidebar,html[data-lp-theme] .board{",
    "background:var(--card);color:var(--text);border-color:var(--border)}",
    "#lp-toolbar{position:sticky;top:0;z-index:2147483000;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;",
    "padding:8px 12px;border-bottom:1px solid var(--border, #d1d5db);background:var(--card, #fff);color:var(--text, #172033);",
    "font:600 13px/1.3 system-ui,-apple-system,Segoe UI,sans-serif}",
    "#lp-toolbar .lp-group{display:inline-flex;align-items:center;gap:6px}",
    "#lp-toolbar button{min-height:28px;padding:4px 10px;border-radius:999px;cursor:pointer;font:inherit}",
    "#lp-toolbar button.lp-on{background:var(--accent);color:#041018;border-color:var(--accent)}",
    "#lp-toolbar select{min-height:28px;padding:4px 8px;border-radius:8px;font:inherit}",
    "#lp-toolbar label{color:var(--muted);font-weight:600}",
  ].join("");

  function ensureThemeStyle() {
    var doc = global.document;
    if (!doc || typeof doc.getElementById !== "function" || typeof doc.createElement !== "function") return;
    if (doc.getElementById("lp-theme-css")) return;
    var style = doc.createElement("style");
    style.id = "lp-theme-css";
    style.textContent = THEME_CSS;
    (doc.head || doc.documentElement).appendChild(style);
  }

  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, SVG: 1, CODE: 1, PRE: 1, TEXTAREA: 1, NOSCRIPT: 1, MATH: 1 };

  function translateTextNode(node, lang) {
    var raw = node.nodeValue;
    if (raw == null) return;
    if (node.__lpSrc == null) node.__lpSrc = raw;
    var src = node.__lpSrc;
    var trimmed = src.trim();
    if (!trimmed) return;
    var next = translatePhrase(src, lang);
    if (next !== node.nodeValue) node.nodeValue = next;
  }

  function translateElement(el, lang) {
    if (!el || el.nodeType !== 1) return;
    if (el.id === "lp-toolbar" || (el.getAttribute && el.getAttribute("data-lp-skip") != null)) return;
    var attrs = ["title", "placeholder", "aria-label", "aria-placeholder"];
    for (var i = 0; i < attrs.length; i++) {
      var name = attrs[i];
      if (!el.hasAttribute || !el.hasAttribute(name)) continue;
      var key = "__lpAttr_" + name;
      if (el[key] == null) el[key] = el.getAttribute(name);
      el.setAttribute(name, translatePhrase(el[key], lang));
    }
    if (el.tagName === "INPUT" && (el.type === "button" || el.type === "submit")) {
      if (el.__lpValue == null) el.__lpValue = el.value;
      el.value = translatePhrase(el.__lpValue, lang);
    }
  }

  function translateTree(root, lang) {
    if (!root) return;
    var node = root;
    var stack = [node];
    while (stack.length) {
      node = stack.pop();
      if (!node) continue;
      if (node.nodeType === 1) {
        if (SKIP_TAGS[node.tagName]) continue;
        if (node.id === "lp-toolbar") continue;
        translateElement(node, lang);
        var child = node.lastChild;
        while (child) {
          stack.push(child);
          child = child.previousSibling;
        }
      } else if (node.nodeType === 3) {
        translateTextNode(node, lang);
      }
    }
  }

  function paintToolbar() {
    if (!toolbar || !global.document) return;
    var copy = chromeCopy(currentLang);
    var lightBtn = toolbar.querySelector('[data-lp-theme="light"]');
    var darkBtn = toolbar.querySelector('[data-lp-theme="dark"]');
    var select = toolbar.querySelector("select");
    var themeLabel = toolbar.querySelector("[data-lp-theme-label]");
    var langLabel = toolbar.querySelector("[data-lp-lang-label]");
    if (themeLabel) themeLabel.textContent = copy.appearance;
    if (langLabel) langLabel.textContent = copy.language;
    if (lightBtn) {
      lightBtn.textContent = copy.light;
      lightBtn.className = currentTheme === "light" ? "lp-on" : "";
    }
    if (darkBtn) {
      darkBtn.textContent = copy.dark;
      darkBtn.className = currentTheme === "dark" ? "lp-on" : "";
    }
    if (select) select.value = currentLang;
  }

  function hostedInFrame() {
    try {
      return global.parent && global.parent !== global;
    } catch (e) {
      return true;
    }
  }

  function ensureToolbar() {
    var doc = global.document;
    if (!doc || !doc.body || typeof doc.createElement !== "function") return;
    // The play page already sets theme and language. A toolbar in the frame
    // pushes the game down and the host then grows the frame to match.
    if (hostedInFrame()) return;
    if (toolbar && toolbar.parentNode) {
      paintToolbar();
      return;
    }
    toolbar = doc.createElement("div");
    toolbar.id = "lp-toolbar";
    toolbar.setAttribute("data-lp-skip", "");
    var langs = i18nPack().langs || [];
    var options = langs
      .map(function (item) {
        return '<option value="' + item.code + '">' + item.label + "</option>";
      })
      .join("");
    toolbar.innerHTML =
      '<div class="lp-group"><label data-lp-theme-label></label>' +
      '<button type="button" data-lp-theme="light"></button>' +
      '<button type="button" data-lp-theme="dark"></button></div>' +
      '<div class="lp-group"><label data-lp-lang-label></label>' +
      "<select>" +
      options +
      "</select></div>";
    doc.body.insertBefore(toolbar, doc.body.firstChild);
    toolbar.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-lp-theme]");
      if (!btn) return;
      applyPrefs({ theme: btn.getAttribute("data-lp-theme") }, true);
    });
    toolbar.querySelector("select").addEventListener("change", function (ev) {
      applyPrefs({ lang: ev.target.value }, true);
    });
    paintToolbar();
  }

  function applyPrefs(opts, fromToolbar) {
    opts = opts || {};
    var theme = opts.theme === "dark" || opts.theme === "light" ? opts.theme : currentTheme;
    var lang = typeof opts.lang === "string" && opts.lang ? opts.lang : currentLang;
    var codes = i18nPack().codes || ["en"];
    if (codes.indexOf(lang) < 0) lang = "en";
    currentTheme = theme;
    currentLang = lang;
    prefsReady = true;
    applyingPrefs = true;
    var doc = global.document;
    if (doc && doc.documentElement) {
      var root = doc.documentElement;
      if (typeof root.setAttribute === "function") {
        root.setAttribute("data-lp-theme", theme);
        root.setAttribute("data-lp-lang", lang);
      }
      root.lang = lang;
      if (root.style) root.style.colorScheme = theme;
    }
    ensureThemeStyle();
    ensureToolbar();
    paintToolbar();
    if (doc && doc.body) translateTree(doc.body, lang);
    applyingPrefs = false;
    scheduleFit();
    if (fromToolbar && !skipHostEcho) {
      emit("prefs", { theme: currentTheme, lang: currentLang });
    }
  }

  function readQueryPrefs() {
    try {
      var params = new URLSearchParams(global.location && global.location.search);
      var theme = params.get("theme");
      var lang = params.get("lang");
      var opts = {};
      if (theme === "dark" || theme === "light") opts.theme = theme;
      if (lang) opts.lang = lang;
      return opts;
    } catch (e) {
      return {};
    }
  }

  function readClassConfig() {
    try {
      var params = new URLSearchParams(global.location && global.location.search);
      return params.get("lp_config") || "";
    } catch (e) {
      return "";
    }
  }

  function applyClassConfig(text) {
    LearnPlay.classConfig = String(text || "");
    try {
      global.dispatchEvent(new CustomEvent("learnplay-config", { detail: LearnPlay.classConfig }));
    } catch (e) {
      /* ignore */
    }
  }

  function bootPrefs() {
    applyPrefs(readQueryPrefs(), false);
    applyClassConfig(readClassConfig());
    emit("ready", { theme: currentTheme, lang: currentLang });
    try {
      global.addEventListener("message", function (ev) {
        var data = ev.data || {};
        if (data.source !== "learnplay-host") return;
        if (data.type === "config") {
          applyClassConfig((data.payload && data.payload.config) || "");
          return;
        }
        if (data.type !== "prefs") return;
        skipHostEcho = true;
        applyPrefs(data.payload || {}, false);
        skipHostEcho = false;
      });
    } catch (e5) {
      /* ignore */
    }
    try {
      if (global.document && global.document.body && typeof global.MutationObserver === "function") {
        var translateQueued = false;
        var obs = new global.MutationObserver(function () {
          if (applyingPrefs || translateQueued) return;
          translateQueued = true;
          var later = typeof global.setTimeout === "function" ? global.setTimeout : function (fn) { fn(); };
          later(function () {
            translateQueued = false;
            if (applyingPrefs) return;
            applyingPrefs = true;
            translateTree(global.document.body, currentLang);
            applyingPrefs = false;
            scheduleFit();
          }, 0);
        });
        obs.observe(global.document.body, { childList: true, subtree: true, characterData: true });
      }
    } catch (e6) {
      /* ignore */
    }
  }

  function watchSize() {
    LearnPlay.fit();
    try {
      if (typeof global.ResizeObserver === "function" && global.document) {
        var ro = new global.ResizeObserver(scheduleFit);
        if (global.document.documentElement) ro.observe(global.document.documentElement);
        if (global.document.body) ro.observe(global.document.body);
      }
    } catch (e3) {
      /* ignore */
    }
    try {
      global.addEventListener("load", scheduleFit);
      global.addEventListener("resize", scheduleFit);
    } catch (e4) {
      /* ignore */
    }
  }

  function startUi() {
    bootPrefs();
    watchSize();
  }

  if (typeof global.document !== "undefined") {
    if (global.document.readyState === "loading") {
      global.document.addEventListener("DOMContentLoaded", startUi);
    } else {
      startUi();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
