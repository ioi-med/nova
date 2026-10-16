#!/usr/bin/env python3
"""Sonde de mise en page : détecte ce qui dépasse de la WebView.

Pour chaque page d'interface, place la page dans une iframe à sa taille réelle
puis mesure, côté navigateur :

* `scrollWidth`/`scrollHeight` du document (barres de défilement parasites) ;
* tout élément dont la boîte sort du cadre visible (texte coupé, image qui
  déborde, popover hors écran) ;
* les éléments dont le contenu est plus large que leur propre boîte
  (`scrollWidth > clientWidth`) sans `overflow:hidden` — texte qui se chevauche.

    python3 tools/ui_probe.py [dark|light]
"""
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ui_shot  # noqa: E402

PROBE = """
setTimeout(function(){
  var d = document.getElementById('f').contentDocument;
  var vw = d.documentElement.clientWidth, vh = d.documentElement.clientHeight;
  var out = ["cadre " + vw + "x" + vh
             + "  contenu " + d.documentElement.scrollWidth + "x"
             + d.documentElement.scrollHeight];
  if (d.documentElement.scrollWidth > vw + 1) out.push("!! defilement horizontal du document");
  if (d.documentElement.scrollHeight > vh + 1) out.push("(le document defile verticalement)");
  var docW = Math.max(d.documentElement.scrollWidth, vw);
  /* Un élément invisible (opacité 0, display:none, visibility:hidden) ou situé
     dans un tel conteneur n'est pas un défaut d'affichage : c'est le cas de la
     barre de progression, animée hors champ quand elle est masquée. */
  var invisible = function (el) {
    var n = el;
    while (n && n.nodeType === 1) {
      var st = d.defaultView.getComputedStyle(n);
      if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') return true;
      n = n.parentElement;
    }
    return false;
  };
  var defile = d.documentElement.scrollHeight > vh + 1;
  var all = d.querySelectorAll('*');
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (el.tagName === 'HTML' || el.tagName === 'BODY') continue;
    /* Halos décoratifs volontairement plus grands que la page. */
    if (typeof el.className === 'string' && el.className.indexOf('glow') !== -1) continue;
    if (invisible(el)) continue;
    var id = el.tagName.toLowerCase()
           + (el.id ? '#' + el.id : '')
           + (typeof el.className === 'string' && el.className
              ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
    var box = '[' + Math.round(r.left) + ',' + Math.round(r.top) + ','
            + Math.round(r.right) + ',' + Math.round(r.bottom) + ']';
    var debordeV = !defile && (r.bottom > vh + 1 || r.top < -1);
    if (r.right > docW + 1 || r.left < -1 || debordeV)
      out.push('!! hors cadre ' + id + ' ' + box);
    else {
      var st = d.defaultView.getComputedStyle(el);
      var tronque = st.textOverflow === 'ellipsis' || st.overflowX === 'hidden'
                 || st.overflowX === 'clip' || st.overflow === 'hidden';
      if (!tronque && el.scrollWidth > el.clientWidth + 2)
        out.push('!! contenu large ' + id + ' scroll=' + el.scrollWidth
                 + ' client=' + el.clientWidth);
    }
  }
  document.body.innerHTML = '<pre id="zzprobe">' + out.slice(0, 30).join('\\n') + '</pre>';
}, 600);
"""


