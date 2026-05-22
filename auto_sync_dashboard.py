#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

import update_dashboard as ud

SCOPUS_AUTHOR_ID_DEFAULT = "55877289000"
ORCID_ID_DEFAULT = "0000-0002-4978-1499"
USER_AGENT_DEFAULT = "sgc-dashboard-updater/1.0"
TIMEOUT = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync dashboard data from Scopus and OpenAlex")
    parser.add_argument("--data", default="dashboard_data.json", help="Path to dashboard_data.json")
    parser.add_argument("--out-js", default="dashboard_data.js", help="Path to dashboard_data.js")
    parser.add_argument("--author-id", default=None, help="Override Scopus Author ID")
    parser.add_argument("--orcid", default=None, help="Override ORCID")
    parser.add_argument("--skip-scopus", action="store_true", help="Skip Scopus sync")
    parser.add_argument("--skip-openalex", action="store_true", help="Skip OpenAlex sync")
    parser.add_argument("--git-push", action="store_true", help="Commit and push changed files to the current git repo")
    parser.add_argument("--git-branch", default=None, help="Branch name for git push")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args()


def log(msg: str, verbose: bool = True) -> None:
    if verbose:
        print(msg)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Eksik ortam değişkeni: {name}")
    return value


def http_get_json(url: str, *, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def normalize_oa_scopus(entry: Dict[str, Any]) -> str:
    for key in ("openaccess", "openaccessFlag", "openaccessflag"):
        if key in entry:
            value = str(entry.get(key, "")).strip().lower()
            return "Open Access" if value in {"1", "true", "yes"} else "No"
    return "No"


def scopus_entry_to_record(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = (entry.get("dc:title") or entry.get("dc:description") or "").strip()
    if not title:
        return None

    year = 0
    cover_date = (entry.get("prism:coverDate") or "").strip()
    if len(cover_date) >= 4 and cover_date[:4].isdigit():
        year = int(cover_date[:4])
    elif str(entry.get("prism:coverDisplayDate", ""))[:4].isdigit():
        year = int(str(entry.get("prism:coverDisplayDate"))[:4])

    doi = (entry.get("prism:doi") or "").strip()
    link = (entry.get("prism:url") or "").strip()
    if not link and doi:
        link = f"https://doi.org/{doi}"

    subtype = (entry.get("subtypeDescription") or entry.get("subtype") or entry.get("aggregationType") or "Article").strip()
    doc_type = ud.normalize_document_type(subtype)

    cited_by = ud.parse_int(entry.get("citedby-count"), 0)

    return {
        "Title": title,
        "Year": year,
        "Journal": (entry.get("prism:publicationName") or entry.get("prism:aggregationType") or "Unknown").strip(),
        "Citations": cited_by,
        "DocumentType": doc_type,
        "OpenAccess": normalize_oa_scopus(entry),
        "DOI": doi,
        "Link": link,
    }


def fetch_scopus_records(api_key: str, author_id: str, verbose: bool) -> List[Dict[str, Any]]:
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": api_key,
        "User-Agent": os.getenv("USER_AGENT", USER_AGENT_DEFAULT),
    }
    url = "https://api.elsevier.com/content/search/scopus"
    start = 0
    count = 25
    total = None
    records: List[Dict[str, Any]] = []

    while True:
        params = {
            "query": f"authid({author_id})",
            "start": start,
            "count": count,
            "view": "COMPLETE",
        }
        payload = http_get_json(url, headers=headers, params=params)
        block = payload.get("search-results", {})
        entries = block.get("entry", []) or []
        if isinstance(entries, dict):
            entries = [entries]

        if total is None:
            total = ud.parse_int(block.get("opensearch:totalResults"), 0)
            log(f"Scopus kayıtları çekiliyor: toplam {total}", verbose)

        for entry in entries:
            record = scopus_entry_to_record(entry)
            if record:
                records.append(record)

        start += len(entries)
        if not entries or (total is not None and start >= total):
            break

    deduped: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        key = rec.get("DOI") or f"{rec.get('Title','').lower()}::{rec.get('Year',0)}"
        existing = deduped.get(key)
        if not existing or ud.parse_int(rec.get("Citations")) > ud.parse_int(existing.get("Citations")):
            deduped[key] = rec

    out = list(deduped.values())
    out.sort(key=lambda r: (ud.parse_int(r.get("Year")), ud.parse_int(r.get("Citations"))), reverse=True)
    return out


def fetch_openalex_author(orcid: str, verbose: bool) -> Optional[Dict[str, Any]]:
    base_url = "https://api.openalex.org/authors"
    params: Dict[str, Any] = {
        "filter": f"orcid:{orcid}",
        "per_page": 1,
    }
    api_key = os.getenv("OPENALEX_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    email = os.getenv("OPENALEX_EMAIL", "").strip()
    if email:
        params["mailto"] = email
    headers = {"Accept": "application/json", "User-Agent": os.getenv("USER_AGENT", USER_AGENT_DEFAULT)}
    payload = http_get_json(base_url, headers=headers, params=params)
    results = payload.get("results", []) or []
    if not results:
        log("OpenAlex üzerinde ORCID ile eşleşen yazar bulunamadı.", verbose)
        return None
    author = results[0]
    log("OpenAlex yazar profili bulundu.", verbose)
    return author


def update_scholar_block_from_openalex(payload: Dict[str, Any], author: Dict[str, Any]) -> None:
    summary = author.get("summary_stats", {}) or {}
    scholar = payload.setdefault("scholar", {})
    scholar.update({
        "citations_total": ud.parse_int(author.get("cited_by_count"), scholar.get("citations_total", 0)),
        "h_index": ud.parse_int(summary.get("h_index"), scholar.get("h_index", 0)),
        "i10_index": ud.parse_int(summary.get("i10_index"), scholar.get("i10_index", 0)),
    })


def maybe_git_push(files: List[Path], branch: Optional[str], verbose: bool) -> None:
    repo_root = Path.cwd()
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, check=True, capture_output=True, text=True)
    except Exception as exc:
        raise SystemExit(f"Git deposu algılanamadı: {exc}")

    rel_files = [str(path.resolve().relative_to(repo_root.resolve())) for path in files]
    subprocess.run(["git", "add", *rel_files], cwd=repo_root, check=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, check=True, capture_output=True, text=True)
    if not status.stdout.strip():
        log("Git tarafında değişiklik yok; push atlanıyor.", verbose)
        return

    message = f"Auto update dashboard data - {date.today().isoformat()}"
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True)
    push_cmd = ["git", "push"]
    if branch:
        push_cmd.extend(["origin", branch])
    subprocess.run(push_cmd, cwd=repo_root, check=True)
    log("Git push tamamlandı.", verbose)


