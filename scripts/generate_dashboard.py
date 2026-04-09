#!/usr/bin/env python3
"""
Generate Expert Groups Dashboard
Extracts data from the EC Register of Expert Groups API
and generates a self-contained HTML dashboard with embedded data.
Licence: Commission Decision 2011/833/EU
Developed for DCIRI/DSSD/SGGov (Portugal)
"""
import json, time, datetime, sys, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://ec.europa.eu/transparency/expert-groups-register/core/api/front"
SEARCH_URL = f"{BASE}/expertGroups/search"
DETAIL_URL = f"{BASE}/expertGroups"
REF_ENDPOINTS = {
    "statuses": f"{BASE}/status",
    "dgs": f"{BASE}/dg",
    "policyAreas": f"{BASE}/policyArea",
    "tasks": f"{BASE}/task",
    "types": f"{BASE}/type",
}
PAGE_SIZE = 2000
BATCH_SIZE = 20
BATCH_DELAY = 0.3
MAX_RETRIES = 3
RETRY_DELAY = 300

def post_json(url, body):
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(url):
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_reference_data():
    print("  Fetching reference data...")
    ref = {}
    for key, url in REF_ENDPOINTS.items():
        try:
            ref[key] = get_json(url)
            print(f"    {key}: {len(ref[key])} items")
        except Exception as e:
            print(f"    WARNING: Failed to fetch {key}: {e}")
            ref[key] = []
    return ref

def fetch_all_ids():
    ids = []
    page = 0
    while True:
        url = f"{SEARCH_URL}?page={page}&size={PAGE_SIZE}"
        result = post_json(url, {})
        for item in result.get("content", []):
            ids.append(item["id"])
        if result.get("last", True):
            break
        page += 1
    return ids

def fetch_all_details(ids):
    records = []
    errors = []
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        for gid in batch:
            try:
                rec = get_json(f"{DETAIL_URL}/{gid}")
                records.append(rec)
            except Exception as e:
                errors.append({"id": gid, "error": str(e)})
        done = min(i + BATCH_SIZE, len(ids))
        pct = 100 * done // len(ids)
        print(f"\r  Progress: {done}/{len(ids)} ({pct}%)", end="", flush=True)
        if done < len(ids):
            time.sleep(BATCH_DELAY)
    print()
    return records, errors

def compact_record(r):
    def labels(arr):
        return ", ".join(x.get("label", x.get("code", "")) for x in (arr or []) if isinstance(x, dict))
    status_obj = r.get("status") if isinstance(r.get("status"), dict) else {}
    main_group = r.get("mainGroup") if isinstance(r.get("mainGroup"), dict) else {}
    type_labels = [t.get("label", "") for t in (r.get("types") or []) if isinstance(t, dict)]
    return {
        "code": (r.get("codeGroup") or "").strip(),
        "title": r.get("title") or "",
        "status": status_obj.get("label", ""),
        "statusCode": status_obj.get("code", ""),
        "type": r.get("type") or "",
        "abbr": r.get("abbreviation") or "",
        "policyAreas": labels(r.get("policyAreas")),
        "leadDgs": labels(r.get("leadDgs")),
        "assocDgs": labels(r.get("associatedDgs")),
        "types": ", ".join(type_labels),
        "scope": labels(r.get("scope")),
        "mission": r.get("mission") or "",
        "tasks": labels(r.get("tasks")),
        "contact": r.get("contact") or "",
        "pubDate": r.get("publicationDate") or "",
        "updDate": r.get("updateDate") or "",
        "createAct": r.get("creatingAct") or "",
        "torLink": r.get("torLink") or "",
        "policyOther": r.get("policyAreaOther") or "",
        "parentCode": (main_group.get("codeGroup") or "").strip(),
        "parentTitle": main_group.get("title") or "",
    }

def fetch_all_data():
    ref_data = fetch_reference_data()
    print("\n  Retrieving all group IDs...")
    ids = fetch_all_ids()
    print(f"  Found {len(ids)} groups.")
    print(f"\n  Fetching details for {len(ids)} groups...")
    records, errors = fetch_all_details(ids)
    print(f"  Fetched {len(records)} records, {len(errors)} errors.")
    if errors:
        for e in errors[:5]:
            print(f"    ID {e['id']}: {e['error']}")
    compact = [compact_record(r) for r in records]
    return compact, ref_data

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    template_path = os.environ.get("TEMPLATE_PATH",
        os.path.join(repo_root, "templates", "dashboard_template.html"))
    output_path = os.environ.get("OUTPUT_PATH",
        os.path.join(repo_root, "docs", "index.html"))

    today = datetime.date.today().isoformat()
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M") + " UTC"
    print(f"{'='*60}")
    print(f"  Expert Groups Dashboard Generator - {today}")
    print(f"{'='*60}")

    # Read template
    if not os.path.exists(template_path):
        print(f"ERROR: Template not found: {template_path}")
        sys.exit(1)
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    print(f"  Template loaded: {len(template)} chars")

    # Fetch data with retries
    compact = None
    ref_data = None
    for attempt in range(MAX_RETRIES):
        try:
            compact, ref_data = fetch_all_data()
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  Attempt {attempt+1} failed: {e}. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  All {MAX_RETRIES} attempts failed. Keeping previous version.")
                sys.exit(0)

    # Build HTML
    data_json = json.dumps(compact, ensure_ascii=False)
    ref_json = json.dumps(ref_data, ensure_ascii=False)
    html = template.replace("'__DATA_PLACEHOLDER__'", data_json)
    html = html.replace("'__REF_PLACEHOLDER__'", ref_json)
    html = html.replace("__GENDATE__", now_str)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = len(html) / 1024 / 1024
    print(f"\n  Dashboard saved: {output_path}")
    print(f"  Size: {size_mb:.2f} MB | Records: {len(compact)} | Date: {now_str}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
