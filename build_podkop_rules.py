#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import fcntl
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SCRIPT_DIR = Path(os.environ.get("SCRIPT_DIR", str(REPO_ROOT)))
OUT_DIR = Path(os.environ.get("OUT_DIR", str(REPO_ROOT / "dist")))
LOCK_FILE = Path(os.environ.get("LOCK_FILE", str(SCRIPT_DIR / "build_podkop_rules.lock")))

DOMAIN_URLS = [
    "https://github.com/itdoginfo/allow-domains/releases/latest/download/russia_inside.srs",
    "https://github.com/1andrevich/Re-filter-lists/releases/latest/download/ruleset-domain-refilter_domains.srs",
    "https://github.com/legiz-ru/sb-rule-sets/raw/main/ru-bundle.srs",
]

IP_URLS = [
    "https://github.com/1andrevich/Re-filter-lists/releases/latest/download/ruleset-ip-refilter_ipsum.srs",
    "https://github.com/legiz-ru/sb-rule-sets/raw/main/rknasnblock.srs",
]

# Что режем из domain/domain_suffix exact/suffix матчем.
FORCE_REMOVE_SUFFIXES = {
    "youtube.com",
    "ytimg.com",
    "yting.com",
    "ggpht.com",
    "googlevideo.com",
    "youtubekids.com",
    "youtu.be",
    "yt.be",
    "youtube-nocookie.com",
    "wide-youtube.l.google.com",
    "ytimg.l.google.com",
    "youtubei.googleapis.com",
    "youtubeembeddedplayer.googleapis.com",
    "youtube-ui.l.google.com",
    "yt-video-upload.l.google.com",
    "jnn-pa.googleapis.com",
    "returnyoutubedislikeapi.com",
    "yt3.googleusercontent.com",
    "youtubeeducation.com",
}

# Что режем в keyword/regex/частично кривых записях по contains.
FORCE_REMOVE_TOKENS = {
    "youtube",
    "youtube.com",
    "ytimg",
    "ytimg.com",
    "yting",
    "yting.com",
    "ggpht",
    "ggpht.com",
    "googlevideo",
    "googlevideo.com",
    "youtubekids",
    "youtubekids.com",
    "youtu.be",
    "yt.be",
    "youtube-nocookie",
    "youtube-nocookie.com",
    "wide-youtube.l.google.com",
    "ytimg.l.google.com",
    "youtubei.googleapis.com",
    "youtubeembeddedplayer.googleapis.com",
    "youtube-ui.l.google.com",
    "yt-video-upload.l.google.com",
    "jnn-pa.googleapis.com",
    "returnyoutubedislikeapi.com",
    "yt3.googleusercontent.com",
    "youtubeeducation",
    "youtubeeducation.com",
}

MANUAL_IP_EXCLUDE_FILE = Path(
    os.environ.get("MANUAL_IP_EXCLUDE_FILE", str(OUT_DIR / "youtube_ip_exclude.txt"))
)

DOMAINS_JSON_FINAL = OUT_DIR / "ru-domains-no-youtube.json"
DOMAINS_SRS_FINAL = OUT_DIR / "ru-domains-no-youtube.srs"
DOMAINS_LST_FINAL = OUT_DIR / "ru-domains-no-youtube.lst"

IPS_JSON_FINAL = OUT_DIR / "ru-ips-merged.json"
IPS_SRS_FINAL = OUT_DIR / "ru-ips-merged.srs"
IPS_LST_FINAL = OUT_DIR / "ru-ips-merged.lst"

META_JSON_FINAL = OUT_DIR / "ru-rules-build-meta.json"

RULESET_VERSION = 3


def fail(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Команда упала:\n"
            f"{' '.join(cmd)}\n\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )
    return proc


def ensure_tools() -> str:
    singbox_bin = os.environ.get("SINGBOX_BIN") or shutil.which("sing-box")
    if not singbox_bin:
        fail("Не найден sing-box в PATH. Поставь sing-box и/или задай SINGBOX_BIN.")
    if not shutil.which("python3"):
        fail("Не найден python3 в PATH.")
    return singbox_bin


def ensure_dirs() -> None:
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not MANUAL_IP_EXCLUDE_FILE.exists():
        MANUAL_IP_EXCLUDE_FILE.write_text(
            "# Сети, которые нужно вручную исключить из итогового IP ruleset.\n"
            "# Автоматом честно вычислить 'все YouTube IP' нельзя.\n"
            "# Формат: один CIDR на строку.\n"
            "# Пример:\n"
            "# 203.0.113.0/24\n",
            encoding="utf-8",
        )


def acquire_lock():
    lock_fd = open(LOCK_FILE, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fail(f"Скрипт уже запущен. Lock: {LOCK_FILE}")
    return lock_fd


def download(url: str, dst: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) podkop-rules-builder/1.2"
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp, open(dst, "wb") as f:
        shutil.copyfileobj(resp, f)


def decompile_ruleset(singbox_bin: str, srs_path: Path, json_path: Path) -> None:
    run_cmd([singbox_bin, "rule-set", "decompile", str(srs_path), "-o", str(json_path)])


def compile_ruleset_atomic(singbox_bin: str, json_path: Path, final_srs: Path) -> None:
    tmp_srs = final_srs.with_name(f".{final_srs.name}.tmp")
    if tmp_srs.exists():
        tmp_srs.unlink()
    run_cmd([singbox_bin, "rule-set", "compile", str(json_path), "-o", str(tmp_srs)])
    os.replace(tmp_srs, final_srs)


def write_json_atomic(data: dict, final_json: Path) -> None:
    tmp_json = final_json.with_name(f".{final_json.name}.tmp")
    tmp_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_json, final_json)


def write_lines_atomic(lines: list[str], final_path: Path) -> None:
    tmp_path = final_path.with_name(f".{final_path.name}.tmp")
    content = "\n".join(lines)
    if content:
        content += "\n"
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, final_path)


