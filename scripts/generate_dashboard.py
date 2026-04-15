#!/usr/bin/env python3
"""
Generate Expert Groups Dashboard

Extracts data from the EC Register of Expert Groups API and generates
a self-contained HTML dashboard with embedded data.

Licence: Commission Decision 2011/833/EU
Developed for DCIRI/DSSD/SGGov (Portugal)
"""

import json, time, datetime, sys, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://ec.europa.eu/transparency/expert-groups-register/core/api/front"
SEARCH_URL  = f"{BASE}/expertGroups/search"
DETAIL_URL  = f"{BASE}/expertGroups"
MEMBERS_URL = f"{BASE}/members"
STATS_URL   = f"{BASE}/expertGroups"      # /{id}/statistics
ADDINFO_URL = f"{BASE}/expertGroups"      # /{id}/additionalInformation

REF_ENDPOINTS = {
    "statuses":    f"{BASE}/status",
    "dgs":         f"{BASE}/dg",
    "policyAreas": f"{BASE}/policyArea",
    "tasks":       f"{BASE}/task",
    "types":       f"{BASE}/type",
}

PAGE_SIZE   = 2000
BATCH_SIZE  = 20
BATCH_DELAY = 0.3
MAX_RETRIES = 3
RETRY_DELAY = 300

MEMBER_CATEGORIES = [1, 2, 3, 4, 5]
MEMBER_TYPE_LABELS = {
    1: "Type A - Individual experts",
    2: "Type B - Representatives of interest",
    3: "Type C - Organisations",
    4: "Type D - Member State authorities",
    5: "Type E - Other public entities",
}


def post_json(url, body):
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url):
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def safe_get_json(url, retries=2, delay=2):
    """get_json with retry logic for member endpoints."""
    for attempt in range(retries):
        try:
            return get_json(url)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                return None


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


def fetch_members_for_group(group_id):
    """Fetch all 5 member categories for a group."""
    members = {}
    countries = set()
    for cat in MEMBER_CATEGORIES:
        url = f"{MEMBERS_URL}/{group_id}/{cat}"
        data = safe_get_json(url)
        if data is None:
            data = []
        members[str(cat)] = data
        # Extract countries
        for m in data:
            if cat == 4 and m.get("country"):
                countries.add(m["country"])
            for area in (m.get("areasRepresented") or []):
                if isinstance(area, str):
                    countries.add(area)
    return members, sorted(countries)


def fetch_statistics_for_group(group_id):
    """Fetch /statistics endpoint for a group."""
    url = f"{STATS_URL}/{group_id}/statistics"
    data = safe_get_json(url)
    return data or {}


def fetch_additional_info_for_group(group_id):
    """Fetch /additionalInformation endpoint for a group."""
    url = f"{ADDINFO_URL}/{group_id}/additionalInformation"
    data = safe_get_json(url)
    return data or {}


def fetch_all_extras_for_group(group_id):
    """Fetch members + statistics + additionalInformation for a single group."""
    members, countries = fetch_members_for_group(group_id)
    stats = fetch_statistics_for_group(group_id)
    addinfo = fetch_additional_info_for_group(group_id)
    return {
        "members": members,
        "countries": countries,
        "statistics": stats,
        "additionalInfo": addinfo,
    }


