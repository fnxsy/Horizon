"""Parse OPML feed list, test availability, and output Horizon-compatible JSON."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

OPML_URL = "https://raw.githubusercontent.com/RSS-Renaissance/awesome-AI-feeds/master/feedlist.opml"
TIMEOUT = 15.0

console = Console()


def parse_opml(text: str) -> list[dict]:
    """Extract all outline entries with title + xmlUrl from OPML.

    Uses regex fallback because OPML files often contain unescaped & characters.
    """
    import re

    feeds = []
    seen = set()
    # Match <outline ... xmlUrl="URL" ... /> and extract title + xmlUrl
    for m in re.finditer(
        r'<outline[^>]+title="([^"]*)"[^>]+xmlUrl="([^"]*)"', text
    ):
        title, url = m.group(1), m.group(2)
        if title and url and url not in seen:
            seen.add(url)
            feeds.append({"name": title.strip(), "url": url.strip()})
    return feeds


async def test_feed(client: httpx.AsyncClient, feed: dict) -> dict | None:
    """Try fetching a feed. Return feed dict with 'ok' key, or None on timeout."""
    try:
        resp = await client.get(feed["url"], follow_redirects=True, timeout=TIMEOUT)
        if resp.status_code == 200:
            feed["status"] = resp.status_code
            return feed
        feed["status"] = resp.status_code
        feed["error"] = f"HTTP {resp.status_code}"
        return feed
    except httpx.TimeoutException:
        return None  # skip timeouts silently
    except Exception as e:
        feed["status"] = 0
        feed["error"] = str(e)[:80]
        return feed


async def main():
    # 1. Fetch OPML
    console.print("[bold]📥 Fetching OPML...[/bold]")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(OPML_URL)
        resp.raise_for_status()
        feeds = parse_opml(resp.text)
    console.print(f"   Found [cyan]{len(feeds)}[/cyan] unique feeds in OPML\n")

    # 2. Test each feed
    console.print("[bold]🔍 Testing feeds (concurrency=10)...[/bold]")
    semaphore = asyncio.Semaphore(10)
    results = {"ok": [], "fail": [], "timeout": []}

    async def worker(feed: dict, progress_task):
        async with semaphore:
            result = await test_feed(client_progress, feed)
        if result is None:
            results["timeout"].append(feed)
        elif result.get("status") == 200:
            results["ok"].append(result)
        else:
            results["fail"].append(result)
        progress.advance(progress_task)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Testing", total=len(feeds))
            await asyncio.gather(*[worker(f, task) for f in feeds])

    # 3. Report
    console.print(f"\n   ✅ [green]{len(results['ok'])} OK[/green]  "
                  f"❌ [red]{len(results['fail'])} failed[/red]  "
                  f"⏱️  [yellow]{len(results['timeout'])} timed out[/yellow]\n")

    if results["fail"]:
        table = Table(title="Failed Feeds", show_lines=False)
        table.add_column("Name", style="dim")
        table.add_column("URL", style="dim")
        table.add_column("Error", style="red")
        for f in results["fail"][:15]:
            table.add_row(f["name"][:40], f["url"][:60], f.get("error", ""))
        console.print(table)
        if len(results["fail"]) > 15:
            console.print(f"   ... and {len(results['fail']) - 15} more\n")

    # 4. Generate Horizon JSON
    horizon_entries = []
    for f in results["ok"]:
        horizon_entries.append({
            "name": f["name"],
            "url": f["url"],
            "enabled": True,
            "category": "ai-feeds",
        })

    output = json.dumps(horizon_entries, indent=2, ensure_ascii=False)
    console.print(f"[bold]📋 Horizon-compatible JSON ({len(horizon_entries)} feeds):[/bold]\n")
    console.print(output)

    # Save to file
    out_path = Path(__file__).parent.parent / "data" / "ai_feeds_from_opml.json"
    out_path.write_text(output, encoding="utf-8")
    console.print(f"\n[dim]Saved to: {out_path}[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
