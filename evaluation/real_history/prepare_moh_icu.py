"""Verify or regenerate the paired official Malaysian ICU schema snapshots."""

import argparse
import csv
import hashlib
from io import StringIO
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
REPO = "https://raw.githubusercontent.com/MoH-Malaysia/covid19-public"
SOURCES = {
    "before": ("3b56bc326306a013d1fb26eb4f33084f432b4b4c",
               "f8bd4e11746df2109807e7a1f0261982b4605564",
               ("date", "state", "beds_icu", "vent_covid", "vent_sari")),
    "after": ("4e80229047d796f14c7aac82910a3377277b699f",
              "bc45a1fa903e0b5ec32ccb7a6ca0b37436e10a37",
              ("date", "state", "bed_icu", "vent_covid")),
}
PROJECTED_SHA256 = {
    "before": "b8a0d35cc73b45f6b9367f67472ee2fbc01559993185ce55694317d2d0f651f6",
    "after": "2cd79c6da5e714153456ee743d8f6d2925c2b108b4997ffa0690215911036be6",
}


def path(version: str) -> Path:
    return ROOT / f"moh_icu_2021_{version}.csv"


def project(raw: bytes, names: tuple[str, ...]) -> bytes:
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""))
    if not set(names) <= set(reader.fieldnames or []):
        raise ValueError("Official snapshot lacks required projection columns")
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=names, lineterminator="\n")
    writer.writeheader()
    writer.writerows({name: row[name] for name in names} for row in reader)
    return output.getvalue().encode("utf-8")


def verify() -> dict[str, int]:
    rows = {}
    for version, (_, _, names) in SOURCES.items():
        data = path(version).read_bytes()
        if hashlib.sha256(data).hexdigest() != PROJECTED_SHA256[version]:
            raise ValueError(f"{version} projection differs from the pinned snapshot")
        with path(version).open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != names:
                raise ValueError(f"{version} projection has wrong fields")
            rows[version] = list(reader)
    before, after = rows["before"], rows["after"]
    if len(before) != len(after) or len(before) < 1000:
        raise ValueError("Snapshots are not substantial paired histories")
    keys = {(row["date"], row["state"]) for row in before}
    if len(keys) != len(before):
        raise ValueError("Before snapshot has duplicate date/state keys")
    for old, new in zip(before, after, strict=True):
        expected = {"date": old["date"], "state": old["state"],
                    "bed_icu": old["beds_icu"], "vent_covid": old["vent_covid"]}
        if new != expected:
            raise ValueError("Actual post-change row differs from documented rename/drop")
    nonzero = sum(int(row["vent_sari"]) != 0 for row in before)
    return {"paired_rows": len(before), "nonzero_dropped_values": nonzero}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true",
                        help="Download and regenerate projections from pinned official commits")
    args = parser.parse_args()
    if args.fetch:
        for version, (commit, git_sha, names) in SOURCES.items():
            url = f"{REPO}/{commit}/epidemic/icu.csv"
            with urlopen(url, timeout=30) as response:
                raw = response.read()
            blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
            if blob != git_sha:
                raise ValueError(f"{version} official Git blob differs from pinned source")
            projected = project(raw, names)
            if hashlib.sha256(projected).hexdigest() != PROJECTED_SHA256[version]:
                raise ValueError(f"{version} projection differs from pinned output")
            path(version).write_bytes(projected)
    print(verify())


if __name__ == "__main__":
    main()
