/* Kori lab frame runtime.
   Receives the ledger (init) and the fragment so far (html), fills {{name|format}} from the ledger,
   morphs the document without restarting what is already on screen, runs the fragment's scripts once
   when it is done, and gives the fragment K: the ledger, formatting, a small kit and helpers.
   Contract: docs/LAB.md sections 2 to 4. No network, no eval. */
(function () {
  "use strict";

  var S = { lang: "en", data: { facts: {}, tables: {}, products: [], sources: [] }, width: 390, html: null, done: false, ran: false, inited: false };
  var root = document.getElementById("k-root");
  var fragStyle = document.getElementById("k-frag-style");
  var REDUCED = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SVGNS = "http://www.w3.org/2000/svg";
  var EASE = function (t) { return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t); }; // ease-out-expo

  function post(m) { try { parent.postMessage(m, "*"); } catch (e) {} }
  function fail(e) { post({ kori: "error", message: String((e && e.message) || e).slice(0, 300) }); }
  addEventListener("error", function (e) { fail(e.error || e.message); });
  addEventListener("unhandledrejection", function (e) { fail(e.reason); });

  /* ---------------- formatting ---------------- */
  var NB = " ", MINUS = "−";
  var L = {
    en: { mon: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], month: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], wd: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], wdl: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], today: "Today", again: "Replay" },
    fi: { mon: ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"], month: ["tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu", "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu"], wd: ["ma", "ti", "ke", "to", "pe", "la", "su"], wdl: ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"], today: "Tänään", again: "Uudestaan" },
  };
  function loc() { return L[S.lang] || L.en; }
  function fi() { return S.lang === "fi"; }
  function grp(i) { return i.replace(/\B(?=(\d{3})+(?!\d))/g, fi() ? NB : ","); }
  function fixed(a, d) { var p = Math.pow(10, d); return (Math.round((a + 1e-9) * p) / p).toFixed(d); }
  function parts(v, d) { // -> [sign, integer, fraction]
    v = +v; if (!isFinite(v)) return ["", "–", ""];
    var s = fixed(Math.abs(v), d).split(".");
    var neg = v < 0 && +(s[0] + "." + (s[1] || 0)) !== 0;
    return [neg ? MINUS : "", grp(s[0]), s[1] ? (fi() ? "," : ".") + s[1] : ""];
  }
  function wdIndex(v) {
    if (typeof v === "number") return ((v % 7) + 7) % 7;
    var s = String(v).slice(0, 3).toLowerCase(), i = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].indexOf(s);
    if (i < 0) i = L.fi.wd.indexOf(String(v).slice(0, 2).toLowerCase());
    return i < 0 && /^\d+$/.test(v) ? +v % 7 : i;
  }
  function ymd(v) {
    var m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(String(v));
    return m ? [+m[1], +m[2], m[3] ? +m[3] : null] : null;
  }
  var fmt = {
    eur: function (v) { var p = parts(v, 2); return fi() ? p[0] + p[1] + p[2] + NB + "€" : p[0] + "€" + p[1] + p[2]; },
    eur0: function (v) { // whole euros round from the cents, halves up
      v = +v; var c = Math.round(Math.abs(v) * 100 + 1e-7), e = Math.floor((c + 50) / 100), p = [v < 0 && e ? MINUS : "", grp(String(e))];
      return fi() ? p[0] + p[1] + NB + "€" : p[0] + "€" + p[1];
    },
    pct: function (v) { var a = Math.abs(+v), p = parts(v, a < 10 && a % 1 ? 1 : 0); return p[0] + p[1] + p[2] + (fi() ? NB + "%" : "%"); },
    int: function (v) { var p = parts(v, 0); return p[0] + p[1]; },
    num: function (v) { var p = parts(v, 2); return p[0] + p[1] + p[2].replace(/0+$/, "").replace(/[.,]$/, ""); },
    signed: function (v) { return (+v > 0 ? "+" : "") + fmt.eur0(v); },
    date: function (v) { var d = ymd(v); if (!d) return String(v); if (d[2] == null) return fmt.month(v); return fi() ? d[2] + "." + d[1] + "." : d[2] + " " + loc().mon[d[1] - 1]; },
    datel: function (v) { var d = ymd(v); if (!d) return String(v); return fi() ? d[2] + ". " + loc().month[d[1] - 1] + "ta " + d[0] : d[2] + " " + loc().month[d[1] - 1] + " " + d[0]; },
    month: function (v) { var d = ymd(v); return d ? loc().mon[d[1] - 1] + " " + d[0] : String(v); },
    mon: function (v) { var d = ymd(v); return d ? loc().mon[d[1] - 1] : String(v); },
    monthl: function (v) { var d = ymd(v); return d ? loc().month[d[1] - 1] : String(v); },
    wd: function (v) { var i = wdIndex(v); return i < 0 ? String(v) : loc().wd[i]; },
    wdl: function (v) { var i = wdIndex(v); return i < 0 ? String(v) : loc().wdl[i]; },
    hour: function (v) { var h = +v; return isFinite(h) ? (h < 10 ? "0" : "") + h + (fi() ? "" : ":00") : String(v); },
    raw: function (v) { return v == null ? "" : String(v); },
  };
  fmt.text = fmt.raw;
  var UNIT_FMT = { eur: "eur", eur_per_day: "eur", eur_per_month: "eur", pct: "pct", count: "int", days: "int", months: "int", date: "date", ratio: "num", text: "raw" };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function apply(v, f) { return (fmt[f] || (typeof v === "number" ? fmt.num : fmt.raw))(v); }
  // html for a figure: the cents (and the trailing sign in Finnish) are a quieter span the kit can dim
  function figHtml(v, f) {
    var s = esc(apply(v, f));
    if (f === "eur") { var m = /^(.*\d)([.,]\d\d)(.*)$/.exec(s); if (m) return m[1] + '<span class="k-c">' + m[2] + m[3] + "</span>"; }
    return s;
  }

  /* ---------------- ledger ---------------- */
  function fact(name) { var f = S.data.facts && S.data.facts[name]; return f == null ? cell(name) : (typeof f === "object" ? f.v : f); }
  // "table.3.column", "table.last.column": one cell of a table, when a view asks for it as a single figure
  function cell(name) {
    var m = /^([\w-]+)\.(\d+|first|last)\.([\w-]+)$/.exec(String(name)); if (!m) return undefined;
    var t = S.data.tables && S.data.tables[m[1]], rows = t && t.rows; if (!rows || !rows.length) return undefined;
    var r = rows[m[2] === "first" ? 0 : m[2] === "last" ? rows.length - 1 : +m[2]], v = r && r[m[3]];
    return v == null ? undefined : v;
  }
  function factUnit(name) { var f = S.data.facts && S.data.facts[name]; return f && f.unit; }
  function table(name) { var t = S.data.tables && S.data.tables[name]; return t ? t.rows : []; }
  function product(id) { var ps = S.data.products || []; for (var i = 0; i < ps.length; i++) if (ps[i].id === id) return ps[i]; return typeof id === "number" ? ps[id] : undefined; }
  function normalise(d) {
    d = d || {}; d.facts = d.facts || {}; d.tables = d.tables || {}; d.products = d.products || []; d.sources = d.sources || [];
    Object.keys(d.tables).forEach(function (k) {
      var t = d.tables[k]; if (Array.isArray(t)) t = d.tables[k] = { rows: t, columns: t[0] ? Object.keys(t[0]) : [] };
      if (t.rows && t.rows.length && Array.isArray(t.rows[0]) && t.columns) t.rows = t.rows.map(function (r) { var o = {}; t.columns.forEach(function (c, i) { o[c] = r[i]; }); return o; });
      t.rows = t.rows || [];
    });
    return d;
  }
  // "a.b" on a row; a string that is a product id opens that product
  function dig(row, path) {
    var v = row, segs = path.split(".");
    for (var i = 0; i < segs.length; i++) {
      if (typeof v === "string") v = product(v);
      if (v == null) return undefined;
      v = v[segs[i]];
    }
    return v;
  }
  // "{col|fmt}" in a row template
  function fillRow(tpl, row, i) {
    return tpl.replace(/\{([\w.$]+)(?:\|(\w+))?\}/g, function (_, path, f) {
      var v = path === "$i" ? i : dig(row, path);
      if (v == null) return "";
      return f === "eur" ? figHtml(v, f) : esc(apply(v, f));
    });
  }

  document.addEventListener("error", function (e) {
    var t = e.target; if (!t || t.nodeName !== "IMG") return;
    var src = t.getAttribute("src") || "";
    if (src && !t._kRetry && /^\/api\//.test(src)) { t._kRetry = 1; setTimeout(function () { t.src = src + (src.indexOf("?") < 0 ? "?" : "&") + "again=1"; }, 500); return; }
    t._kKeep = { src: 1 }; t.removeAttribute("src");
  }, true);

  /* ---------------- placeholders ---------------- */
  var PH = /\{\{\s*([\w.-]+)\s*(?:\|\s*(\w+)\s*)?(\|[^{}]*)?\}\}/g; // anything after the format is ignored, never shown
  function phText(name, f) {
    var v = fact(name); if (v === undefined) return "–";
    return apply(v, f || UNIT_FMT[factUnit(name)] || (typeof v === "number" ? "num" : "raw"));
  }
  function fillTree(node) {
    var kids = Array.prototype.slice.call(node.childNodes);
    for (var i = 0; i < kids.length; i++) {
      var n = kids[i];
      if (n.nodeType === 3) {
        if (n.data.indexOf("{{") < 0) continue;
        var par = n.parentNode, plain = par.namespaceURI === SVGNS || /^(SCRIPT|STYLE|TITLE|TEXTAREA|OPTION)$/.test(par.nodeName);
        if (plain) { n.data = n.data.replace(PH, function (_, a, b, c) { return c && /hidden/.test(c) ? "" : phText(a, b); }); continue; }
        var frag = document.createDocumentFragment(), last = 0, m; PH.lastIndex = 0;
        while ((m = PH.exec(n.data))) {
          if (m.index > last) frag.appendChild(document.createTextNode(n.data.slice(last, m.index)));
          var sp = document.createElement("span"), v = fact(m[1]), f = m[2] || UNIT_FMT[factUnit(m[1])] || (typeof v === "number" ? "num" : "raw");
          sp.className = "k-n"; sp.setAttribute("data-trace", m[1]);
          if (v === undefined) sp.textContent = "–";
          else { sp.innerHTML = figHtml(v, f); if (typeof v === "number") { sp.setAttribute("data-v", v); sp.setAttribute("data-f", f); } }
          last = m.index + m[0].length;
          if (m[3] && /hidden/.test(m[3])) continue;
          frag.appendChild(sp);
          // a Finnish date ends in a full stop: the sentence's own is not doubled
          if (/\.$/.test(sp.textContent)) {
            if (n.data.charAt(last) === "." && n.data.charAt(last + 1) !== ".") last++;
            else if (last === n.data.length && /^(B|STRONG|EM|I|SPAN)$/.test(par.nodeName) && n === par.lastChild) {
              var nx = par.nextSibling; if (nx && nx.nodeType === 3 && /^\.(?!\.)/.test(nx.data)) nx.data = nx.data.slice(1);
            }
          }
        }
        if (last < n.data.length) frag.appendChild(document.createTextNode(n.data.slice(last)));
        par.replaceChild(frag, n);
      } else if (n.nodeType === 1) {
        for (var a = 0; a < n.attributes.length; a++) { var at = n.attributes[a]; if (at.value.indexOf("{{") >= 0) at.value = at.value.replace(PH, function (_, x, y) { return phText(x, y || "raw"); }); }
        if (n.nodeName === "TEMPLATE") fillTree(n.content); else fillTree(n);
      }
    }
  }

  /* ---------------- the fragment so far -> DOM ---------------- */
  function prepare(html, done) {
    var s = html, css = "", scripts = [];
    // scripts: complete ones are kept for the end, an unfinished one is held back
    s = s.replace(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi, function (_, attrs, code) { if (!/type\s*=\s*["']?(application\/json|text\/template)/i.test(attrs)) scripts.push(code); return ""; });
    var open = s.search(/<script\b/i); if (open >= 0) s = s.slice(0, open);
    s = s.replace(/<style\b[^>]*>([\s\S]*?)<\/style\s*>/gi, function (_, c) { css += c + "\n"; return ""; });
    open = s.search(/<style\b/i);
    if (open >= 0) { var part = s.slice(open).replace(/^<style\b[^>]*>?/i, ""); var end = part.lastIndexOf("}"); if (end >= 0) css += part.slice(0, end + 1); s = s.slice(0, open); }
    if (!done) {
      var lt = s.lastIndexOf("<"); if (lt > s.lastIndexOf(">")) s = s.slice(0, lt);
      var t = s.lastIndexOf("<template"); if (t >= 0 && s.indexOf("</template>", t) < 0) s = s.slice(0, t);
      var o = s.lastIndexOf("{{"); if (o >= 0 && s.indexOf("}}", o) < 0) s = s.slice(0, o);
      s = s.replace(/\{$/, "").replace(/&[#\w]*$/, "");
    }
    return { html: s, css: css, scripts: scripts };
  }
  function own(n) { return n.nodeType === 1 && n.hasAttribute("data-k-own"); }
  function adopt(n) {
    var c = document.importNode(n, true);
    if (c.nodeType === 1 && S.html !== null && !REDUCED) c.setAttribute("data-k-new", "");
    return c;
  }
  function syncAttrs(o, n) {
    var i, a;
    for (i = o.attributes.length - 1; i >= 0; i--) { a = o.attributes[i]; if (a.name.indexOf("data-k-") !== 0 && !n.hasAttribute(a.name) && !(o._kKeep && o._kKeep[a.name])) o.removeAttribute(a.name); }
    for (i = 0; i < n.attributes.length; i++) { a = n.attributes[i]; if (o.getAttribute(a.name) !== a.value && !(o._kKeep && o._kKeep[a.name])) o.setAttribute(a.name, a.value); }
  }
  function morph(oldP, newP) {
    var o = oldP.firstChild, n = newP.firstChild, nx;
    while (n) {
      nx = n.nextSibling;
      while (o && own(o)) o = o.nextSibling;
      if (!o) oldP.appendChild(adopt(n));
      else if (o.nodeType === n.nodeType && o.nodeName === n.nodeName) {
        if (o.nodeType === 1) {
          syncAttrs(o, n);
          if (o.nodeName === "TEMPLATE") { if (o.innerHTML !== n.innerHTML) o.innerHTML = n.innerHTML; }
          else morph(o, n);
        } else if (o.data !== n.data) o.data = n.data;
        o = o.nextSibling;
      } else { var r = adopt(n); oldP.replaceChild(r, o); o = r.nextSibling; }
      n = nx;
    }
    while (o) { nx = o.nextSibling; if (!own(o)) oldP.removeChild(o); o = nx; }
  }
  var KIT = "k-chart,k-heat,k-bars,k-each,k-product,k-slides,k-choice";
  function syncKit() {
    var els = root.querySelectorAll(KIT);
    for (var i = 0; i < els.length; i++) if (els[i]._sync) { try { els[i]._sync(); } catch (e) { fail(e); } }
    var rs = root.querySelectorAll('input[type="range"]');
    for (i = 0; i < rs.length; i++) rangeFill(rs[i]);
  }
  function render(html, done) {
    if (S.ran) { if (html === S.html) return; S.ran = false; root.textContent = ""; S.html = null; }
    var p = prepare(html, done);
    if (fragStyle.textContent !== p.css) fragStyle.textContent = p.css;
    var t = document.createElement("template"); t.innerHTML = p.html;
    fillTree(t.content);
    if (S.html === null) { S.html = ""; }
    morph(root, t.content);
    S.html = html;
    syncKit();
    if (done) {
      S.ran = true; S.done = true;
      for (var i = 0; i < p.scripts.length; i++) runScript(p.scripts[i]);
      syncKit();
      var sl = root.querySelectorAll("k-slides"); for (i = 0; i < sl.length; i++) sl[i].play && sl[i].play();
      document.documentElement.setAttribute("data-k-done", "");
    }
    reportHeight();
  }
  function runScript(code) {
    var s = document.createElement("script");
    s.textContent = "try{\n" + code + "\n}catch(e){K._fail(e)}";
    document.head.appendChild(s); s.remove();
  }
  var lastH = -1, hQueued = false;
  function reportHeight() {
    if (hQueued) return; hQueued = true;
    requestAnimationFrame(function () {
      hQueued = false;
      var h = Math.ceil(root.getBoundingClientRect().height);
      if (h !== lastH) { lastH = h; post({ kori: "height", h: h }); }
    });
  }
  if (window.ResizeObserver) new ResizeObserver(reportHeight).observe(root);
  addEventListener("load", reportHeight, true);

  function markFlagged(list) {
    if (!list || !list.length) return;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), nodes = [], n;
    while ((n = w.nextNode())) nodes.push(n);
    nodes.forEach(function (t) {
      list.forEach(function (lit) {
        if (!t.parentNode || !lit) return;
        var i = t.data.indexOf(lit); if (i < 0 || t.parentNode.closest("mark.k-flag,script,style")) return;
        var mid = t.splitText(i); mid.splitText(lit.length);
        var m = document.createElement("mark"); m.className = "k-flag"; mid.parentNode.replaceChild(m, mid); m.appendChild(mid);
      });
    });
  }

  addEventListener("message", function (e) {
    var m = e.data; if (!m || typeof m !== "object" || !m.kori || e.source !== parent) return;
    try {
      if (m.kori === "init") {
        S.lang = m.lang === "fi" ? "fi" : "en"; S.data = normalise(m.data); S.width = m.width || 390; S.inited = true;
        K.data = S.data; K.lang = S.lang; document.documentElement.lang = S.lang;
        if (m.gutter != null) document.documentElement.style.setProperty("--k-gutter", m.gutter + "px");
        if (S.html) { var h = S.html, d = S.done; S.ran = false; S.html = null; root.textContent = ""; render(h, d); }
      } else if (m.kori === "html") render(String(m.html || ""), !!m.done);
      else if (m.kori === "check") markFlagged(m.flagged);
    } catch (err) { fail(err); }
  });

  /* taps: ask, open, trace */
  root.addEventListener("click", function (e) {
    var t = e.target, a;
    if (!(t instanceof Element)) return;
    if ((a = t.closest("[data-ask]"))) { post({ kori: "ask", text: a.getAttribute("data-ask") || a.textContent.trim() }); return; }
    if ((a = t.closest("[data-open]"))) { post({ kori: "open", url: a.getAttribute("data-open") }); return; }
    if (t.closest("input,button,select,label,k-choice,k-slides,svg")) return;
    if ((a = t.closest("[data-trace]"))) post({ kori: "trace", name: a.getAttribute("data-trace") });
  });
  function rangeFill(el) {
    var lo = +el.min || 0, hi = el.max === "" ? 100 : +el.max, v = +el.value;
    el.style.setProperty("--k-fill", (hi > lo ? ((v - lo) / (hi - lo)) * 100 : 0) + "%");
  }
  root.addEventListener("input", function (e) { if (e.target.type === "range") rangeFill(e.target); });

  /* ---------------- motion helpers ---------------- */
  function tween(ms, step, done) {
    if (REDUCED || ms <= 0) { step(1); done && done(); return function () {}; }
    var t0 = performance.now(), live = true;
    (function tick(now) {
      if (!live) return;
      var t = Math.min(1, (now - t0) / ms); step(EASE(t));
      if (t < 1) requestAnimationFrame(tick); else done && done();
    })(t0);
    return function () { live = false; };
  }
  // set a figure on an element; it counts from what it showed to the new value
  function num(el, v, f, ms) {
    if (typeof el === "string") el = root.querySelector(el);
    if (!el) return;
    f = f || el.getAttribute("data-f") || "eur";
    var from = el._kv != null ? el._kv : parseFloat(el.getAttribute("data-v"));
    if (!isFinite(from)) from = v;
    if (el._kstop) el._kstop();
    el._kv = v; el.setAttribute("data-v", v); el.setAttribute("data-f", f);
    el._kstop = tween(from === v ? 0 : ms || 450, function (t) { el.innerHTML = figHtml(from + (v - from) * t, f); });
  }
  function el(tag, attrs, parentNode) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (parentNode) parentNode.appendChild(e);
    return e;
  }
  function h(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; e.setAttribute("data-k-own", ""); return e; }
  var TONES = { brand: "brand", ink: "ink", dim: "ink-3", soft: "brand-line", mid: "brand-mid", line: "line-strong", warn: "warn", neg: "neg", info: "info", fixed: "fixed", everyday: "everyday", surprise: "surprise", saving: "saving" };
  function tone(t, fallback) { return "var(--color-" + (TONES[t] || TONES[fallback] || "brand") + ")"; }
  function color(t) { var d = document.createElement("i"); d.style.color = tone(t); root.appendChild(d); var c = getComputedStyle(d).color; d.remove(); return c; }
  function niceTicks(lo, hi, n) {
    var span = hi - lo || 1, raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p, step = (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p, out = [];
    for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }
  function xval(v) { // -> [number, kind]
    var d = ymd(v); if (d && typeof v === "string") return [Date.UTC(d[0], d[1] - 1, d[2] || 1) / 864e5, "date"];
    return typeof v === "number" || (v !== "" && isFinite(v)) ? [+v, "num"] : [NaN, "ord"];
  }
  function sigOf(elm) {
    var s = "", i; for (i = 0; i < elm.attributes.length; i++) if (elm.attributes[i].name.indexOf("data-k-") !== 0) s += elm.attributes[i].name + "=" + elm.attributes[i].value + ";";
    for (i = 0; i < elm.children.length; i++) if (!own(elm.children[i])) s += elm.children[i].nodeName === "TEMPLATE" ? elm.children[i].innerHTML : elm.children[i].outerHTML;
    return s + "|" + (elm.clientWidth || 0) + "|" + S.lang + (S.inited ? 1 : 0);
  }
  function Base() { return Reflect.construct(HTMLElement, [], this.constructor); }
  Base.prototype = Object.create(HTMLElement.prototype);
  Base.prototype.connectedCallback = function () {
    var me = this;
    if (window.ResizeObserver && !this._ro) { this._ro = new ResizeObserver(function () { me._sync(); }); this._ro.observe(this); }
    if (!this._mo) { this._mo = new MutationObserver(function () { me._watch(); me._sync(); }); this._watch(); }
    this._sync();
  };
  // a changed attribute on the element or on one of its series redraws it: chart.querySelector("k-line").setAttribute("table", "fan_200")
  Base.prototype._watch = function () {
    this._mo.disconnect(); this._mo.observe(this, { attributes: true, childList: true });
    for (var i = 0; i < this.children.length; i++) if (!own(this.children[i])) this._mo.observe(this.children[i], { attributes: true });
  };
  Base.prototype.disconnectedCallback = function () { if (this._ro) { this._ro.disconnect(); this._ro = null; } if (this._mo) { this._mo.disconnect(); this._mo = null; } };
  Base.prototype._sync = function () { if (!this.isConnected) return; var s = sigOf(this); if (s === this._sig) return; this._sig = s; this._render(); reportHeight(); };
  Base.prototype.refresh = function () { this._sig = null; this._sync(); };
  Base.prototype._clear = function () { var k = this.children; for (var i = k.length - 1; i >= 0; i--) if (own(k[i])) k[i].remove(); };
  function define(name, proto) {
    function C() { return Reflect.construct(HTMLElement, [], C); }
    C.prototype = Object.create(Base.prototype); C.prototype.constructor = C;
    for (var k in proto) C.prototype[k] = proto[k];
    customElements.define(name, C);
  }

  /* ---------------- k-chart: lines, bands, marks over a shared x ---------------- */
  define("k-chart", {
    set: function (o) { // change attributes on every series at once, e.g. chart.set({table: "fan_200"})
      var kids = this.querySelectorAll("k-line,k-area");
      for (var i = 0; i < kids.length; i++) for (var k in o) kids[i].setAttribute(k, o[k]);
      this._sync();
    },
    _render: function () {
      var me = this, W = this.clientWidth || S.width - 40, H = +this.getAttribute("h") || 190;
      var xcol = this.getAttribute("x") || "date", yf = this.getAttribute("yfmt") || "eur0";
      var kids = Array.prototype.filter.call(this.children, function (c) { return !own(c); });
      var series = [], kind = "ord", xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity, ordN = 0;
      kids.forEach(function (c) {
        var tag = c.nodeName.toLowerCase(); if (tag !== "k-line" && tag !== "k-area") return;
        var rows = table(c.getAttribute("table")), xc = c.getAttribute("x") || xcol;
        var cols = tag === "k-area" && c.hasAttribute("lo") ? [c.getAttribute("lo"), c.getAttribute("hi")] : [c.getAttribute("y") || "value"];
        var pts = [];
        rows.forEach(function (r, i) {
          var xv = xval(r[xc]), a = +r[cols[0]], b = cols[1] ? +r[cols[1]] : a;
          if (!isFinite(a) || !isFinite(b)) return;
          if (xv[1] === "ord") xv[0] = i; else kind = xv[1];
          pts.push({ x: xv[0], a: a, b: b, row: r, xr: r[xc] });
          if (xv[0] < xmin) xmin = xv[0]; if (xv[0] > xmax) xmax = xv[0];
          if (Math.min(a, b) < ymin) ymin = Math.min(a, b); if (Math.max(a, b) > ymax) ymax = Math.max(a, b);
        });
        ordN = Math.max(ordN, rows.length);
        series.push({ el: c, tag: tag, band: cols.length === 2, pts: pts, tone: c.getAttribute("tone"), label: c.getAttribute("label"), dash: c.hasAttribute("dash"), fill: c.hasAttribute("fill") || (tag === "k-area" && cols.length === 1), end: c.hasAttribute("end"), w: +c.getAttribute("w") || 2, f: c.getAttribute("fmt") || yf });
      });
      var first = !this._drawn;
      this._clear();
      var readout = null, hasLabels = series.some(function (s) { return s.label; });
      if (hasLabels) { readout = h("div", "k-readout k-legend"); this.appendChild(readout); }
      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, height: H, role: "img" }); svg.setAttribute("data-k-own", ""); this.appendChild(svg);
      if (!series.length || !isFinite(xmin)) return;
      kids.forEach(function (c) { // rules and marks stretch the y range too
        if (c.nodeName === "K-RULE" && isFinite(+c.getAttribute("y"))) { ymin = Math.min(ymin, +c.getAttribute("y")); ymax = Math.max(ymax, +c.getAttribute("y")); }
        if (c.nodeName === "K-NOW" || c.nodeName === "K-MARK") { var xs = c.nodeName === "K-NOW" ? [c.getAttribute("x") || S.data.today] : table(c.getAttribute("table")).map(function (r) { return r[c.getAttribute("x") || xcol]; }); xs.forEach(function (v) { var q = xval(v); if (q[1] !== "ord") { xmin = Math.min(xmin, q[0]); xmax = Math.max(xmax, q[0]); } }); }
      });
      if (this.hasAttribute("ymin")) ymin = +this.getAttribute("ymin");
      if (this.hasAttribute("ymax")) ymax = +this.getAttribute("ymax");
      if (this.hasAttribute("zero") || (ymin >= 0 && ymin < 0.4 * ymax)) ymin = Math.min(0, ymin);
      var pad = (ymax - ymin || 1) * 0.08; if (!this.hasAttribute("ymax")) ymax += pad; if (ymin !== 0 && !this.hasAttribute("ymin")) ymin -= pad;
      var ticks = niceTicks(ymin, ymax, 3), marked = kids.some(function (c) { return c.nodeName === "K-MARK"; });
      // the scale has its own gutter on the left, so a line never runs through a label
      var PL = this.hasAttribute("bare") ? 0 : Math.ceil(Math.max.apply(null, ticks.map(function (t) { return apply(t, yf).length; }).concat(2)) * 6.1) + 10;
      // and a line that ends with its value gets room for it on the right
      var PR = 0; series.forEach(function (s) { if (s.end && s.pts.length) PR = Math.max(PR, Math.ceil(apply(s.pts[s.pts.length - 1].b, s.f).length * 6.5) + 12); });
      var T = marked ? 26 : 10, B = 22, ph = H - T - B, pw = W - PL - PR;
      var X = function (v) { return PL + (xmax > xmin ? ((v - xmin) / (xmax - xmin)) * pw : pw / 2); };
      var Y = function (v) { return T + ph - ((v - ymin) / (ymax - ymin || 1)) * ph; };
      // grid
      var g = el("g", {}, svg);
      ticks.forEach(function (t) {
        var y = Math.round(Y(t)) + 0.5; if (y < T - 2 || y > T + ph + 1) return;
        el("line", { x1: PL, x2: W - PR, y1: y, y2: y, class: "k-grid" + (t === 0 ? " k-zero" : "") }, g);
        if (PL) el("text", { x: 0, y: y + 3.5, class: "k-ax" }, g).textContent = apply(t, yf);
      });
      // plot, revealed left to right the first time
      var clipId = "kc" + Math.random().toString(36).slice(2, 8), defs = el("defs", {}, svg), plot = el("g", {}, svg);
      if (first && !REDUCED) {
        var cr = el("rect", { x: -4, y: -4, width: W + 8, height: H + 8 }, el("clipPath", { id: clipId }, defs));
        plot.setAttribute("clip-path", "url(#" + clipId + ")");
        cr.style.transformBox = "fill-box"; cr.style.transformOrigin = "left center";
        cr.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { duration: 1100, easing: "cubic-bezier(0.3, 0.7, 0.2, 1)" });
      }
      var geo = [];
      series.forEach(function (s, si) {
        var c = tone(s.tone, s.tag === "k-area" ? "soft" : "brand"), top = s.pts.map(function (p) { return [X(p.x), Y(p.b)]; }), bot = s.band ? s.pts.map(function (p) { return [X(p.x), Y(p.a)]; }) : null;
        s.px = top;
        var shape = { top: top, bot: bot, paths: [] };
        if (s.band || s.fill) { var a = el("path", { fill: c, "fill-opacity": s.band ? (s.el.getAttribute("opacity") || 0.2) : 0.1, stroke: "none" }, plot); shape.area = a; }
        if (s.tag === "k-line") { var ln = el("path", { fill: "none", stroke: c, "stroke-width": s.w, "stroke-linejoin": "round", "stroke-linecap": "round" }, plot); if (s.dash) ln.setAttribute("stroke-dasharray", "1 5"); shape.line = ln; }
        if (s.end && top.length) { shape.dot = el("circle", { r: 4, fill: c, stroke: "var(--color-surface)", "stroke-width": 2 }, plot); shape.lab = el("text", { class: "k-ax on", "text-anchor": "start", style: "fill:" + c }, plot); shape.lab.textContent = apply(s.pts[s.pts.length - 1].b, s.f); }
        geo.push(shape);
      });
      function d(pts) { return pts.length ? "M" + pts.map(function (p) { return p[0].toFixed(1) + " " + p[1].toFixed(1); }).join("L") : ""; }
      function draw(t, prev) {
        var ends = [];
        geo.forEach(function (s, i) {
          var p = prev && prev[i], mix = function (now, was) { return !was || was.length !== now.length || t >= 1 ? now : now.map(function (q, j) { return [was[j][0] + (q[0] - was[j][0]) * t, was[j][1] + (q[1] - was[j][1]) * t]; }); };
          var top = mix(s.top, p && p.top), bot = s.bot ? mix(s.bot, p && p.bot) : null;
          if (s.line) s.line.setAttribute("d", d(top));
          if (s.area) s.area.setAttribute("d", top.length ? d(top) + "L" + (bot ? bot.slice().reverse().map(function (q) { return q[0].toFixed(1) + " " + q[1].toFixed(1); }).join("L") : top[top.length - 1][0].toFixed(1) + " " + (T + ph) + "L" + top[0][0].toFixed(1) + " " + (T + ph)) + "Z" : "");
          if (s.dot) { var e = top[top.length - 1]; s.dot.setAttribute("cx", e[0]); s.dot.setAttribute("cy", e[1]); ends.push({ lab: s.lab, x: e[0] + 9, y: e[1] + 4 }); }
        });
        // values at the ends of lines: beside their dots, pushed apart when two lines end close together
        ends.sort(function (a, b) { return a.y - b.y; });
        for (var q = 1; q < ends.length; q++) if (ends[q].y - ends[q - 1].y < 13) { var mid = (ends[q].y + ends[q - 1].y) / 2; ends[q - 1].y = mid - 6.5; ends[q].y = mid + 6.5; }
        ends.forEach(function (o) { o.lab.setAttribute("x", o.x); o.lab.setAttribute("y", Math.max(10, Math.min(T + ph + 4, o.y))); });
      }
      if (this._stop) this._stop();
      var prev = this._geo; this._geo = geo.map(function (s) { return { top: s.top, bot: s.bot }; });
      if (prev && !first && prev.length === geo.length) { draw(0, prev); this._stop = tween(520, function (t) { draw(t, prev); }); } else draw(1);
      this._drawn = true;
      // where a value sits on the first line that covers x
      function onLine(xv) {
        for (var i = 0; i < series.length; i++) { var s = series[i]; if (s.tag !== "k-line" || !s.pts.length) continue; var p = s.pts; if (xv < p[0].x || xv > p[p.length - 1].x) continue; for (var j = 1; j < p.length; j++) if (xv <= p[j].x) { var t = (xv - p[j - 1].x) / (p[j].x - p[j - 1].x || 1); return p[j - 1].b + (p[j].b - p[j - 1].b) * t; } return p[0].b; }
        return null;
      }
      var xl = (this.getAttribute("xlabels") || "").split("|"), xf = this.getAttribute("xfmt") || (kind === "date" ? "date" : "raw");
      var firstRow = null, lastRow = null;
      series.forEach(function (s) { if (!s.pts.length) return; if (!firstRow || s.pts[0].x < firstRow.x) firstRow = s.pts[0]; if (!lastRow || s.pts[s.pts.length - 1].x > lastRow.x) lastRow = s.pts[s.pts.length - 1]; });
      var axis = el("g", {}, svg), taken = [];
      function xlab(px, text, cls, anchor) {
        var w = text.length * 6.2 + 8, lo = anchor === "start" ? px : anchor === "end" ? px - w : px - w / 2;
        for (var i = 0; i < taken.length; i++) if (lo < taken[i][1] && lo + w > taken[i][0]) return;
        taken.push([lo, lo + w]);
        el("text", { x: px, y: H - 5, class: "k-ax" + (cls || ""), "text-anchor": anchor }, axis).textContent = text;
      }
      kids.forEach(function (c) {
        var tag = c.nodeName.toLowerCase(), col = tone(c.getAttribute("tone"), "ink");
        if (tag === "k-now") {
          var q = xval(c.getAttribute("x") || S.data.today), px = Math.round(X(q[0])) + 0.5;
          el("line", { x1: px, x2: px, y1: T - 4, y2: T + ph, stroke: "var(--color-ink)", "stroke-width": 1, "stroke-dasharray": "2 3" }, axis);
          xlab(px, c.getAttribute("label") || loc().today, " on", px < PL + 30 ? "start" : px > W - PR - 30 ? "end" : "middle");
        } else if (tag === "k-rule") {
          var yv = +c.getAttribute("y"); if (!isFinite(yv)) return; var py = Math.round(Y(yv)) + 0.5;
          el("line", { x1: PL, x2: W - PR, y1: py, y2: py, stroke: col, "stroke-width": 1, "stroke-dasharray": "3 3" }, axis);
          if (c.getAttribute("label")) el("text", { x: PL + 2, y: py - 5, class: "k-ax on k-halo", "text-anchor": "start", style: "fill:" + col }, axis).textContent = c.getAttribute("label");
        } else if (tag === "k-mark") {
          var by = {}, order = [];
          table(c.getAttribute("table")).forEach(function (r) { var k = r[c.getAttribute("x") || xcol]; if (!by[k]) { by[k] = []; order.push(k); } by[k].push(r[c.getAttribute("label") || "label"]); });
          order.forEach(function (k) {
            var q = xval(k), px = X(q[0]), v = onLine(q[0]), py = v == null ? T + ph : Y(v);
            // the name sits above the plot, a hairline drops from it to the point on the line
            el("line", { x1: px, x2: px, y1: T - 8, y2: py, stroke: col, "stroke-width": 1, opacity: 0.45 }, axis);
            el("circle", { cx: px, cy: py, r: 4.5, fill: "var(--color-surface)", stroke: col, "stroke-width": 2 }, axis);
            var text = by[k].filter(Boolean).join(" + "); if (!text) return;
            if (text.length > 30) text = text.slice(0, 29) + "…";
            var half = text.length * 3.3, anchor = px - half < PL ? "start" : px + half > W ? "end" : "middle";
            el("text", { x: anchor === "start" ? Math.max(PL, px - 6) : anchor === "end" ? Math.min(W, px + 6) : px, y: T - 13, class: "k-ax on", "text-anchor": anchor }, axis).textContent = text;
          });
        }
      });
      if (firstRow) xlab(PL, xl[0] || apply(firstRow.xr, xf), "", "start");
      if (lastRow && lastRow !== firstRow) xlab(W - PR, xl[1] || apply(lastRow.xr, xf), "", "end");
      // legend, replaced by the values under the finger
      function legend() {
        if (!readout) return;
        readout.innerHTML = series.filter(function (s) { return s.label; }).map(function (s) { return '<span><i style="--c:' + tone(s.tone, s.tag === "k-area" ? "soft" : "brand") + '"' + (s.tag === "k-line" ? ' data-line="' + (s.dash ? "dash" : "solid") + '"' : "") + "></i>" + esc(s.label) + "</span>"; }).join("");
      }
      legend();
      if (this.hasAttribute("noscrub")) return;
      var cur = el("g", { style: "display:none" }, svg), vline = el("line", { y1: T - 4, y2: T + ph, stroke: "var(--color-ink)", "stroke-width": 1 }, cur), dots = [];
      series.forEach(function (s) { dots.push(s.tag === "k-line" ? el("circle", { r: 4.5, fill: tone(s.tone, "brand"), stroke: "var(--color-surface)", "stroke-width": 2 }, cur) : null); });
      var hit = el("rect", { x: 0, y: 0, width: W, height: H, fill: "transparent" }, svg);
      function at(ev) {
        var r = svg.getBoundingClientRect(), mx = ((ev.clientX - r.left) / r.width) * W, best = null, bd = 1e9;
        series.forEach(function (s) { if (s.tag !== "k-line") return; s.px.forEach(function (p, j) { var dd = Math.abs(p[0] - mx); if (dd < bd) { bd = dd; best = { s: s, j: j }; } }); });
        if (!best) return;
        var bx = best.s.px[best.j][0], pt = best.s.pts[best.j], out = '<span class="k-when">' + esc(apply(pt.xr, xf)) + "</span>";
        cur.style.display = ""; vline.setAttribute("x1", bx); vline.setAttribute("x2", bx);
        series.forEach(function (s, i) {
          var j = -1; s.px.forEach(function (p, k) { if (Math.abs(p[0] - bx) < 0.75) j = k; });
          if (dots[i]) { dots[i].style.display = j < 0 ? "none" : ""; if (j >= 0) { dots[i].setAttribute("cx", s.px[j][0]); dots[i].setAttribute("cy", s.px[j][1]); } }
          if (j >= 0 && (s.label || series.length === 1)) out += '<span><i style="--c:' + tone(s.tone, s.tag === "k-area" ? "soft" : "brand") + '"' + (s.tag === "k-line" ? ' data-line="solid"' : "") + "></i><b>" + (s.band ? esc(apply(s.pts[j].a, s.f)) + "–" + esc(apply(s.pts[j].b, s.f)) : esc(apply(s.pts[j].b, s.f))) + "</b></span>";
        });
        if (readout) readout.innerHTML = out;
        me.dispatchEvent(new CustomEvent("k-scrub", { bubbles: true, detail: { row: pt.row, x: pt.xr } }));
      }
      hit.addEventListener("pointerdown", function (e) { try { hit.setPointerCapture(e.pointerId); } catch (x) {} at(e); });
      hit.addEventListener("pointermove", function (e) { if (e.pointerType === "mouse" || e.buttons || e.pressure > 0) at(e); });
      var off = function () { cur.style.display = "none"; legend(); };
      hit.addEventListener("pointerleave", off); hit.addEventListener("pointerup", function (e) { if (e.pointerType !== "mouse") off(); }); hit.addEventListener("pointercancel", off);
    },
  });

  /* ---------------- k-heat: a grid of values, or a year of days ---------------- */
  define("k-heat", {
    _render: function () {
      var me = this, W = this.clientWidth || S.width - 40, rows = table(this.getAttribute("table")), vcol = this.getAttribute("v") || "value";
      var dateCol = this.getAttribute("date"), xc = this.getAttribute("x"), yc = this.getAttribute("y"), xf = this.getAttribute("xfmt"), yfm = this.getAttribute("yfmt");
      var col = tone(this.getAttribute("tone"), "brand");
      this._clear();
      if (!rows.length) { var ph0 = el("svg", { height: 160, viewBox: "0 0 " + W + " 160" }); ph0.setAttribute("data-k-own", ""); this.appendChild(ph0); return; }
      // cells: {xi, yi, band, v, row}; slots: every place a cell could be (the empty grid)
      var cells = [], slots = [], xlabels = [], ylabels = [], vmax = 0, nx, ny, bands = 1;
      if (dateCol) {
        var days = rows.map(function (r) { return { d: xval(r[dateCol])[0], r: r }; }).filter(function (o) { return isFinite(o.d); }).sort(function (a, b) { return a.d - b.d; });
        var dow = function (dd) { return (((dd + 3) % 7) + 7) % 7; }; // 1970-01-01 was a Thursday; Monday = 0
        var first = days[0].d, last = days[days.length - 1].d, start = first - dow(first), nW = Math.floor((last - start) / 7) + 1;
        bands = Math.ceil(nW / 27); nx = Math.ceil(nW / bands); ny = 7;    // a year is two bands of half a year each
        ylabels = [loc().wd[0], "", "", loc().wd[3], "", "", loc().wd[6]];
        var seenM = {};
        for (var dd = first; dd <= last; dd++) {
          var wk = Math.floor((dd - start) / 7), slot = { xi: wk % nx, yi: dow(dd), band: Math.floor(wk / nx) }, dt = new Date(dd * 864e5), mk = dt.getUTCFullYear() + "-" + dt.getUTCMonth();
          slots.push(slot);
          if (!seenM[mk] && dt.getUTCDate() <= 7) { seenM[mk] = 1; xlabels.push({ xi: slot.xi, band: slot.band, s: loc().mon[dt.getUTCMonth()] }); }
        }
        days.forEach(function (o) { var v = +o.r[vcol] || 0, wk = Math.floor((o.d - start) / 7); cells.push({ xi: wk % nx, yi: dow(o.d), band: Math.floor(wk / nx), v: v, row: o.r }); if (v > vmax) vmax = v; });
      } else {
        var uniq = function (c) {
          var seen = {}, out = []; rows.forEach(function (r) { var k = r[c]; if (!(k in seen)) { seen[k] = 1; out.push(k); } });
          if (out.every(function (k) { return typeof k === "number"; })) {
            // a run of whole numbers gets its gaps filled (weekdays, hours); blocks of two hours stay as they are
            out.sort(function (a, b) { return a - b; });
            var unit = out.some(function (k, j) { return j && k - out[j - 1] === 1; }), full = []; for (var q = out[0]; q <= out[out.length - 1]; q++) full.push(q);
            if (unit && full.length <= out.length * 3) out = full;
          } else if (out.every(function (k) { return /^\d/.test(String(k)); })) out.sort(function (a, b) { return parseFloat(a) - parseFloat(b); });
          else if (out.every(function (k) { return wdIndex(k) >= 0 && isNaN(+k); })) out.sort(function (a, b) { return wdIndex(a) - wdIndex(b); });
          return out;
        };
        var xs = uniq(xc), ys = uniq(yc); nx = xs.length; ny = ys.length;
        xs.forEach(function (k, i) { xlabels.push({ xi: i, band: 0, s: xf ? apply(k, xf) : String(k) }); }); ylabels = ys.map(function (k) { return yfm ? apply(k, yfm) : String(k); });
        for (var gy = 0; gy < ny; gy++) for (var gx = 0; gx < nx; gx++) slots.push({ xi: gx, yi: gy, band: 0 });
        rows.forEach(function (r) { var v = +r[vcol] || 0; cells.push({ xi: xs.indexOf(r[xc]), yi: ys.indexOf(r[yc]), band: 0, v: v, row: r }); if (v > vmax) vmax = v; });
      }
      var labW = Math.min(64, Math.max.apply(null, ylabels.map(function (t) { return t.length; })) * 6.4 + 10), gap = nx > 20 ? 2 : 3;
      var cw = (W - labW - gap * (nx - 1)) / nx, ch = dateCol ? cw : Math.max(20, Math.min(34, cw));
      var labH = 18, bandH = ny * ch + (ny - 1) * gap, topPad = dateCol ? labH : 2, bandStep = bandH + (dateCol ? labH + 6 : 0);
      var H = topPad + bands * bandH + (bands - 1) * (bandStep - bandH) + (dateCol ? 2 : 20);
      var X = function (c) { return labW + c.xi * (cw + gap); }, Y = function (c) { return topPad + c.band * bandStep + c.yi * (ch + gap); };
      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, height: H }); svg.setAttribute("data-k-own", "");
      var rad = Math.min(6, cw / 3.2), picked = null;
      for (var bi = 0; bi < bands; bi++) ylabels.forEach(function (t, i) { if (t) el("text", { x: 0, y: Y({ band: bi, yi: i }) + ch / 2 + 4, class: "k-ax" }, svg).textContent = t; });
      var stepL = Math.max(1, Math.ceil(30 / (cw + gap))), lastLab = {};
      xlabels.forEach(function (o, i) {
        if (!o.s) return;
        if (dateCol) { if (lastLab[o.band] != null && o.xi - lastLab[o.band] < 3) return; lastLab[o.band] = o.xi; el("text", { x: X(o), y: Y({ band: o.band, yi: 0 }) - 6, class: "k-ax" }, svg).textContent = o.s; }
        else if (i % stepL === 0) el("text", { x: X(o) + cw / 2, y: H - 5, class: "k-ax", "text-anchor": "middle" }, svg).textContent = o.s;
      });
      // the empty grid first, values on top
      slots.forEach(function (c) { el("rect", { x: X(c), y: Y(c), width: cw, height: ch, rx: rad, fill: "var(--color-sunk)" }, svg); });
      var firstDraw = !this._drawn; this._drawn = true;
      cells.forEach(function (c) {
        if (c.xi < 0 || c.yi < 0) return;
        var r = el("rect", { x: X(c), y: Y(c), width: cw, height: ch, rx: rad }, svg);
        var p = c.v > 0 && vmax > 0 ? 8 + 92 * Math.pow(c.v / vmax, 0.8) : 0;
        r.style.fill = p ? "color-mix(in oklch, " + col + " " + p.toFixed(0) + "%, var(--k-heat-low, var(--color-brand-soft)))" : "transparent";
        if (firstDraw && !REDUCED && p) r.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: 250 + ((c.xi + c.band * nx) / (nx * bands)) * 700, fill: "backwards", easing: "ease-out" });
        c.el = r; c.cx = X(c) + cw / 2; c.cy = Y(c) + ch / 2;
      });
      var ring = el("rect", { fill: "none", stroke: "var(--color-ink)", "stroke-width": 2, rx: rad + 1.5, style: "display:none;pointer-events:none" }, svg);
      this.appendChild(svg);
      var tpl = this.getAttribute("readout"), out = tpl ? h("div", "k-readout") : null; if (out) this.appendChild(out);
      function pick(c, quiet) {
        if (!c || c === picked) return; picked = c;
        ring.style.display = ""; ring.setAttribute("x", +c.el.getAttribute("x") - 2); ring.setAttribute("y", +c.el.getAttribute("y") - 2); ring.setAttribute("width", cw + 4); ring.setAttribute("height", ch + 4);
        if (out) out.innerHTML = fillRow(tpl, c.row, 0).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
        if (!quiet) me.dispatchEvent(new CustomEvent("k-pick", { bubbles: true, detail: c.row }));
      }
      this.pick = function (fn) { for (var i = 0; i < cells.length; i++) if (cells[i].el && fn(cells[i].row)) return pick(cells[i]); };
      function at(ev) { // the nearest cell that holds a value, within reach of a finger
        var r = svg.getBoundingClientRect(), mx = ((ev.clientX - r.left) / r.width) * W, my = ((ev.clientY - r.top) / r.height) * H, best = null, bd = Math.pow(Math.max(22, cw * 1.6), 2);
        cells.forEach(function (c) { if (!c.el) return; var d2 = Math.pow(c.cx - mx, 2) + Math.pow(c.cy - my, 2); if (d2 < bd) { bd = d2; best = c; } });
        pick(best);
      }
      svg.addEventListener("pointerdown", function (e) { try { svg.setPointerCapture(e.pointerId); } catch (x) {} at(e); });
      svg.addEventListener("pointermove", function (e) { if (e.buttons || (e.pointerType !== "mouse" && e.pressure > 0)) at(e); });
      var init = this.getAttribute("pick") || "max";
      if (init !== "none") { var top = null; cells.forEach(function (c) { if (c.el && (!top || c.v > top.v)) top = c; }); pick(top, true); }
    },
  });

  /* ---------------- k-bars ---------------- */
  define("k-bars", {
    _render: function () {
      var me = this, W = this.clientWidth || S.width - 40, rows = table(this.getAttribute("table")).slice(), xc = this.getAttribute("x") || "label", yc = this.getAttribute("y") || "value";
      var f = this.getAttribute("fmt") || "eur0", xf = this.getAttribute("xfmt"), horiz = this.getAttribute("dir") === "h", limit = +this.getAttribute("limit") || (horiz ? 8 : 40);
      var sort = this.getAttribute("sort"); if (sort) { var desc = sort[0] === "-", sc = sort.replace(/^-/, "") || yc; rows.sort(function (a, b) { return desc ? b[sc] - a[sc] : a[sc] - b[sc]; }); }
      rows = rows.slice(0, limit);
      var firstDraw = !this._drawn; this._drawn = true;
      this._clear(); if (!rows.length) return;
      var vmax = Math.max.apply(null, rows.map(function (r) { return +r[yc] || 0; })) || 1, pickMode = this.getAttribute("pick") || "max", sel = -1;
      if (pickMode === "max") rows.forEach(function (r, i) { if (sel < 0 || +r[yc] > +rows[sel][yc]) sel = i; }); else if (pickMode === "last") sel = rows.length - 1; else if (/^\d+$/.test(pickMode)) sel = +pickMode;
      var lab = function (r) { return xf ? apply(r[xc], xf) : String(r[xc]); };
      var tpl = this.getAttribute("readout");
      if (horiz) {
        var items = rows.map(function (r, i) {
          var b = h("button", "k-hbar", "<span>" + esc(lab(r)) + '</span><i style="--w:' + ((+r[yc] / vmax) * 100).toFixed(1) + ";--i:" + i + '"></i><b class="k-n">' + esc(apply(r[yc], f)) + "</b>");
          if (!firstDraw) b.querySelector("i").style.animation = "none";
          b.addEventListener("click", function () { choose(i); }); me.appendChild(b); return b;
        });
        var out = tpl ? h("div", "k-readout") : null; if (out) this.appendChild(out);
        var choose = function (i, quiet) { sel = i; items.forEach(function (b, j) { b.setAttribute("aria-current", j === i ? "true" : "false"); }); if (out && rows[i]) out.innerHTML = fillRow(tpl, rows[i], i).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); if (!quiet) me.dispatchEvent(new CustomEvent("k-pick", { bubbles: true, detail: rows[i] })); };
        choose(sel, true); return;
      }
      var H = +this.getAttribute("h") || 150, T = 22, B = 22, n = rows.length, band = W / n, bw = Math.max(3, Math.min(44, band * (n > 20 ? 0.78 : 0.62))), ph = H - T - B;
      var svg = el("svg", { viewBox: "0 0 " + W + " " + H, height: H }); svg.setAttribute("data-k-own", ""); this.appendChild(svg);
      el("line", { x1: 0, x2: W, y1: T + ph + 0.5, y2: T + ph + 0.5, class: "k-grid" }, svg);
      var step = Math.max(1, Math.ceil(34 / band)), bars = [], labs = [], val = el("text", { class: "k-ax on", "text-anchor": "middle" }, svg);
      // a label gets the width of its slot: a long weekday becomes its short form, anything else is cut with an ellipsis
      var maxCh = Math.max(2, Math.floor((band * step - 4) / 6.6)), full = lab, all = rows.map(full);
      var days = all.some(function (t) { return t.length > maxCh; }) && all.every(function (t) { return isNaN(+t) && wdIndex(t) >= 0; }); // one long weekday: all go short together
      lab = function (r) {
        var t = full(r); if (days) t = loc().wd[wdIndex(t)];
        return t.length <= maxCh ? t : t.slice(0, Math.max(1, maxCh - 1)).replace(/\s+$/, "") + "…";
      };
      rows.forEach(function (r, i) {
        var v = Math.max(0, +r[yc] || 0), bh = Math.max(v > 0 ? 2 : 0, (v / vmax) * ph), x = i * band + (band - bw) / 2;
        var b = el("rect", { x: x, y: T + ph - bh, width: bw, height: bh, rx: Math.min(5, bw / 2.5) }, svg);
        b.style.transition = "fill 200ms"; b.style.transformBox = "fill-box"; b.style.transformOrigin = "bottom";
        if (firstDraw && !REDUCED) b.animate([{ transform: "scaleY(0)" }, { transform: "scaleY(1)" }], { duration: 700, delay: 120 + i * (360 / n), fill: "backwards", easing: "cubic-bezier(0.16, 1, 0.3, 1)" });
        bars.push(b);
        var t = el("text", { x: i * band + band / 2, y: H - 5, class: "k-ax", "text-anchor": "middle" }, svg); var endL = step === 2 && i === n - 1, nearEnd = step === 2 && i !== n - 1 && n - 1 - i < step; /* the last bar keeps its label, so its neighbour gives way */ t.textContent = (i % step === 0 && !nearEnd) || endL ? lab(r) : ""; labs.push(t);
        var hitr = el("rect", { x: i * band, y: 0, width: band, height: H, fill: "transparent", class: "k-hit" }, svg);
        hitr.addEventListener("pointerdown", function () { choose(i); }); hitr.addEventListener("pointerenter", function (e) { if (e.buttons) choose(i); });
      });
      var out2 = tpl ? h("div", "k-readout") : null; if (out2) this.appendChild(out2);
      var col = tone(this.getAttribute("tone"), "brand");
      function choose(i, quiet) {
        sel = i;
        bars.forEach(function (b, j) { b.style.fill = j === i || i < 0 ? col : "var(--color-brand-line)"; if (me.closest("k-slides")) b.style.fill = j === i || i < 0 ? "var(--k-tone)" : "var(--k-rule)"; });
        labs.forEach(function (t, j) { t.setAttribute("class", "k-ax" + (j === i ? " on" : "")); if (j === i && !t.textContent) t.textContent = lab(rows[j]); });
        if (i >= 0) { var bx = i * band + band / 2; val.textContent = apply(rows[i][yc], f); val.setAttribute("x", Math.max(24, Math.min(W - 24, bx))); val.setAttribute("y", +bars[i].getAttribute("y") - 7); }
        if (out2 && rows[i]) out2.innerHTML = fillRow(tpl, rows[i], i).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
        if (!quiet && i >= 0) me.dispatchEvent(new CustomEvent("k-pick", { bubbles: true, detail: rows[i] }));
      }
      choose(sel, true);
    },
  });

  /* ---------------- k-each: one template, once per row ---------------- */
  define("k-each", {
    _render: function () {
      var tpl = this.querySelector(":scope > template"); this._clear(); if (!tpl) return;
      var src = this.hasAttribute("products") ? S.data.products : table(this.getAttribute("table")), rows = src.slice(), sort = this.getAttribute("sort");
      if (sort) { var desc = sort[0] === "-", sc = sort.replace(/^-/, ""); rows.sort(function (a, b) { return desc ? (b[sc] > a[sc] ? 1 : -1) : a[sc] > b[sc] ? 1 : -1; }); }
      var limit = +this.getAttribute("limit"), more = this.getAttribute("more"), total = rows.length;
      var html = tpl.innerHTML, box = document.createElement("template"), me = this, firstDraw = !this._drawn; this._drawn = true;
      function add(r, i, fresh, order) {
        box.innerHTML = fillRow(html, r, i);
        Array.prototype.slice.call(box.content.children).forEach(function (c) {
          c.setAttribute("data-k-own", ""); c.setAttribute("data-i", i); c.kRow = r;
          if (fresh && !REDUCED) { c.setAttribute("data-k-new", ""); c.style.animationDelay = Math.min(order, 8) * 45 + "ms"; }
          me.appendChild(c);
        });
      }
      var cut = limit && !(more && this._all) ? Math.min(limit, total) : total;
      for (var i = 0; i < cut; i++) add(rows[i], i, firstDraw, i);
      // more="Show all {n}": the rest stay out of the way until asked for, and then simply join the list (nothing is re-drawn)
      if (more && cut < total) {
        var btn = h("button", "k-more", esc(more.replace(/\{n\}/g, String(total)))); btn.type = "button";
        btn.addEventListener("click", function () {
          me._all = true; btn.remove();
          for (var j = cut; j < total; j++) add(rows[j], j, true, j - cut);
          me.dispatchEvent(new CustomEvent("k-more", { bubbles: true }));
        });
        this.appendChild(btn);
      }
    },
  });

  /* ---------------- k-product ---------------- */
  define("k-product", {
    _render: function () {
      var id = this.getAttribute("pid"), p = product(id) || (/^\d+$/.test(id || "") ? S.data.products[+id] : null);
      var k = this.children; for (var i = k.length - 1; i >= 0; i--) if (own(k[i])) k[i].remove();
      if (!p) return;
      var tile = this.getAttribute("layout") === "tile", meta = [p.brand && String(p.name || "").toLowerCase().indexOf(String(p.brand).toLowerCase()) !== 0 ? p.brand : "", p.size || p.store].filter(Boolean).slice(0, tile ? 1 : 2).join(" · ");
      var img = h("img", "k-pic" + (tile ? " l" : "")); img.alt = ""; img.loading = "eager"; if (p.image) img.src = p.image; img.onerror = function () { if (p.image && !img._again) { img._again = 1; setTimeout(function () { img.src = p.image + "&r=1"; }, 1200); } else img.style.visibility = "hidden"; };
      var text = h("div", "k-ptext", '<div class="k-pname">' + esc(p.name || "") + "</div>" + (meta ? '<div class="k-pmeta">' + esc(meta) + "</div>" : ""));
      var first = this.firstChild;
      this.insertBefore(img, first); this.insertBefore(text, first);
      if (!this.hasAttribute("noprice") && p.price != null) { var pr = h("div", "k-pprice k-n", figHtml(p.price, p.price % 1 ? "eur" : "eur0")); pr.setAttribute("data-trace", p.run || "products"); if (tile) text.appendChild(pr), pr.removeAttribute("data-k-own"); else this.insertBefore(pr, first); }
      if (this.hasAttribute("link") && p.url) { img.setAttribute("data-open", p.url); }
    },
  });

  /* ---------------- k-choice: one of several ---------------- */
  define("k-choice", {
    _render: function () {
      var me = this, kids = Array.prototype.filter.call(this.querySelectorAll("[value]"), function (c) { return !/^(INPUT|OPTION|LI|DATA|METER|PROGRESS|PARAM)$/.test(c.nodeName) && c.closest("k-choice") === me; });
      this.setAttribute("role", "radiogroup");
      if (this._value == null) { var pre = kids.filter(function (c) { return c.hasAttribute("checked"); })[0] || (this.hasAttribute("none") ? null : kids[0]); this._value = pre ? pre.getAttribute("value") : null; }
      kids.forEach(function (c) { c._kKeep = { "aria-checked": 1, role: 1, tabindex: 1 }; c.setAttribute("role", "radio"); c.setAttribute("tabindex", "0"); c.setAttribute("aria-checked", c.getAttribute("value") === me._value ? "true" : "false"); });
      if (!this._wired) {
        this._wired = true;
        var go = function (e) { var c = e.target.closest && e.target.closest("[value]"); if (c && c.closest("k-choice") === me) me.value = c.getAttribute("value"); };
        this.addEventListener("click", go);
        this.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(e); } });
      }
    },
  });
  // its options may arrive later and deeper (rows of a k-each): watch the whole subtree for them
  customElements.get("k-choice").prototype._watch = function () { this._mo.disconnect(); this._mo.observe(this, { childList: true, subtree: true, attributes: true, attributeFilter: ["value", "checked", "none", "class"] }); };
  Object.defineProperty(customElements.get("k-choice").prototype, "value", {
    get: function () { return this._value; },
    set: function (v) {
      v = String(v); if (v === this._value) return; this._value = v; var hit = null;
      Array.prototype.forEach.call(this.querySelectorAll("[value]"), function (c) { var on = c.getAttribute("value") === v; c.setAttribute("aria-checked", on ? "true" : "false"); if (on) hit = c; });
      this.dispatchEvent(new CustomEvent("change", { bubbles: true, detail: { value: v, el: hit, row: hit && (hit.kRow || (hit.closest("[data-i]") || {}).kRow) } }));
    },
  });

  /* ---------------- k-slides: tap-through story that advances by itself ---------------- */
  define("k-slides", {
    _render: function () {
      var me = this, secs = this._secs = Array.prototype.filter.call(this.children, function (c) { return c.nodeName === "SECTION"; });
      var prog = this.querySelector(":scope > .k-prog"); if (!prog) { prog = h("div", "k-prog"); this.appendChild(prog); }
      while (prog.children.length < secs.length) prog.appendChild(document.createElement("i")).appendChild(document.createElement("b"));
      while (prog.children.length > secs.length) prog.lastChild.remove();
      if (this._i == null) this._i = 0;
      this._kKeep = { style: 1 };
      if (this.getAttribute("h")) this.style.height = this.getAttribute("h") + "px";
      this._show(Math.min(this._i, Math.max(0, secs.length - 1)), true);
      if (!this._wired) {
        this._wired = true; var downAt = 0, held = false;
        this.addEventListener("pointerdown", function (e) { if (e.target.closest("button,a,[data-ask],input,k-choice")) return; downAt = performance.now(); held = false; me._holdT = setTimeout(function () { held = true; me._pause(true); }, 220); });
        var up = function (e) {
          clearTimeout(me._holdT); if (!downAt) return; downAt = 0;
          if (held) { me._pause(false); return; }
          if (e.type !== "pointerup") return;
          var r = me.getBoundingClientRect(); if ((e.clientX - r.left) / r.width < 0.3) me.go(me._i - 1); else me.go(me._i + 1);
        };
        this.addEventListener("pointerup", up); this.addEventListener("pointercancel", up); this.addEventListener("pointerleave", up);
      }
    },
    _show: function (i, quiet) {
      var secs = this._secs || [], prog = this.querySelector(":scope > .k-prog"); if (!secs.length) return;
      var changed = this._shown !== secs[i];
      this._i = i; this._shown = secs[i];
      secs.forEach(function (s, j) { if (j === i) s.setAttribute("data-k-on", ""); else s.removeAttribute("data-k-on"); });
      this.style.setProperty("--k-pc", getComputedStyle(secs[i]).color);
      Array.prototype.forEach.call(prog.children, function (b, j) { b.setAttribute("data-s", j < i ? "done" : j === i ? "on" : ""); if (j !== i && b._anim) { b._anim.cancel(); b._anim = null; } });
      if (changed && !quiet) {
        Array.prototype.forEach.call(secs[i].querySelectorAll(".k-big .k-n[data-v], .k-big[data-v]"), function (n) { var v = +n.getAttribute("data-v"), f = n.getAttribute("data-f"); n._kv = /^(eur|eur0|int)$/.test(f) ? 0 : v * 0.5; num(n, v, f, 1100); });
        Array.prototype.forEach.call(secs[i].querySelectorAll("k-bars,k-chart,k-heat"), function (c) { c._drawn = false; c._geo = null; c.refresh && c.refresh(); });
      }
    },
    play: function () { this._playing = true; this.go(this._i || 0, true); },
    _pause: function (on) { var b = this._bar(); if (b && b._anim) on ? b._anim.pause() : b._anim.play(); },
    _bar: function () { var p = this.querySelector(":scope > .k-prog"); return p && p.children[this._i] && p.children[this._i].firstChild; },
    go: function (i, force) {
      var secs = this._secs || [], me = this; if (!secs.length) return;
      if (i >= secs.length) { if (!force) i = 0; else i = secs.length - 1; }
      if (i < 0) i = 0;
      this._shown = force ? null : this._shown;
      this._show(i);
      var bar = this._bar(); if (!bar || !this._playing) return;
      if (bar._anim) bar._anim.cancel();
      var ms = +secs[i].getAttribute("ms") || +this.getAttribute("auto") || 4600;
      if (REDUCED) { bar.parentNode.setAttribute("data-s", "done"); return; }
      bar._anim = bar.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { duration: ms, easing: "linear", fill: "forwards" });
      bar._anim.onfinish = function () { if (me._i === i && i < secs.length - 1) me.go(i + 1); };
    },
  });

  /* ---------------- vendored libraries ---------------- */
  var libs = {}, here = (document.currentScript && document.currentScript.src) || "";
  function load(name) {
    if (libs[name]) return libs[name];
    var files = { three: "vendor/three.min.js" };
    if (!files[name]) return Promise.reject(new Error("unknown library " + name));
    return (libs[name] = new Promise(function (ok, no) {
      var s = document.createElement("script"); s.src = new URL(files[name], here || location.href).href;
      s.onload = function () { ok(window.THREE); }; s.onerror = function () { no(new Error("could not load " + name)); };
      document.head.appendChild(s);
    }));
  }
  // a small three.js stage in Kori's light: K.stage(el, {h}).then(({T, scene, camera, frame, color}) => ...)
  function stage(target, o) {
    if (typeof target === "string") target = root.querySelector(target);
    o = o || {};
    var Hh = o.h || 300; target._kKeep = { style: 1, "class": 1 }; target.classList.add("k-stage"); target.style.height = Hh + "px";
    return load("three").then(function (T) {
      var W = target.clientWidth || S.width - 40, ren = new T.WebGLRenderer({ antialias: true, alpha: true });
      ren.setPixelRatio(Math.min(2, devicePixelRatio || 1)); ren.setSize(W, Hh, false); target.appendChild(ren.domElement);
      var scene = new T.Scene(), cam = new T.PerspectiveCamera(o.fov || 30, W / Hh, 0.1, 200);
      cam.position.set.apply(cam.position, o.eye || [7, 6, 9]); cam.lookAt.apply(cam, o.look || [0, 0.8, 0]);
      scene.add(new T.HemisphereLight(0xffffff, 0xdfe6df, 1.15));
      var sun = new T.DirectionalLight(0xffffff, 1.4); sun.position.set(4, 9, 6); scene.add(sun);
      var pivot = new T.Group(); scene.add(pivot);
      var fns = [], rot = o.turn == null ? -0.5 : o.turn, target0 = rot, drag = null, dirty = true;
      pivot.rotation.y = rot - 0.6;
      target.addEventListener("pointerdown", function (e) { drag = { x: e.clientX, r: target0 }; try { target.setPointerCapture(e.pointerId); } catch (x) {} });
      target.addEventListener("pointermove", function (e) { if (drag) { target0 = drag.r + (e.clientX - drag.x) * 0.012; dirty = true; } });
      target.addEventListener("pointerup", function () { drag = null; }); target.addEventListener("pointercancel", function () { drag = null; });
      var t0 = performance.now();
      (function loop(now) {
        if (!target.isConnected) { ren.dispose(); return; }
        requestAnimationFrame(loop);
        var d = target0 - pivot.rotation.y, live = false;
        if (Math.abs(d) > 0.0005) { pivot.rotation.y += d * 0.09; live = true; }
        for (var i = 0; i < fns.length; i++) if (fns[i]((now - t0) / 1000) !== false) live = true;
        if (live || dirty) { ren.render(scene, cam); dirty = false; }
      })(t0);
      return { T: T, scene: scene, pivot: pivot, camera: cam, renderer: ren, width: W, height: Hh, frame: function (fn) { fns.push(fn); }, color: function (t) { return new T.Color(color(t)); }, redraw: function () { dirty = true; } };
    });
  }

  /* ---------------- K ---------------- */
  var K = (window.K = {
    data: S.data, lang: S.lang,
    fact: fact, table: table, product: product, fmt: fmt, html: figHtml,
    ask: function (text) { post({ kori: "ask", text: String(text) }); },
    open: function (url) { post({ kori: "open", url: String(url) }); },
    trace: function (name) { post({ kori: "trace", name: String(name) }); },
    load: load, stage: stage, num: num, tween: tween, ease: EASE, color: color, tone: tone, svg: el,
    $: function (s, ctx) { return (ctx || root).querySelector(s); },
    $$: function (s, ctx) { return Array.prototype.slice.call((ctx || root).querySelectorAll(s)); },
    on: function (sel, type, fn) { root.addEventListener(type, function (e) { var t = e.target instanceof Element ? e.target.closest(sel) : null; if (t && root.contains(t)) fn(e, t); }); },
    sum: function (rows, col) { return rows.reduce(function (a, r) { return a + (+(col ? r[col] : r) || 0); }, 0); },
    row: function (name, col, v) { var r = table(name); for (var i = 0; i < r.length; i++) if (r[i][col] == v) return r[i]; },
    fill: fillRow, reduced: REDUCED, _fail: fail,
  });

  post({ kori: "ready" });
})();