def fetch_all_details(ids):
    records = []
    errors = []
    total = len(ids)
    for i in range(0, total, BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        for gid in batch:
            try:
                rec = get_json(f"{DETAIL_URL}/{gid}")
                rec["_numericId"] = gid
                records.append(rec)
            except Exception as e:
                errors.append({"id": gid, "error": str(e)})
        done = min(i + BATCH_SIZE, total)
        pct = 100 * done // total
        print(f"\r  Progress (details): {done}/{total} ({pct}%)", end="", flush=True)
        if done < total:
            time.sleep(BATCH_DELAY)
    print()
    return records, errors


def fetch_all_extras(records):
    """Fetch members + statistics + additional info for all groups."""
    extras_map = {}
    total = len(records)
    for i, rec in enumerate(records):
        gid = rec.get("_numericId")
        if gid is None:
            continue
        try:
            extras_map[gid] = fetch_all_extras_for_group(gid)
        except Exception:
            extras_map[gid] = {"members": {}, "countries": [], "statistics": {}, "additionalInfo": {}}

        if (i + 1) % 10 == 0 or (i + 1) == total:
            pct = 100 * (i + 1) // total
            print(f"\r  Progress (extras): {i+1}/{total} ({pct}%)", end="", flush=True)
        time.sleep(BATCH_DELAY)
    print()
    return extras_map


def compact_member(m, cat):
    """Compact a single member record — captures ALL available fields."""
    base = {
        "status":           m.get("membershipStatus", ""),
        "name":             m.get("name", ""),
        "category":         m.get("category", ""),
        "appointmentDate":  m.get("appointmentDate", ""),
        "gender":           m.get("gender", ""),
        "role":             m.get("role", ""),
    }
    # Category-specific fields
    if cat == 3 or cat == 5:
        base["areas"] = m.get("areasRepresented", [])
        base["transparencyRegisterNumber"] = m.get("transparencyRegisterNumber", "")
    if cat == 2:
        base["transparencyRegisterNumber"] = m.get("transparencyRegisterNumber", "")
    if cat == 4:
        base["country"] = m.get("country", "")
        base["paCount"] = m.get("publicAuthorityCount", 0)
        # Public authorities list may be present
        pas = m.get("publicAuthorities") or []
        if pas:
            base["publicAuthorities"] = [
                {"name": pa.get("name", ""), "role": pa.get("role", "")}
                for pa in pas if isinstance(pa, dict)
            ]
    if cat == 5:
        base["entityType"] = m.get("entityType", "")
    return base


def compact_record(r, extras=None):
    """Compact a group record with ALL fields: basic + members + stats + additionalInfo."""
    def labels(arr):
        return ", ".join(x.get("label", x.get("code", "")) for x in (arr or []) if isinstance(x, dict))
    def labels_list(arr):
        return [x.get("label", x.get("code", "")) for x in (arr or []) if isinstance(x, dict)]

    status_obj  = r.get("status") if isinstance(r.get("status"), dict) else {}
    main_group  = r.get("mainGroup") if isinstance(r.get("mainGroup"), dict) else {}
    type_labels = [t.get("label", "") for t in (r.get("types") or []) if isinstance(t, dict)]

    result = {
        # Identification
        "code":        (r.get("codeGroup") or "").strip(),
        "title":       r.get("title") or "",
        "status":      status_obj.get("label", ""),
        "statusCode":  status_obj.get("code", ""),
        "type":        r.get("type") or "",
        "abbr":        r.get("abbreviation") or "",
        # Classification (both as strings and lists)
        "policyAreas":     labels(r.get("policyAreas")),
        "policyAreasList": labels_list(r.get("policyAreas")),
        "leadDgs":         labels(r.get("leadDgs")),
        "leadDgsList":     labels_list(r.get("leadDgs")),
        "assocDgs":        labels(r.get("associatedDgs")),
        "assocDgsList":    labels_list(r.get("associatedDgs")),
        "types":           ", ".join(type_labels),
        "typesList":       type_labels,
        "scope":           labels(r.get("scope")),
        "scopeList":       labels_list(r.get("scope")),
        "tasks":           labels(r.get("tasks")),
        "tasksList":       labels_list(r.get("tasks")),
        "policyOther":     r.get("policyAreaOther") or "",
        # Description
        "mission":    r.get("mission") or "",
        "createAct":  r.get("creatingAct") or "",
        "torLink":    r.get("torLink") or "",
        "contact":    r.get("contact") or "",
        # Dates
        "pubDate":       r.get("publicationDate") or "",
        "updDate":       r.get("updateDate") or "",
        "creationDate":  r.get("creationDate") or "",
        # Structure
        "parentCode":    (main_group.get("codeGroup") or "").strip(),
        "parentTitle":   main_group.get("title") or "",
    }

    # --- Members ---
    if extras:
        result["countries"] = extras.get("countries", [])
        raw_members = extras.get("members", {})
        compacted = {}
        total_members = 0
        for cat_str, mlist in raw_members.items():
            cat = int(cat_str)
            compacted[cat_str] = [compact_member(m, cat) for m in mlist]
            total_members += len(mlist)
        result["members"] = compacted
        result["memberCount"] = total_members

        # --- Statistics ---
        stats = extras.get("statistics") or {}
        result["stats"] = {
            "totalMembers":   stats.get("totalMembers", 0),
            "totalObservers": stats.get("totalObservers", 0),
            "maleCount":      stats.get("maleCount", 0),
            "femaleCount":    stats.get("femaleCount", 0),
            "otherGender":    stats.get("otherGender", 0),
            "byCategory":     stats.get("byCategory", {}),
            "byGender":       stats.get("byGender", {}),
            "raw":            stats,  # keep raw in case fields vary
        }

        # --- Additional Info ---
        addinfo = extras.get("additionalInfo") or {}
        result["addInfo"] = {
            "website":           addinfo.get("website", ""),
            "rulesOfProcedure":  addinfo.get("rulesOfProcedure", ""),
            "selectionProcedure": addinfo.get("selectionProcedure", ""),
            "activityReports":   addinfo.get("activityReports", []),
            "meetingMinutes":    addinfo.get("meetingMinutes", []),
            "agendas":           addinfo.get("agendas", []),
            "documents":         addinfo.get("documents", []),
            "raw":               addinfo,  # keep raw
        }
    else:
        result["countries"] = []
        result["members"] = {}
        result["memberCount"] = 0
        result["stats"] = {}
        result["addInfo"] = {}

    return result


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

    print(f"\n  Fetching extras (members + stats + addInfo) for {len(records)} groups...")
    extras_map = fetch_all_extras(records)
    print(f"  Extras fetched for {len(extras_map)} groups.")

    compact = []
    for r in records:
        gid = r.get("_numericId")
        mi = extras_map.get(gid)
        compact.append(compact_record(r, mi))

    return compact, ref_data


def main():
    script_dir    = os.path.dirname(os.path.abspath(__file__))
    repo_root     = os.path.dirname(script_dir)
    template_path = os.environ.get("TEMPLATE_PATH",
                                   os.path.join(repo_root, "templates", "dashboard_template.html"))
    output_path   = os.environ.get("OUTPUT_PATH",
                                   os.path.join(repo_root, "docs", "index.html"))

    today   = datetime.date.today().isoformat()
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
    compact  = None
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
    ref_json  = json.dumps(ref_data, ensure_ascii=False)
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
