#!/usr/bin/env python3
"""Assemble knowledge/index.json from Notion ingestion results.

The agent (see .claude/skills/sync-notion) walks the Notion tree and records what
it read here. Anything not actually read is marked ingested=false: the grounding
gate refuses to cite a section that has no ingested content, so a stub can never
back a quiz answer.

    .venv/bin/python scripts/build_index.py
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = "https://app.notion.com/p/"

def sec(heading, tags, services=(), note=None):
    d = {"heading": heading, "exam_tags": list(tags), "services": list(services)}
    if note:
        d["note"] = note
    return d

COURSES = [
    {
        "title": "Google Cloud Fundamentals: Core Infrastructure",
        "url": N + "REDACTED-NOTION-PAGE-ID",
        "transcript": {
            "url": N + "REDACTED-NOTION-PAGE-ID",
            "ingested": True,
            "note": "Single page. H1 = module, H2 = section, timestamped.",
            "modules": {
                "Introducing Google Cloud": [
                    "Cloud Computing Overview", "Iaas & Paas", "The Google Cloud Network",
                    "Environmental impact", "Security", "OpenSource Eco-system",
                    "Pricing & Billing", "Section Quiz"],
                "Resources and Access in the Cloud": [
                    "Google Cloud resource hierarchy", "Identity and Access Management (IAM)",
                    "Service accounts", "Cloud Identity", "Interacting with Google Cloud",
                    "Section Quiz"],
                "Virtual Machines and Networks in the Cloud": [
                    "Virtual Private Cloud networking", "Compute Engine",
                    "Scaling virtual machines", "Important VPC compatibilities",
                    "Cloud Load Balancing", "Cloud DNS and Cloud CDN",
                    "Connecting networks to Google VPC", "Section Quiz"],
                "Storage in the Cloud": [
                    "Google Cloud storage options", "Cloud Storage",
                    "Cloud Storage: Storage classes and data transfer", "Cloud SQL",
                    "Spanner", "Firestore", "Bigtable", "Comparing storage options",
                    "Section Quiz"],
                "Containers in the Cloud": [
                    "Introduction to containers", "Kubernetes", "Google Kubernetes Engine",
                    "Section Quiz"],
                "Applications in the Cloud": [
                    "Cloud Run", "Development in the cloud", "Section Quiz"],
                "Prompt Engineering": ["Prompt Engineering", "Section Quiz"],
            },
        },
        "material": {
            "url": N + "REDACTED-NOTION-PAGE-ID",
            "pages": [
                {"title": "Module 1: Introducing Google Cloud",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": True,
                 "quiz_questions": 3,
                 "sections": [
                     sec("01 — An overview of cloud computing", []),
                     sec("02 — IaaS and PaaS", [], ["Compute Engine", "App Engine", "Cloud Run"]),
                     sec("03 — The Google Cloud network", [], ["regions", "zones"]),
                     sec("04 — Environmental impact", []),
                     sec("05 — Security", ["5.1"],
                         ["Google Front End", "encryption at rest", "U2F"],
                         "Infrastructure security layers; supports shared-responsibility questions."),
                     sec("06 — Open APIs and open source", []),
                     sec("07 — Pricing and billing", [], ["Budgets", "Quotas"]),
                 ]},
                {"title": "Module 2: Resources and Access in the Cloud",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": True,
                 "quiz_questions": 3,
                 "sections": [
                     sec("01 — Google Cloud resource hierarchy", ["1.5"],
                         ["Resource Manager", "folders", "projects", "organization node"]),
                     sec("02 — Identity and Access Management (IAM)", ["1.4"],
                         ["IAM", "deny policies", "policy inheritance"]),
                     sec("03 — IAM roles", ["1.4"],
                         ["basic roles", "predefined roles", "custom roles"]),
                     sec("04 — Service accounts", ["1.2"], ["service accounts"]),
                     sec("05 — Cloud Identity", ["1.1"],
                         ["Cloud Identity", "Google Admin console", "Active Directory", "LDAP"]),
                     sec("06 — Interacting with Google Cloud", [],
                         ["Cloud console", "gcloud", "Cloud Shell", "APIs"]),
                 ]},
                {"title": "Module 3: Virtual Machines and Networks in the Cloud",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": True,
                 "quiz_questions": 5,
                 "sections": [
                     sec("01 — Virtual private cloud networking", ["2.2"],
                         ["VPC", "subnets"],
                         "States VPC is global and subnets regional — a top AWS trap."),
                     sec("02 — Compute Engine", [], ["Compute Engine", "Spot VMs"]),
                     sec("03 — Scaling virtual machines", [], ["autoscaling"]),
                     sec("04 — Important VPC compatibilities", ["2.2", "2.3"],
                         ["firewall rules", "network tags", "VPC Peering", "Shared VPC", "routing tables"],
                         "GAP: teaches firewall targets via network tags only. Official sample Q6 "
                         "keys on service-account targets, which this material does not cover."),
                     sec("05 — Cloud Load Balancing", ["2.1"],
                         ["Cloud Load Balancing", "Application Load Balancer", "Network Load Balancer"]),
                     sec("06 — Cloud DNS", ["2.1"], ["Cloud DNS"]),
                     sec("07 — Cloud CDN", [], ["Cloud CDN"]),
                     sec("08 — Connecting Networks to Google VPC", ["2.3"],
                         ["Cloud VPN", "Cloud Router", "Dedicated Interconnect",
                          "Partner Interconnect", "Direct Peering", "Carrier Peering"]),
                 ]},
                {"title": "Module 4: Storage in the Cloud",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": False,
                 "sections": []},
                {"title": "Module 5: Containers in the Cloud",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": False,
                 "sections": []},
                {"title": "Module 6: Applications in the Cloud",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": False,
                 "sections": []},
                {"title": "Module 7: Prompt Engineering",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": False,
                 "sections": []},
                {"title": "Course Summary",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": False,
                 "sections": []},
            ],
        },
    },
    {
        "title": "Introduction to Security in the World of AI",
        "url": N + "REDACTED-NOTION-PAGE-ID",
        "transcript": {"url": N + "REDACTED-NOTION-PAGE-ID",
                       "ingested": False, "modules": {}},
        "material": {
            "url": N + "REDACTED-NOTION-PAGE-ID",
            "pages": [
                {"title": "Introduction to Security in the World of AI — Review",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": True,
                 "sections": [
                     sec("Three primary ways to engage with AI", ["3.3"]),
                     sec("How AI models work", ["3.3"]),
                     sec("Three forms of AI security", ["3.3"]),
                     sec("Components of a secure AI system", ["3.3"],
                         ["application", "model", "data", "infrastructure"]),
                     sec("Google's Secure AI Framework (SAIF)", ["3.3"], ["SAIF"]),
                 ]},
                {"title": "Google Secure AI Framework (SAIF) — Approach Notes",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": True,
                 "sections": [
                     sec("What SAIF is", ["3.3"], ["SAIF"]),
                     sec("Putting SAIF into practice — four steps", ["3.3"]),
                     sec("The six core elements", ["3.3"],
                         ["red teaming", "data governance", "model risk management"]),
                     sec("Takeaways", ["3.3"]),
                 ]},
                {"title": "Secure AI Framework (SAIF)",
                 "url": N + "REDACTED-NOTION-PAGE-ID", "ingested": False,
                 "sections": []},
            ],
        },
    },
]


def main() -> int:
    doc = {
        "_generated": datetime.date.today().isoformat(),
        "_root": {
            "title": "Professional Cloud Security Engineer",
            "url": N + "REDACTED-NOTION-PAGE-ID",
        },
        "_note": "Sections with ingested=false are known to exist but have not been read. "
                 "The grounding gate refuses to cite them.",
        "courses": COURSES,
    }
    out = ROOT / "knowledge/index.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n")

    pages = [p for c in COURSES for p in c["material"]["pages"]]
    done = [p for p in pages if p["ingested"]]
    secs = [s for p in done for s in p["sections"]]
    tagged = [s for s in secs if s["exam_tags"]]
    print(f"courses          : {len(COURSES)}")
    print(f"material pages   : {len(done)}/{len(pages)} ingested")
    print(f"sections         : {len(secs)} ({len(tagged)} mapped to blueprint)")
    print(f"blueprint tags   : {sorted({t for s in tagged for t in s['exam_tags']})}")
    print(f"gap notes        : {sum('GAP' in (s.get('note') or '') for s in secs)}")
    print(f"-> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
