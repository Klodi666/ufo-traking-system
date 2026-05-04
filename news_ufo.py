#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════╗
║         UFO/UAP SIGNAL INTERCEPT v2.1        ║
║     [ CONTINUOUS FEED AGGREGATOR UNIT ]      ║
╚══════════════════════════════════════════════╝
"""

import feedparser
import argparse
import json
import time
import sys
import re
import random
import os
from datetime import datetime
from collections import defaultdict
from urllib.parse import quote

# ── Try optional deps, degrade gracefully ──────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.rule import Rule
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.columns import Columns
    from rich import box
    RICH = True
except ImportError:
    RICH = False

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

KEYWORDS = [
    "UFO", "UAP", "unidentified flying object", "unidentified aerial phenomenon",
    "alien craft", "orb sighting", "AARO", "extraterrestrial", "non-human intelligence",
    "Bob Lazar", "Skinwalker", "disclosure", "crash retrieval", "reverse engineering",
]

CATEGORIES = {
    "government": ["AARO", "congress", "senate", "pentagon", "disclosure", "classified", "legislation"],
    "sighting":   ["sighting", "witnessed", "spotted", "video", "footage", "photograph", "photo"],
    "science":    ["research", "study", "scientist", "analysis", "physicist", "data"],
    "military":   ["pilot", "navy", "air force", "military", "defense", "radar"],
}

RSS_URLS = {
    "Google/UFO":   "https://news.google.com/rss/search?q=UFO&hl=en-US&gl=US&ceid=US:en",
    "Google/UAP":   "https://news.google.com/rss/search?q=UAP+OR+%22unidentified+aerial+phenomenon%22&hl=en-US&gl=US&ceid=US:en",
    "Google/Disc":  "https://news.google.com/rss/search?q=UFO+disclosure&hl=en-US&gl=US&ceid=US:en",
    "Google/AARO":  "https://news.google.com/rss/search?q=AARO+UFO&hl=en-US&gl=US&ceid=US:en",
    "Google/Sight": "https://news.google.com/rss/search?q=UFO+sighting+2025&hl=en-US&gl=US&ceid=US:en",
}

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

console = Console(highlight=False) if RICH else None

BANNER = r"""
  ██╗   ██╗███████╗ ██████╗     ███████╗███████╗███████╗██████╗
  ██║   ██║██╔════╝██╔═══██╗    ██╔════╝██╔════╝██╔════╝██╔══██╗
  ██║   ██║█████╗  ██║   ██║    █████╗  █████╗  █████╗  ██║  ██║
  ██║   ██║██╔══╝  ██║   ██║    ██╔══╝  ██╔══╝  ██╔══╝  ██║  ██║
  ╚██████╔╝██║     ╚██████╔╝    ██║     ███████╗███████╗██████╔╝
   ╚═════╝ ╚═╝      ╚═════╝     ╚═╝     ╚══════╝╚══════╝╚═════╝
         [ SIGNAL INTERCEPT UNIT — CONTINUOUS FEED v2.1 ]