def iter_rule_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        rules = obj.get("rules")
        if isinstance(rules, list):
            for item in rules:
                yield from iter_rule_dicts(item)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_rule_dicts(item)


def iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def normalize_domain(v: str) -> str:
    return v.strip().lower().strip(".")


def normalize_keyword(v: str) -> str:
    return v.strip().lower()


def normalize_regex(v: str) -> str:
    return v.strip()


def is_force_removed(v: str) -> bool:
    x = v.strip().lower()
    x_clean = x.strip(".")

    for token in FORCE_REMOVE_TOKENS:
        if token in x:
            return True

    for suffix in FORCE_REMOVE_SUFFIXES:
        s = suffix.strip().lower().strip(".")
        if x_clean == s or x_clean.endswith("." + s):
            return True

    return False


def normalize_cidr(v: str) -> str | None:
    raw = v.strip()
    if not raw:
        return None
    try:
        return str(ipaddress.ip_network(raw, strict=False))
    except ValueError:
        print(f"[WARN] Пропускаю кривой CIDR: {raw!r}", file=sys.stderr)
        return None


def sort_cidrs(cidrs: set[str]) -> list[str]:
    nets = [ipaddress.ip_network(x, strict=False) for x in cidrs]
    nets.sort(key=lambda n: (n.version, int(n.network_address), n.prefixlen))
    return [str(n) for n in nets]


def load_manual_ip_excludes() -> set[str]:
    result = set()
    if not MANUAL_IP_EXCLUDE_FILE.exists():
        return result

    for line in MANUAL_IP_EXCLUDE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        cidr = normalize_cidr(line)
        if cidr:
            result.add(cidr)
    return result


def collect_from_json(json_path: Path) -> dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    out = {
        "domain": [],
        "domain_suffix": [],
        "domain_keyword": [],
        "domain_regex": [],
        "ip_cidr": [],
        "source_ip_cidr": [],
    }

    for rule in iter_rule_dicts(data):
        for key in out.keys():
            for s in iter_strings(rule.get(key)):
                out[key].append(s)

    return out


def build_domain_rules(merged: list[dict]) -> tuple[dict, dict, list[str]]:
    domains = set()
    domain_suffixes = set()
    domain_keywords = set()
    domain_regexes = set()

    src_stats = {
        "raw_domain": 0,
        "raw_domain_suffix": 0,
        "raw_domain_keyword": 0,
        "raw_domain_regex": 0,
        "force_removed": 0,
    }

    for item in merged:
        for raw in item["domain"]:
            src_stats["raw_domain"] += 1
            v = normalize_domain(raw)
            if not v:
                continue
            if is_force_removed(v):
                src_stats["force_removed"] += 1
                continue
            domains.add(v)

        for raw in item["domain_suffix"]:
            src_stats["raw_domain_suffix"] += 1
            v = normalize_domain(raw)
            if not v:
                continue
            if is_force_removed(v):
                src_stats["force_removed"] += 1
                continue
            domain_suffixes.add(v)

        for raw in item["domain_keyword"]:
            src_stats["raw_domain_keyword"] += 1
            v = normalize_keyword(raw)
            if not v:
                continue
            if is_force_removed(v):
                src_stats["force_removed"] += 1
                continue
            domain_keywords.add(v)

        for raw in item["domain_regex"]:
            src_stats["raw_domain_regex"] += 1
            v = normalize_regex(raw)
            if not v:
                continue
            if is_force_removed(v):
                src_stats["force_removed"] += 1
                continue
            domain_regexes.add(v)

    rules = []
    if domains:
        rules.append({"domain": sorted(domains)})
    if domain_suffixes:
        rules.append({"domain_suffix": sorted(domain_suffixes)})
    if domain_keywords:
        rules.append({"domain_keyword": sorted(domain_keywords)})
    if domain_regexes:
        rules.append({"domain_regex": sorted(domain_regexes)})

    domain_json = {
        "version": RULESET_VERSION,
        "rules": rules,
    }

    domain_lst_lines = sorted(domains | domain_suffixes)

    stats = {
        **src_stats,
        "final_domain": len(domains),
        "final_domain_suffix": len(domain_suffixes),
        "final_domain_keyword": len(domain_keywords),
        "final_domain_regex": len(domain_regexes),
        "final_domain_lst_lines": len(domain_lst_lines),
    }

    return domain_json, stats, domain_lst_lines