def main():
    theme = sys.argv[1] if len(sys.argv) > 1 else "dark"
    ui_shot.CONFIG["theme"] = theme
    out_dir = ui_shot.OUT / "build"
    out_dir.mkdir(parents=True, exist_ok=True)
    problems = 0

    pages = [
        # (page, script exécuté après le rendu, libellé, options d'état)
        ("sidebar", "window.NovaUI.render(window.__NOVA__);"),
        ("sidebar", "window.__NOVA__.history_open=true;"
                    "window.NovaUI.render(window.__NOVA__);", "sidebar-historique"),
        ("sidebar", "window.NovaUI.render(window.__NOVA__);"
                    "document.getElementById('engineBtn').click();", "sidebar-moteurs"),
        ("sidebar", "window.NovaUI.render(window.__NOVA__);"
                    "document.getElementById('menuBtn').click();", "sidebar-menu"),
        ("sidebar", "window.NovaUI.render(window.__NOVA__);"
                    "const t=document.querySelector('.tab');"
                    "t.dispatchEvent(new MouseEvent('contextmenu',"
                    "{bubbles:true,clientX:60,clientY:120}));", "sidebar-menu-onglet"),
        ("sidebar", "window.NovaUI.render(window.__NOVA__);"
                    "const a=document.querySelector('.app');"
                    "a.dispatchEvent(new MouseEvent('contextmenu',"
                    "{bubbles:true,clientX:60,clientY:150}));", "sidebar-menu-app"),
        ("sidebar", "window.NovaUI.render(window.__NOVA__);", "sidebar-sans-favoris",
         {"favorites": []}),
        ("sidebar", "window.NovaUI.render(window.__NOVA__);", "sidebar-fond",
         {"ui_bg": "#2a2035"}),
        ("toolbar", "window.NovaUI.render(window.__NOVA__);"),
        ("toolbar", "window.NovaUI.render(window.__NOVA__);", "toolbar-favori",
         {"is_favorite": True}),
        ("toolbar", "window.NovaUI.render(window.__NOVA__);", "toolbar-fond",
         {"ui_bg": "#f7efe0"}),
        ("newtab", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
        ("newtab", "window.NovaPage && window.NovaPage.render(window.__NOVA__);",
         "newtab-sans-favoris", {"favorites": []}),
        ("newtab", "window.NovaPage && window.NovaPage.render(window.__NOVA__);",
         "newtab-fond", {"ui_bg": "#0f2a24"}),
        ("settings", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
        ("settings", "window.NovaPage && window.NovaPage.render(window.__NOVA__);",
         "settings-fond", {"ui_bg": "#3a2b2b"}),
        ("history", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
        ("import", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
        ("import", "window.NovaPage && window.NovaPage.render(window.__NOVA__);",
         "import-analysant", {"import_result": {}, "import_busy": True}),
        ("import", "window.NovaPage && window.NovaPage.render(window.__NOVA__);",
         "import-vide", {"import_sources": [], "import_result": None}),
        ("import", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"
                   "window.scrollTo(0, 99999);", "import-resultat-bas"),
        ("settings", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"
                     "window.scrollTo(0, 99999);", "settings-import"),
        ("settings", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"
                     "document.getElementById('openImport')"
                     ".scrollIntoView({block:'center'});", "settings-import-haut"),
        ("sidebar", "window.NovaUI.render(window.__NOVA__);", "sidebar-favoris-import",
         {"favorites": ui_shot.MANY_FAVORITES}),
        ("welcome", "window.NovaUI && 0;"),
    ]

    for item in pages:
        name, tail = item[0], item[1]
        label = item[2] if len(item) > 2 else name
        opts = item[3] if len(item) > 3 else {}
        w, h = ui_shot.SIZES[name]
        opts = {k: v for k, v in opts.items() if k != "theme"}
        inner = ui_shot.page(name, theme, tail, **opts)
        host = ui_shot.host(inner, w, h, theme)
        # insertion à la fin du document hôte (le `<body>` interne est dans srcdoc)
        cut = host.rfind("</body></html>")
        host = host[:cut] + f"<script>{PROBE}</script>\n" + host[cut:]
        path = out_dir / f"probe-{label}-{theme}.html"
        path.write_text(host, encoding="utf-8")

        dom = subprocess.run(
            [ui_shot.CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--allow-file-access-from-files", "--virtual-time-budget=4000",
             "--dump-dom", f"file://{path}"],
            capture_output=True, text=True, timeout=120).stdout
        start = dom.rfind('id="zzprobe"')
        report = dom[dom.find(">", start) + 1:dom.find("</pre>", start)] \
            if start != -1 else "(sonde non exécutée)"
        report = report.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        bad = [l for l in report.splitlines() if l.startswith("!!")]
        if bad:
            problems += len(bad)
        print(f"--- {label} ({theme})")
        for line in report.splitlines():
            print("    " + line)

    print(f"\n{problems} anomalie(s) de mise en page.")

    # --- contrôle du thème : « Système » doit être résolu par Rust ----------
    print("\nThème appliqué par page (état theme=system, dark=False -> clair) :")
    thorst = 0
    for name, tail in (("sidebar", "window.NovaUI.render(window.__NOVA__);"),
                       ("toolbar", "window.NovaUI.render(window.__NOVA__);"),
                       ("newtab", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
                       ("settings", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
                       ("history", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
                       ("import", "window.NovaPage && window.NovaPage.render(window.__NOVA__);"),
                       ("welcome", "window.NovaPage && window.NovaPage.render(window.__NOVA__);")):
        w, h = ui_shot.SIZES[name]
        inner = ui_shot.page(name, "light", tail, cfg_theme="system", dark=False)
        probe = """setTimeout(function(){
  var d = document.getElementById('f').contentDocument;
  var el = d.documentElement;
  var bg = d.defaultView.getComputedStyle(d.body).backgroundColor;
  document.body.innerHTML = '<pre id="zzprobe">' + el.dataset.theme + '|' + bg
    + '</pre>';
}, 500);"""
        host = ui_shot.host(inner, w, h, theme)
        cut = host.rfind("</body></html>")
        host = host[:cut] + f"<script>{probe}</script>\n" + host[cut:]
        path = out_dir / f"theme-{name}.html"
        path.write_text(host, encoding="utf-8")
        dom = subprocess.run(
            [ui_shot.CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--allow-file-access-from-files", "--virtual-time-budget=3000",
             "--dump-dom", f"file://{path}"],
            capture_output=True, text=True, timeout=120).stdout
        i = dom.rfind('id="zzprobe"')
        res = dom[dom.find(">", i) + 1:dom.find("</pre>", i)] if i != -1 else "?"
        themecol, _, bg = res.partition("|")
        clear = "sombre" if themecol == "dark" else "#f" in bg or "255" in bg
        marque = "OK " if themecol == "light" else "!! "
        if themecol != "light":
            thorst += 1
        print(f"    {marque}{name:9s} data-theme={themecol:5s} fond={bg}")
    print(f"\n{thorst} page(s) restée(s) sombre(s) alors que le système est clair.")
    return 1 if (problems or thorst) else 0


if __name__ == "__main__":
    sys.exit(main())