"""

def print_banner():
    if RICH:
        console.print(BANNER, style="bold green")
        console.print(
            Panel(
                "[green]Initialising feed interceptors… scanning encrypted channels…[/green]",
                border_style="green", box=box.DOUBLE
            )
        )
    else:
        print(BANNER)


def glitch(text: str) -> str:
    """Return Rich markup with random green-shade glitch effect."""
    shades = ["bright_green", "green", "dark_green", "bold green"]
    return f"[{random.choice(shades)}]{text}[/]"


def categorise(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for cat, words in CATEGORIES.items():
        if any(w.lower() in text for w in words):
            return cat
    return "other"


def is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(k.lower() in text for k in KEYWORDS)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_date(published: str) -> datetime:
    if not published or published == "Unknown":
        return datetime.min
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            return datetime.strptime(published, fmt)
        except ValueError:
            continue
    return datetime.min


def highlight_keywords(text: str) -> str:
    """Wrap matched keywords with Rich markup."""
    for kw in sorted(KEYWORDS, key=len, reverse=True):
        pattern = re.compile(re.escape(kw), re.IGNORECASE)
        text = pattern.sub(f"[bold yellow]{kw}[/bold yellow]", text)
    return text

# ─────────────────────────────────────────────────────────────────────────────
#  CORE FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch_news(filter_kw: str | None = None, limit: int = 50) -> list[dict]:
    articles = []
    seen_titles: set[str] = set()

    if RICH:
        with Progress(
            SpinnerColumn(spinner_name="dots", style="green"),
            TextColumn("[green]{task.description}"),
            BarColumn(bar_width=30, style="green", complete_style="bright_green"),
            console=console,
            transient=True,
        ) as prog:
            task = prog.add_task("Intercepting feeds…", total=len(RSS_URLS))
            for source, url in RSS_URLS.items():
                prog.update(task, description=f"[green]Tapping [cyan]{source}[/cyan]…")
                _parse_feed(url, source, articles, seen_titles, filter_kw)
                prog.advance(task)
                time.sleep(0.3)
    else:
        for source, url in RSS_URLS.items():
            print(f"  >> Fetching {source} …")
            _parse_feed(url, source, articles, seen_titles, filter_kw)

    articles.sort(key=lambda a: a["_date"], reverse=True)
    return articles[:limit]


def _parse_feed(url, source, articles, seen_titles, filter_kw):
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title   = strip_html(entry.get("title", ""))
            summary = strip_html(entry.get("summary", ""))
            link    = entry.get("link", "")
            pub     = entry.get("published", "Unknown")

            norm = title.lower().strip()
            if norm in seen_titles:
                continue
            seen_titles.add(norm)

            if not is_relevant(title, summary):
                continue

            if filter_kw:
                combined = (title + summary).lower()
                if filter_kw.lower() not in combined:
                    continue

            articles.append({
                "title":     title,
                "summary":   summary[:300] + ("…" if len(summary) > 300 else ""),
                "link":      link,
                "published": pub,
                "source":    source,
                "category":  categorise(title, summary),
                "_date":     parse_date(pub),
            })
    except Exception as exc:
        if RICH:
            console.print(f"  [red]✗ Feed error [{source}]: {exc}[/red]")
        else:
            print(f"  !! Feed error [{source}]: {exc}")

# ─────────────────────────────────────────────────────────────────────────────
#  DISPLAY
# ─────────────────────────────────────────────────────────────────────────────

CAT_COLOUR = {
    "government": "cyan",
    "sighting":   "bright_yellow",
    "science":    "bright_blue",
    "military":   "red",
    "other":      "white",
}

def display_news(articles: list[dict], show_summary: bool = False, show_header: bool = True):
    if not RICH:
        _display_plain(articles)
        return

    if show_header:
        console.print()
        console.rule("[bold green]// INTERCEPTED TRANSMISSIONS //[/bold green]", style="green")
        console.print()

    for i, a in enumerate(articles, 1):
        cat   = a["category"]
        col   = CAT_COLOUR.get(cat, "white")
        dtag  = f"[dim]{a['_date'].strftime('%Y-%m-%d %H:%M') if a['_date'] != datetime.min else a['published']}[/dim]"
        stag  = f"[dim green]src:[/dim green][cyan]{a['source']}[/cyan]"
        ctag  = f"[{col}]▸ {cat.upper()}[/{col}]"

        title_hl = highlight_keywords(a["title"])

        body = f"[bold bright_green]{i:02d}.[/bold bright_green]  {title_hl}\n"
        body += f"     {dtag}   {stag}   {ctag}\n"
        if show_summary and a["summary"]:
            body += f"\n     [dim]{a['summary']}[/dim]\n"
        body += f"\n     [green underline]{a['link']}[/green underline]"

        console.print(
            Panel(body, border_style="dim green", box=box.SIMPLE_HEAVY, padding=(0, 1))
        )

    # Stats bar
    cats = defaultdict(int)
    for a in articles:
        cats[a["category"]] += 1

    if show_header:
        console.print()
        console.rule("[bold green]// SIGNAL STATS //[/bold green]", style="green")

        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold green",
                    border_style="dim green")
        tbl.add_column("CATEGORY",  style="cyan",         width=14)
        tbl.add_column("COUNT",     style="bright_green",  justify="center", width=8)
        tbl.add_column("BAR",       style="green",         width=30)

        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            bar = "█" * count + "░" * max(0, 10 - count)
            tbl.add_row(cat.upper(), str(count), bar)

        console.print(tbl)
        console.print(
            f"  [dim]Total signals intercepted:[/dim] [bold bright_green]{len(articles)}[/bold bright_green]"
            f"   [dim]Last scan:[/dim] [green]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/green]"
        )
        console.print()


def _display_plain(articles):
    print("\n" + "=" * 60)
    print(" UFO / UAP SIGNAL INTERCEPT — CLASSIFIED FEED")
    print("=" * 60)
    for i, a in enumerate(articles, 1):
        print(f"\n[{i:02d}] {a['title']}")
        print(f"  Date  : {a['published']}")
        print(f"  Source: {a['source']}")
        print(f"  Cat   : {a['category'].upper()}")
        print(f"  Link  : {a['link']}")
    print("\n" + "=" * 60)
    print(f"Total: {len(articles)}  |  Scanned: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_json(articles: list[dict], path: str):
    clean = [{k: v for k, v in a.items() if k != "_date"} for a in articles]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    _log_ok(f"JSON exported → {path}")


def export_html(articles: list[dict], path: str):
    rows = ""
    for a in articles:
        cat_col = {"government":"#0ff","sighting":"#ff0","science":"#0af","military":"#f44","other":"#aaa"}.get(a["category"],"#aaa")
        date_str = a['_date'].strftime('%Y-%m-%d') if a['_date'] != datetime.min else '?'
        rows += f"""
        <tr>
          <td style="color:#0f0">{date_str}</td>
          <td><a href="{a['link']}" target="_blank">{a['title']}</a></td>
          <td style="color:{cat_col}">{a['category'].upper()}</td>
          <td style="color:#0af">{a['source']}</td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UFO FEED — CLASSIFIED</title>