def build_ip_rules(merged: list[dict]) -> tuple[dict, dict, list[str]]:
    cidrs = set()
    raw_count = 0

    for item in merged:
        for key in ("ip_cidr", "source_ip_cidr"):
            for raw in item[key]:
                raw_count += 1
                cidr = normalize_cidr(raw)
                if cidr:
                    cidrs.add(cidr)

    manual_excludes = load_manual_ip_excludes()
    before_manual = len(cidrs)
    cidrs -= manual_excludes
    after_manual = len(cidrs)

    cidr_lines = sort_cidrs(cidrs)

    ip_json = {
        "version": RULESET_VERSION,
        "rules": [{"ip_cidr": cidr_lines}] if cidr_lines else [],
    }

    stats = {
        "raw_ip_entries": raw_count,
        "final_ip_cidrs": len(cidr_lines),
        "manual_ip_excludes_applied": len(manual_excludes),
        "removed_by_manual_file": before_manual - after_manual,
        "final_ip_lst_lines": len(cidr_lines),
    }

    return ip_json, stats, cidr_lines


def main() -> None:
    singbox_bin = ensure_tools()
    ensure_dirs()
    lock_fd = acquire_lock()

    print("[INFO] Старт")
    print(f"[INFO] SCRIPT_DIR = {SCRIPT_DIR}")
    print(f"[INFO] OUT_DIR = {OUT_DIR}")
    print(f"[INFO] sing-box = {singbox_bin}")

    with tempfile.TemporaryDirectory(prefix="podkop_rules_") as tmp:
        tmpdir = Path(tmp)

        domain_collected = []
        ip_collected = []

        for idx, url in enumerate(DOMAIN_URLS, start=1):
            srs_path = tmpdir / f"domain_{idx}.srs"
            json_path = tmpdir / f"domain_{idx}.json"
            print(f"[INFO] Качаю domain list {idx}: {url}")
            download(url, srs_path)
            print(f"[INFO] Decompile domain list {idx}")
            decompile_ruleset(singbox_bin, srs_path, json_path)
            domain_collected.append(collect_from_json(json_path))

        for idx, url in enumerate(IP_URLS, start=1):
            srs_path = tmpdir / f"ip_{idx}.srs"
            json_path = tmpdir / f"ip_{idx}.json"
            print(f"[INFO] Качаю ip list {idx}: {url}")
            download(url, srs_path)
            print(f"[INFO] Decompile ip list {idx}")
            decompile_ruleset(singbox_bin, srs_path, json_path)
            ip_collected.append(collect_from_json(json_path))

        domains_json, domains_stats, domains_lst_lines = build_domain_rules(domain_collected)
        ips_json, ips_stats, ips_lst_lines = build_ip_rules(ip_collected)

        write_json_atomic(domains_json, DOMAINS_JSON_FINAL)
        write_json_atomic(ips_json, IPS_JSON_FINAL)

        write_lines_atomic(domains_lst_lines, DOMAINS_LST_FINAL)
        write_lines_atomic(ips_lst_lines, IPS_LST_FINAL)

        compile_ruleset_atomic(singbox_bin, DOMAINS_JSON_FINAL, DOMAINS_SRS_FINAL)
        compile_ruleset_atomic(singbox_bin, IPS_JSON_FINAL, IPS_SRS_FINAL)

        meta = {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "script_dir": str(SCRIPT_DIR),
            "output_dir": str(OUT_DIR),
            "domain_sources": DOMAIN_URLS,
            "ip_sources": IP_URLS,
            "ruleset_version": RULESET_VERSION,
            "force_remove_suffixes": sorted(FORCE_REMOVE_SUFFIXES),
            "force_remove_tokens": sorted(FORCE_REMOVE_TOKENS),
            "domains_stats": domains_stats,
            "ips_stats": ips_stats,
            "manual_ip_exclude_file": str(MANUAL_IP_EXCLUDE_FILE),
            "domain_lst_file": str(DOMAINS_LST_FINAL),
            "ip_lst_file": str(IPS_LST_FINAL),
        }
        write_json_atomic(meta, META_JSON_FINAL)

        print("[OK] Готово")
        print(f"[OK] {DOMAINS_JSON_FINAL}")
        print(f"[OK] {DOMAINS_SRS_FINAL}")
        print(f"[OK] {DOMAINS_LST_FINAL}")
        print(f"[OK] {IPS_JSON_FINAL}")
        print(f"[OK] {IPS_SRS_FINAL}")
        print(f"[OK] {IPS_LST_FINAL}")
        print(f"[OK] {META_JSON_FINAL}")

    lock_fd.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
