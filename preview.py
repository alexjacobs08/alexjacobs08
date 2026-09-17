#!/usr/bin/env python3
"""
Render README.md exactly as GitHub will, locally.

Uses GitHub's own /markdown endpoint via the authenticated `gh` CLI, so what you see
is the real renderer — not a lookalike. Sanitisation, table handling and the HTML
subset all behave as they will on the profile.

  python3 preview.py            # render + open in browser
  python3 preview.py --watch    # re-render on every save
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "README.md"
DST = ROOT / "preview.html"

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>alexjacobs08 — profile preview</title>
<link rel="stylesheet" href="assets/gh-light.css" id="css-light">
<link rel="stylesheet" href="assets/gh-dark.css" id="css-dark" disabled>
<style>
  /* Measured from a live github.com profile at a 1280 viewport: the page splits into
     a 296px sidebar and an 896px main column, and the README Box sits in that main
     column with 32px of padding. Previewing at the 1012px repo-page width made the
     layout look roomier than it will actually be. */
  :root {{ --main: 896px; --pad: 32px; --line: #d1d9e0; --bar: #f6f8fa; --ink: #59636e; }}
  body.dark {{ --line: #3d444d; --bar: #151b23; --ink: #9198a1; }}

  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #fff; color: #1f2328;
          font: 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  body.dark {{ background: #0d1117; color: #e6edf3; }}

  header {{ position: sticky; top: 0; z-index: 9; display: flex; align-items: center;
            gap: 16px; padding: 0 20px; height: 48px;
            background: var(--bar); border-bottom: 1px solid var(--line); }}
  header .who {{ font-weight: 600; }}
  header .meta {{ color: var(--ink); font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }}
  header .spacer {{ margin-left: auto; }}
  .seg {{ display: flex; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }}
  .seg button {{ border: 0; padding: 5px 12px; cursor: pointer; font: inherit; font-size: 12px;
                 background: transparent; color: var(--ink); }}
  .seg button + button {{ border-left: 1px solid var(--line); }}
  .seg button:hover {{ background: #8881; }}
  .seg button[aria-pressed="true"] {{ background: #8882; color: inherit; font-weight: 600; }}

  /* the profile page: sidebar rail + main column, so the README sits at its real width */
  .page {{ display: flex; gap: 24px; max-width: 1248px; margin: 0 auto; padding: 24px 16px 96px; }}
  .rail {{ flex: 0 0 296px; }}
  .rail .ghost {{ border: 1px dashed var(--line); border-radius: 6px; height: 296px;
                  display: flex; align-items: center; justify-content: center;
                  color: var(--ink); font-size: 12px; text-align: center; padding: 16px; }}
  .main {{ flex: 1 1 var(--main); min-width: 0; max-width: var(--main); }}
  .markdown-body {{ padding: var(--pad); border: 1px solid var(--line); border-radius: 6px; }}
  @media (max-width: 1100px) {{ .rail {{ display: none; }} .page {{ max-width: var(--main); }} }}
</style>
<header>
  <span class="who">alexjacobs08/README.md</span>
  <span class="meta">896px column &middot; rendered {stamp}</span>
  <span class="spacer"></span>
  <div class="seg">
    <button onclick="t('light')" data-th="light">Light</button>
    <button onclick="t('dark')" data-th="dark">Dark</button>
    <button onclick="t(null)" data-th="">System</button>
  </div>
</header>
<div class="page">
  <div class="rail"><div class="ghost">avatar &amp; bio<br>(GitHub renders this column)</div></div>
  <div class="main"><article class="markdown-body">{body}</article></div>
</div>
<script>
  // The combined github-markdown-css puts its dark variables inside
  // @media (prefers-color-scheme: dark), so a [data-theme] toggle is inert unless the
  // OS is already dark. Swap whole stylesheets instead.
  function t(v) {{
    const sys = matchMedia('(prefers-color-scheme: dark)').matches;
    const dark = v ? v === 'dark' : sys;
    document.getElementById('css-dark').disabled = !dark;
    document.getElementById('css-light').disabled = dark;
    document.body.classList.toggle('dark', dark);
    if (v) localStorage.setItem('th', v); else localStorage.removeItem('th');
    for (const b of document.querySelectorAll('.seg button'))
      b.setAttribute('aria-pressed', b.dataset.th === (v || ''));
  }}
  t(localStorage.getItem('th'));
  matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => t(localStorage.getItem('th')));
  // reload when the rendered file changes on disk
  let seen = "{stamp}";
  setInterval(async () => {{
    try {{
      const r = await fetch(location.href, {{ cache: 'no-store' }});
      const m = (await r.text()).match(/class="stamp">([^<]+)/);
      if (m && m[1] !== seen) location.reload();
    }} catch (e) {{}}
  }}, 1000);
</script>
"""


def render(md: str) -> str:
    """GitHub's own GFM renderer, in the context of the profile repo."""
    payload = json.dumps({
        "text": md,
        "mode": "gfm",
        "context": "alexjacobs08/alexjacobs08",
    })
    p = subprocess.run(
        ["gh", "api", "--method", "POST", "/markdown", "--input", "-"],
        input=payload, capture_output=True, text=True,
    )
    if p.returncode:
        sys.exit(f"gh api failed:\n{p.stderr.strip()}\n\nIs `gh auth status` healthy?")
    return p.stdout


def build():
    md = SRC.read_text()
    html = render(md)
    stamp = time.strftime("%H:%M:%S")
    DST.write_text(PAGE.format(body=html, stamp=stamp))
    return stamp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    stamp = build()
    print(f"[{stamp}] -> {DST.relative_to(ROOT)}")
    if not a.no_open:
        subprocess.run(["open", str(DST)])

    if a.watch:
        print("watching README.md — ctrl-c to stop")
        last = hashlib.md5(SRC.read_bytes()).hexdigest()
        while True:
            time.sleep(0.5)
            cur = hashlib.md5(SRC.read_bytes()).hexdigest()
            if cur != last:
                last = cur
                print(f"[{build()}] rebuilt")


if __name__ == "__main__":
    main()
