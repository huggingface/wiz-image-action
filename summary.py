#!/usr/bin/env python3
"""Render a Wiz scan report as the run's step summary.

A run page that says "failed a Wiz policy" and nothing else sends the reader to the Wiz
portal to find out what. The counts, the digest and the report link belong on the page
that already has their attention.

    summary.py <report.json> <image> <verdict>
"""

import json
import sys

report, image, verdict = sys.argv[1], sys.argv[2], sys.argv[3]
scan = json.load(open(report))

print(f"## {'✅' if verdict == 'passed' else '❌'} Wiz scan — `{image}`\n")

digest = (scan.get("scanOriginResource") or {}).get("digest", "")
if digest:
    print(f"`{digest}`\n")

counts = (scan.get("result") or {}).get("analytics") or {}
vulnerabilities = counts.get("vulnerabilities") or {}
rows = [
    (name, found)
    for name, found in (
        ("Vulnerabilities", vulnerabilities),
        ("Secrets", counts.get("secrets") or {}),
        ("Malware", counts.get("malware") or {}),
    )
    if found.get("totalCount")
]

if rows:
    print("| | Critical | High | Medium | Low | Total |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for name, found in rows:
        print(
            f"| {name} | {found.get('criticalCount', 0)} | {found.get('highCount', 0)} "
            f"| {found.get('mediumCount', 0)} | {found.get('lowCount', 0)} "
            f"| {found.get('totalCount', 0)} |"
        )
    # The difference between "upgrade the base" and "wait for upstream".
    unfixed = vulnerabilities.get("unfixedCount")
    if unfixed:
        print(f"\n{unfixed} of the vulnerabilities have no fix available.")
else:
    print("No vulnerabilities, secrets or malware found.")

# Which policies were applied is the one thing the exit code cannot say.
applied = [p["name"] for p in (scan.get("policies") or []) if p.get("name")]
if applied:
    print(f"\nPolicies applied: {', '.join(applied)}")

url = scan.get("reportUrl")
if url:
    print(f"\n[Full report in Wiz]({url})")