<style>
  body  {{ background:#000; color:#0f0; font-family:'Courier New',monospace; padding:2rem; }}
  h1    {{ color:#0f0; text-shadow:0 0 10px #0f0; letter-spacing:.3em; }}
  table {{ border-collapse:collapse; width:100%; }}
  th    {{ background:#0a0; color:#000; padding:.5rem 1rem; text-align:left; }}
  td    {{ padding:.4rem 1rem; border-bottom:1px solid #020; }}
  tr:hover {{ background:#011; }}
  a     {{ color:#0f0; text-decoration:none; }}
  a:hover {{ text-shadow:0 0 6px #0f0; }}
</style>
</head>
<body>
<h1>// UFO / UAP SIGNAL INTERCEPT //</h1>
<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — {len(articles)} transmissions intercepted</p>
<table>
<tr><th>DATE</th><th>TITLE</th><th>CATEGORY</th><th>SOURCE</th></tr>
{rows}
</table>
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    _log_ok(f"HTML exported → {path}")


def export_txt(articles: list[dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(BANNER + "\n")
        f.write(f"Generated: {datetime.now()}\n{'='*70}\n\n")
        for i, a in enumerate(articles, 1):
            f.write(f"[{i:02d}] {a['title']}\n")
            f.write(f"  Date     : {a['published']}\n")
            f.write(f"  Category : {a['category'].upper()}\n")
            f.write(f"  Source   : {a['source']}\n")
            f.write(f"  Link     : {a['link']}\n\n")
    _log_ok(f"TXT exported → {path}")


def _log_ok(msg):
    if RICH:
        console.print(f"  [bold green]✔[/bold green] [green]{msg}[/green]")
    else:
        print(f"  ✔ {msg}")

# ─────────────────────────────────────────────────────────────────────────────
#  INTERACTIVE MENU (no-args mode)
# ─────────────────────────────────────────────────────────────────────────────

def interactive_menu(articles: list[dict]):
    if not RICH:
        print("Interactive menu requires 'rich' module. Install with: pip install rich")
        return

    console.print("\n[bold green]// COMMAND INTERFACE //" )
    console.print("[dim]  [S] Show summaries    [J] Export JSON")
    console.print("  [H] Export HTML       [T] Export TXT")
    console.print("  [F] Filter keyword    [Q] Quit[/dim]\n")

    while True:
        try:
            cmd = console.input("[green]>[/green] ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd == "Q":
            console.print("[green]// SIGNAL TERMINATED — STAY VIGILANT //[/green]")
            break
        elif cmd == "S":
            display_news(articles, show_summary=True)
        elif cmd == "J":
            export_json(articles, "ufo_feed.json")
        elif cmd == "H":
            export_html(articles, "ufo_feed.html")
        elif cmd == "T":
            export_txt(articles, "ufo_feed.txt")
        elif cmd == "F":
            kw = console.input("[green]filter keyword >[/green] ").strip()
            filtered = [a for a in articles if kw.lower() in (a["title"]+a["summary"]).lower()]
            console.print(f"[green]{len(filtered)} matches for '{kw}'[/green]")
            display_news(filtered)
        else:
            console.print("[dim red]  unknown command[/dim red]")

# ─────────────────────────────────────────────────────────────────────────────
#  CONTINUOUS LIVE MODE
# ─────────────────────────────────────────────────────────────────────────────

def clear_screen():
    """Clear terminal screen cross‑platform."""
    os.system('cls' if os.name == 'nt' else 'clear')

def live_mode(args):
    """Continuously fetch and display news every `interval` seconds."""
    interval = args.interval
    show_summary = args.summary
    limit = args.limit
    filter_kw = args.filter

    if not RICH:
        print("Live mode works best with 'rich' installed. Install: pip install rich")
        print("Starting plain live mode (no automatic refresh – use Ctrl+C to stop).")

    try:
        iteration = 1
        while True:
            # Clear screen before each refresh
            clear_screen()

            # Print banner and mode info
            if RICH:
                console.print(BANNER, style="bold green")
                console.print(f"[dim]Live mode — refreshing every {interval} seconds (Ctrl+C to stop)[/dim]\n")
            else:
                print(BANNER)
                print(f"Live mode — refreshing every {interval} seconds (Ctrl+C to stop)\n")

            # Fetch articles
            articles = fetch_news(filter_kw=filter_kw, limit=limit)

            if not articles:
                msg = "No relevant articles found. Check network or filters."
                if RICH:
                    console.print(f"[red]{msg}[/red]")
                else:
                    print(msg)
            else:
                # Display (without the global header/stats rule – we already printed banner)
                if RICH:
                    # Use display_news but prevent extra top rule and stats (we add stats manually)
                    # Simpler: call display_news with show_header=False and then print stats ourselves
                    display_news(articles, show_summary=show_summary, show_header=False)
                    # Print cycle stats
                    console.rule("[bold green]// LIVE CYCLE //[/bold green]", style="green")
                    console.print(f"  [dim]Cycle:[/dim] [green]#{iteration}[/green]   [dim]Next refresh in[/dim] [green]{interval}[/green] [dim]seconds[/dim]")
                    console.print(f"  [dim]Press Ctrl+C to exit live mode[/dim]")
                    console.print()
                else:
                    _display_plain(articles)
                    print(f"\n--- Cycle #{iteration} | Next refresh in {interval} seconds (Ctrl+C to stop) ---")

            # Wait for next cycle
            for remaining in range(interval, 0, -1):
                sys.stdout.write(f"\rNext refresh in {remaining} seconds... ")
                sys.stdout.flush()
                time.sleep(1)
            print()  # newline after countdown
            iteration += 1

    except KeyboardInterrupt:
        if RICH:
            console.print("\n[bold red]// LIVE MODE TERMINATED //[/bold red]")
        else:
            print("\nLive mode stopped by user.")
        sys.exit(0)

# ─────────────────────────────────────────────────────────────────────────────
#  CLI ARGUMENT PARSING
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="UFO/UAP hacker-style news aggregator with continuous live mode",
        formatter_class=argparse.RawTextHelpFormatter
    )
    p.add_argument("--filter", "-f", type=str, help="Extra keyword filter (title+summary)")
    p.add_argument("--limit", "-l", type=int, default=50, help="Max articles to show (default: 50)")
    p.add_argument("--summary", "-s", action="store_true", help="Show article summaries")
    p.add_argument("--json", dest="json_out", type=str, metavar="FILE", help="Export to JSON")
    p.add_argument("--html", dest="html_out", type=str, metavar="FILE", help="Export to HTML")
    p.add_argument("--txt", dest="txt_out", type=str, metavar="FILE", help="Export to TXT")
    p.add_argument("--quiet", "-q", action="store_true", help="Suppress console output (only exports)")
    p.add_argument("--interactive", "-i", action="store_true", help="Interactive menu after fetch")
    p.add_argument("--live", "--watch", action="store_true", help="Continuous live mode (auto-refresh)")
    p.add_argument("--interval", type=int, default=60, help="Refresh interval in seconds (default: 60, used with --live)")
    p.add_argument("--version", "-v", action="version", version="UFO Signal Intercept v2.1")
    return p

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not RICH and not args.quiet:
        print("[!] 'rich' not installed – using plain text output. Install with: pip install rich")

    # Live mode takes precedence
    if args.live:
        if args.interactive:
            print("Error: --live and --interactive cannot be used together.")
            sys.exit(1)
        if args.json_out or args.html_out or args.txt_out:
            print("Warning: Exports are ignored in live mode. Use standard mode for exports.")
        live_mode(args)
        return

    # Normal / interactive / export mode
    if not args.quiet:
        print_banner()

    articles = fetch_news(filter_kw=args.filter, limit=args.limit)

    if not articles:
        msg = "No relevant articles found. Try a different filter or check network."
        if RICH and not args.quiet:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)
        sys.exit(0)

    # Handle exports
    if args.json_out:
        export_json(articles, args.json_out)
    if args.html_out:
        export_html(articles, args.html_out)
    if args.txt_out:
        export_txt(articles, args.txt_out)

    # Interactive or normal display
    if args.interactive:
        if not args.quiet:
            interactive_menu(articles)
        else:
            print("Interactive mode not available with --quiet")
    elif not args.quiet:
        display_news(articles, show_summary=args.summary)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Fatal error: {e}")
        sys.exit(1)