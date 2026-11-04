"""Write one free-source report to reports/free-scan/latest.json and print a short summary."""

import json
from pathlib import Path

import httpx

from scanner.free_scan.scan import USER_AGENT, run_free_scan


def main() -> None:
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
        report = run_free_scan(client)
    path = Path("reports/free-scan/latest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["generated_at"])
    print(report["disclaimer"])
    print(f"Abos verwendet: {report['subscriptions_used'] or 'keine'}")
    for source in report["sources"]:
        print(f"{source['status']:12} {source['title']:32} {len(source['hits'])} Zeilen")
    if report["overlap"]:
        print("Mehrfach:")
        for item in report["overlap"]:
            print(f"  {item['label']}: {', '.join(item['sources'])}")
    else:
        print("Mehrfach: keine")
    print(path)


if __name__ == "__main__":
    main()