def main() -> int:
    args = parse_args()
    load_env_file(Path(".env"))
    data_path = Path(args.data)
    out_js = Path(args.out_js)
    if not data_path.exists():
        raise SystemExit(f"Veri dosyası bulunamadı: {data_path}")

    payload = ud.load_json(data_path)
    author_id = (args.author_id or os.getenv("SCOPUS_AUTHOR_ID") or SCOPUS_AUTHOR_ID_DEFAULT).strip()
    orcid = (args.orcid or os.getenv("ORCID_ID") or ORCID_ID_DEFAULT).strip()

    if not args.skip_scopus:
        api_key = get_required_env("SCOPUS_API_KEY")
        records = fetch_scopus_records(api_key, author_id, args.verbose)
        if records:
            payload["records"] = records
            ud.recompute_derived_fields(payload, top_cited_limit=10)
        else:
            log("Scopus'tan kayıt gelmedi; mevcut kayıtlar korunuyor.", args.verbose)

    if not args.skip_openalex:
        author = fetch_openalex_author(orcid, args.verbose)
        if author:
            update_scholar_block_from_openalex(payload, author)

    today = date.today()
    payload.setdefault("meta", {})
    payload["meta"].update({
        "full_name": payload.get("meta", {}).get("full_name", "Süleyman Gökhan Çolak"),
        "last_updated": today.isoformat(),
        "last_updated_display_tr": ud.tr_date_display(today),
    })
    # Backward-compatible fields for older HTML builds
    payload["lastUpdated"] = today.isoformat()
    payload["lastUpdatedDisplay"] = ud.tr_date_display(today)

    ud.save_json(data_path, payload)
    ud.save_js(out_js, payload)
    log(f"Güncellendi: {data_path} ve {out_js}", args.verbose or True)

    auto_push = args.git_push or os.getenv("GIT_AUTO_PUSH", "0").strip().lower() in {"1", "true", "yes"}
    branch = args.git_branch or os.getenv("GIT_BRANCH", "").strip() or None
    if auto_push:
        maybe_git_push([data_path, out_js], branch, args.verbose or True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
