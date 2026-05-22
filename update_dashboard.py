#!/usr/bin/env python3
"""
Update the academic dashboard data files without editing the HTML.

Typical uses
------------
1) Only refresh headline metrics and date:
   python update_dashboard.py --data dashboard_data.json \
       --set-scholar-citations 1050 --set-scholar-h 15 --set-scholar-i10 19

2) Replace Scopus records from a CSV export and recompute all derived tables:
   python update_dashboard.py --data dashboard_data.json \
       --scopus-csv scopus_export.csv \
       --subject-areas-json subject_areas.json \
       --highlighted-json highlighted.json

3) Use a JSON file for Scholar headline metrics:
   python update_dashboard.py --data dashboard_data.json \
       --scholar-metrics-json scholar_metrics.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TR_MONTHS = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update dashboard_data.json and dashboard_data.js")
    parser.add_argument("--data", default="dashboard_data.json", help="Input JSON data file")
    parser.add_argument("--out-json", default=None, help="Output JSON path (default: overwrite input)")
    parser.add_argument("--out-js", default="dashboard_data.js", help="Output JS path")
    parser.add_argument("--last-updated", default="today", help="YYYY-MM-DD or 'today'")

    parser.add_argument("--scholar-metrics-json", help="JSON file with Scholar metrics")
    parser.add_argument("--set-scholar-citations", type=int, help="Override Scholar total citations")
    parser.add_argument("--set-scholar-h", type=int, help="Override Scholar h-index")
    parser.add_argument("--set-scholar-i10", type=int, help="Override Scholar i10-index")
    parser.add_argument("--set-scholar-citations-since2021", type=int, help="Override Scholar citations since 2021")
    parser.add_argument("--set-scholar-h-since2021", type=int, help="Override Scholar h-index since 2021")
    parser.add_argument("--set-scholar-i10-since2021", type=int, help="Override Scholar i10-index since 2021")

    parser.add_argument("--scopus-csv", help="CSV export containing publication-level Scopus records")
    parser.add_argument("--subject-areas-json", help="JSON file with subject areas")
    parser.add_argument("--highlighted-json", help="JSON file with highlighted publications")
    parser.add_argument("--top-cited-limit", type=int, default=10, help="Top cited list length")
    return parser.parse_args()


def canonicalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", key.lower())


def first_existing(row: Dict[str, Any], aliases: Iterable[str]) -> Any:
    canon_map = {canonicalize_key(k): v for k, v in row.items()}
    for alias in aliases:
        c = canonicalize_key(alias)
        if c in canon_map and canon_map[c] not in ("", None):
            return canon_map[c]
    return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_js(path: Path, payload: Any) -> None:
    path.write_text("window.DASHBOARD_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


def parse_date_input(value: str) -> date:
    if value == "today":
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def tr_date_display(d: date) -> str:
    return f"{d.day} {TR_MONTHS[d.month]} {d.year}"


def parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    text = text.replace(".", "").replace(",", "")
    match = re.search(r"-?\d+", text)
    return int(match.group()) if match else default


def parse_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    match = re.search(r"(19|20)\d{2}", text)
    return int(match.group()) if match else None


def normalize_document_type(value: Any) -> str:
    if value is None:
        return "Unknown"
    text = str(value).strip()
    lower = text.lower()
    mapping = {
        "article": "Article",
        "review": "Review",
        "book chapter": "Book chapter",
        "bookchapter": "Book chapter",
        "chapter": "Book chapter",
    }
    return mapping.get(lower, text.title() if text.islower() else text)


def normalize_open_access(value: Any) -> str:
    if value is None:
        return "No"
    text = str(value).strip()
    if not text:
        return "No"
    lower = text.lower()
    if lower in {"0", "false", "no", "n", "closed"}:
        return "No"
    if lower in {"1", "true", "yes", "y", "open"}:
        return "Open Access"
    return text


def make_record_from_csv_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = first_existing(row, ["Title", "Document Title"])
    if not title:
        return None

    year = parse_year(first_existing(row, ["Year", "Publication Year", "Cover Date", "Date"]))
    journal = first_existing(row, ["Journal", "Source title", "Source Title", "Sourcetitle"])
    citations = parse_int(first_existing(row, ["Citations", "Cited by", "Cited By", "Citedbycount"]))
    doc_type = normalize_document_type(first_existing(row, ["Document Type", "Subtype Description", "Subtype", "Type"]))
    open_access = normalize_open_access(first_existing(row, ["Open Access", "Openaccess", "OA"]))
    doi = first_existing(row, ["DOI", "Doi"])
    link = first_existing(row, ["Link", "URL", "Scopus URL", "ScopusUrl"])
    if not link and doi:
        link = f"https://doi.org/{str(doi).strip()}"

    record = {
        "Title": str(title).strip(),
        "Year": year or 0,
        "Journal": str(journal).strip() if journal else "Unknown",
        "Citations": citations,
        "DocumentType": doc_type,
        "OpenAccess": open_access,
        "DOI": str(doi).strip() if doi else "",
        "Link": str(link).strip() if link else "",
    }
    return record


def load_scopus_records_from_csv(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = make_record_from_csv_row(row)
            if record:
                records.append(record)
    records.sort(key=lambda r: (parse_int(r.get("Year")), parse_int(r.get("Citations"))), reverse=True)
    return records


def is_oa(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text and text not in {"no", "nan", "false", "0"})


def recompute_derived_fields(payload: Dict[str, Any], top_cited_limit: int = 10) -> None:
    records = payload.get("records", [])
    records = [r for r in records if r.get("Title")]
    payload["records"] = records

    citations_total = sum(parse_int(r.get("Citations")) for r in records)
    articles = sum(1 for r in records if str(r.get("DocumentType", "")).strip().lower() == "article")
    reviews = sum(1 for r in records if str(r.get("DocumentType", "")).strip().lower() == "review")
    book_chapters = sum(1 for r in records if str(r.get("DocumentType", "")).strip().lower() == "book chapter")
    oa_docs = sum(1 for r in records if is_oa(r.get("OpenAccess")))

    years = [parse_year(r.get("Year")) for r in records if parse_year(r.get("Year"))]
    active_years = f"{min(years)}–{max(years)}" if years else "—"

    payload.setdefault("scopusMetrics", {})
    payload["scopusMetrics"].update({
        "documents": len(records),
        "citations_total": citations_total,
        "oa_docs": oa_docs,
        "reviews": reviews,
        "articles": articles,
        "book_chapters": book_chapters,
        "active_years": active_years,
    })

    yearly_map: Dict[int, Dict[str, int]] = defaultdict(lambda: {"Publications": 0, "TotalCitationsOfPapersPublishedThatYear": 0})
    for r in records:
        year = parse_year(r.get("Year"))
        if not year:
            continue
        yearly_map[year]["Publications"] += 1
        yearly_map[year]["TotalCitationsOfPapersPublishedThatYear"] += parse_int(r.get("Citations"))

    payload["yearly"] = [
        {
            "Year": year,
            "Publications": values["Publications"],
            "TotalCitationsOfPapersPublishedThatYear": values["TotalCitationsOfPapersPublishedThatYear"],
        }
        for year, values in sorted(yearly_map.items())
    ]

    journal_counter = Counter(str(r.get("Journal", "Unknown")).strip() or "Unknown" for r in records)
    payload["journalCounts"] = [
        {"Journal": journal, "Publications": count}
        for journal, count in journal_counter.most_common(10)
    ]

    doc_counter = Counter(normalize_document_type(r.get("DocumentType")) for r in records)
    payload["docTypes"] = [
        {"DocumentType": doc_type, "Publications": count}
        for doc_type, count in doc_counter.most_common()
    ]

    payload["topCited"] = [
        {
            "Title": r.get("Title", ""),
            "Year": parse_year(r.get("Year")) or 0,
            "Journal": r.get("Journal", "Unknown"),
            "Citations": parse_int(r.get("Citations")),
        }
        for r in sorted(records, key=lambda x: parse_int(x.get("Citations")), reverse=True)[:top_cited_limit]
    ]

    payload["pre2023"] = sum(1 for r in records if (parse_year(r.get("Year")) or 0) < 2023)
    payload["post2023"] = sum(1 for r in records if (parse_year(r.get("Year")) or 0) >= 2023)


def update_scholar_metrics(payload: Dict[str, Any], args: argparse.Namespace) -> None:
    payload.setdefault("scholar", {})
    scholar = payload["scholar"]

    if args.scholar_metrics_json:
        incoming = load_json(Path(args.scholar_metrics_json))
        if not isinstance(incoming, dict):
            raise ValueError("scholar-metrics-json must contain a JSON object")
        scholar.update(incoming)

    mapping = {
        "citations_total": args.set_scholar_citations,
        "h_index": args.set_scholar_h,
        "i10_index": args.set_scholar_i10,
        "citations_since2021": args.set_scholar_citations_since2021,
        "h_since2021": args.set_scholar_h_since2021,
        "i10_since2021": args.set_scholar_i10_since2021,
    }
    for key, value in mapping.items():
        if value is not None:
            scholar[key] = value


def main() -> None:
    args = parse_args()
    data_path = Path(args.data)
    out_json_path = Path(args.out_json) if args.out_json else data_path
    out_js_path = Path(args.out_js)

    payload = load_json(data_path)
    if not isinstance(payload, dict):
        raise ValueError("Input data must be a JSON object")

    payload.setdefault("meta", {})
    update_date = parse_date_input(args.last_updated)
    payload["meta"]["last_updated"] = update_date.isoformat()
    payload["meta"]["last_updated_display_tr"] = tr_date_display(update_date)

    update_scholar_metrics(payload, args)

    if args.scopus_csv:
        payload["records"] = load_scopus_records_from_csv(Path(args.scopus_csv))

    if args.subject_areas_json:
        payload["subjectAreas"] = load_json(Path(args.subject_areas_json))

    if args.highlighted_json:
        payload["highlighted"] = load_json(Path(args.highlighted_json))

    recompute_derived_fields(payload, top_cited_limit=args.top_cited_limit)

    save_json(out_json_path, payload)
    save_js(out_js_path, payload)

    print(f"JSON written: {out_json_path}")
    print(f"JS written:   {out_js_path}")
    print(f"Scopus docs:  {payload.get('scopusMetrics', {}).get('documents', 0)}")
    print(f"Citations:    {payload.get('scholar', {}).get('citations_total', 0)} (Scholar) / {payload.get('scopusMetrics', {}).get('citations_total', 0)} (Scopus)")


if __name__ == "__main__":
    main()
