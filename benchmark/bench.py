#!/usr/bin/env python3
"""Benchmark jsonschema validation of an array of records (realistic use case).

Measures how long it takes to validate a JSON response array of `n` heterogeneous
records against a fixed JSON Schema. This is the dominant, everyday use of
jsonschema (validating API/document payloads), where the SAME subschema is
descended into once per array element.
"""
import argparse
import json
import os
import statistics
import sys
import time

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if "--baseline" not in sys.argv:
    sys.path.insert(0, _SRC)

from jsonschema.validators import Draft202012Validator  # noqa: E402


def build_case(n):
    """A realistic schema for validating a page of API responses."""
    member_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "minimum": 0},
            "name": {"type": "string", "maxLength": 128},
            "email": {"type": "string", "format": "email"},
            "active": {"type": "boolean"},
            "roles": {
                "type": "array",
                "items": {"type": "string", "enum": ["admin", "user", "viewer"]},
                "maxItems": 16,
            },
            "balance": {"type": "number", "minimum": 0.0},
            "created": {"type": "string", "format": "date-time"},
        },
        "required": ["id", "name", "email", "active"],
        "additionalProperties": False,
    }
    schema = {
        "type": "array",
        "items": member_schema,
        "maxItems": 100000,
    }
    roles_pool = ["admin", "user", "viewer"]
    instance = []
    for i in range(n):
        instance.append(
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "active": i % 2 == 0,
                "roles": [roles_pool[i % 3]],
                "balance": round(i * 1.5, 2),
                "created": "2026-11-01T08:30:0%dZ" % (i % 9),
            }
        )
    return schema, instance


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--baseline", action="store_true",
                    help="import the installed upstream jsonschema instead of src/ (reference run)")
    ap.add_argument("--samples", type=int, default=7)
    ap.add_argument("--warmup", type=int, default=3)
    args = ap.parse_args()

    sizes = {"small": 500, "medium": 2000, "large": 8000}
    if args.scale not in sizes:
        raise SystemExit(f"unknown scale {args.scale!r}; choose {list(sizes)}")
    n = sizes[args.scale]
    schema, instance = build_case(n)
    validator = Draft202012Validator(schema)

    def run():
        errors = list(validator.iter_errors(instance))
        # A valid case: no errors expected.
        assert not errors, args.scale

    for _ in range(args.warmup):
        run()

    samples = []
    outdir = os.path.dirname(args.output)
    stem = os.path.splitext(os.path.basename(args.output))[0]
    for i in range(args.samples):
        t0 = time.perf_counter()
        run()
        dt = time.perf_counter() - t0
        samples.append(dt)
        with open(os.path.join(outdir, f"{stem}-{i}.json"), "w") as f:
            json.dump(
                {"scale": args.scale, "n": n, "sample_index": i, "seconds": dt},
                f,
            )

    med = statistics.median(samples)
    p25 = sorted(samples)[args.samples // 4]
    p75 = sorted(samples)[args.samples * 3 // 4]
    mean = statistics.fmean(samples)
    stdev = statistics.pstdev(samples)
    rsd = stdev / mean * 100
    agg = {
        "scale": args.scale,
        "n": n,
        "samples": samples,
        "median_seconds": med,
        "p25_seconds": p25,
        "p75_seconds": p75,
        "mean_seconds": mean,
        "stdev_seconds": stdev,
        "rsd_percent": rsd,
    }
    base = os.path.splitext(args.output)[0]
    with open(base + "_agg.json", "w") as f:
        json.dump(agg, f, indent=2)
    print(json.dumps(agg))


if __name__ == "__main__":
    main()