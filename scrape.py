"""ジェクサーのグループレッスン時間割から BODY COMBAT / BODY ATTACK / UBOUND の枠を集める。

使い方:
    python scrape.py          # 今月分 -> data/latest.txt, data/YYYYMM.txt
    python scrape.py --next   # 翌月分 -> data/next.txt
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":  # Windows の証明書ストアを使う（Windows 環境の SSL エラー対策）
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass

import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BASE = "https://www.jexer.jp/schedule/{kind}/?shop={shop}"

# (店舗名, 種別, shop番号)
STORES = [
    ("四谷", "fitness", 3), ("大井町", "fitness", 4), ("赤羽", "fitness", 5),
    ("大宮", "fitness", 6), ("戸田公園", "fitness", 7), ("上野", "fitness", 8),
    ("池袋", "fitness", 9), ("東神奈川", "fitness", 17), ("亀戸", "fitness", 24),
    ("新宿", "fitness", 25), ("大塚", "fitness", 32), ("新川崎", "fitness", 37),
    ("浦和", "fitness", 45), ("横浜", "fitness", 66), ("板橋", "fitness", 67),
    ("川崎", "fitness", 76), ("新小岩", "fitness", 86),
    ("国分寺", "lightgym", 60), ("東小金井", "lightgym", 63), ("高円寺", "lightgym", 64),
]

DAY_CLASS = {"monday": "月", "tueday": "火", "wedday": "水", "thuday": "木",
             "friday": "金", "satday": "土", "sunday": "日"}
DAY_ORDER = "月火水木金土日"

TARGET = re.compile(r"BODY\s*(COMBAT|ATTACK)|UBOUND", re.I)
# 備考として拾う括弧書き
BRACKETS = re.compile(r"【([^】]*)】|〔([^〕]*)〕|〈([^〉]*)〉|［([^］\]]*)[］\]]|\[([^\]］]*)[\]］]|[(（]([^)）]*)[)）]")


def clean(s):
    return re.sub(r"\s+", " ", s.replace("|", "／")).strip()


def category(program):
    m = TARGET.search(program)
    if m.group(1):
        return "C" if m.group(1).upper() == "COMBAT" else "A"
    return "U"


def hhmm(t):
    h, m = t.strip().split(":")
    return f"{int(h):02d}:{m}"


def parse(html, store):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    closed = [lab.get_text(strip=True)[0] for lab in soup.select(".weekSelect label")
              if "休館" in lab.get_text()]
    table = soup.find(id="tameTable")
    rows = []
    if table is None:
        return title, closed, rows
    for daydiv in table.find_all("div", class_="wCount"):
        day = next((DAY_CLASS[c] for c in daydiv.get("class", []) if c in DAY_CLASS), None)
        if day is None:
            continue
        for ul in daydiv.find_all("ul"):
            head = ul.find("li", class_="title")
            studio = clean(head.get_text()) if head else ""
            for li in ul.find_all("li"):
                prog_el = li.find("span", class_="program")
                if prog_el is None:
                    continue
                program = clean(prog_el.get_text(" "))
                if not TARGET.search(program):
                    continue
                start, end = re.split(r"[～〜~]", li.find("span", class_="time").get_text(strip=True))
                inst_el = li.find("span", class_="instractor")
                instructor = clean(inst_el.get_text(" ")) if inst_el else ""
                icons = {img["src"].rsplit("/", 1)[-1].split(".")[0] for img in li.find_all("img")}
                vr = instructor.upper().startswith("VR") or "VR" in program.upper().split()
                notes = []
                for m in BRACKETS.finditer(program):
                    note = clean(next(g for g in m.groups() if g is not None))
                    if note and "暗闇" not in note and note not in notes:
                        notes.append(note)
                # 定員表記は備考に入れたうえでプログラム名からは取り除く
                program = clean(BRACKETS.sub(
                    lambda m: "" if "定員" in m.group(0) else m.group(0), program))
                flags = "x" if vr or "icon_reserve" not in icons else "w"
                if "暗闇" in program:
                    flags += "d"
                if vr:
                    flags += "v"
                if "icon_yen" in icons:
                    flags += "y"
                if "icon_new" in icons:
                    flags += "n"
                if "icon_beg" in icons:
                    flags += "b"
                rows.append({
                    "day": day, "start": hhmm(start), "end": hhmm(end),
                    "cat": category(program), "program": program, "store": store,
                    "studio": studio, "instructor": "VR" if vr else instructor,
                    "flags": flags, "note": "・".join(notes),
                })
    return title, closed, merge_studios(rows)


def merge_studios(rows):
    """同じ枠が複数スタジオ列（例: アリーナ①・②）に重複表示される場合は1行にまとめる。"""
    merged = {}
    for r in rows:
        key = (r["day"], r["start"], r["end"], r["program"], r["instructor"])
        if key in merged:
            if r["studio"] not in merged[key]["studio"].split("・"):
                merged[key]["studio"] += "・" + r["studio"]
        else:
            merged[key] = dict(r)
    return list(merged.values())


def fetch(url):
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (jexer-lessons)"}, timeout=(10, 30))
            r.raise_for_status()
            return r.content.decode("utf-8", "replace")
        except requests.RequestException as e:
            print(f"  retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(5)
    return None


def line(r):
    return "|".join([r["day"], r["start"], r["end"], r["cat"], r["program"], r["store"],
                     r["studio"], r["instructor"], r["flags"], r["note"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", action="store_true", help="翌月分を取得して data/next.txt に出力")
    args = ap.parse_args()

    now = datetime.now(JST)
    all_rows, stores, warnings = [], {}, []
    for name, kind, shop in STORES:
        url = BASE.format(kind=kind, shop=shop) + ("&next=true" if args.next else "")
        html = fetch(url)
        if html is None and not stores:
            # 最初の店舗から取れないときはサイトに接続できていないので、既存データを残して中止
            sys.exit(f"ERROR: {url} に接続できません。data/ は更新しません。")
        if html is None:
            warnings.append(f"{name}: 取得失敗 {url}")
            stores[name] = {"shop": shop, "kind": kind, "closed": [], "count": 0,
                            "fetched_at": now.isoformat(timespec="seconds"), "error": "fetch failed"}
            continue
        title, closed, rows = parse(html, name)
        if name not in title:
            warnings.append(f"{name}: ページの店舗名が想定と違う（{title}）")
        if not rows:
            warnings.append(f"{name}: 件数0")
        rows.sort(key=lambda r: (DAY_ORDER.index(r["day"]), r["start"], r["studio"]))
        all_rows += rows
        stores[name] = {"shop": shop, "kind": kind, "page_title": title, "closed": closed,
                        "count": len(rows), "fetched_at": datetime.now(JST).isoformat(timespec="seconds")}
        print(f"{name}\t{len(rows)}", flush=True)
        time.sleep(1)  # サーバーに負荷をかけないよう間隔をあける

    if not all_rows:
        sys.exit("ERROR: 1件も取れませんでした。data/ は更新しません。")
    os.makedirs(DATA_DIR, exist_ok=True)
    text = "".join(line(r) + "\n" for r in all_rows)
    outputs = ["next.txt"] if args.next else ["latest.txt", now.strftime("%Y%m") + ".txt"]
    for fn in outputs:
        with open(os.path.join(DATA_DIR, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    if not args.next:
        with open(os.path.join(DATA_DIR, "stores.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(stores, f, ensure_ascii=False, indent=2)
            f.write("\n")
    with open(os.path.join(DATA_DIR, "warnings.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(w + "\n" for w in warnings))
    print(f"合計 {len(all_rows)} 枠 -> {', '.join(outputs)}")
    for w in warnings:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
