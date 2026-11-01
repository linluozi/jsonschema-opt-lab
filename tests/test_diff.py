#!/usr/bin/env python3
"""Differential test: prove the optimized jsonschema is byte-for-byte identical
to the unpatched upstream on a diverse, deterministic corpus.

G2 gate: >=1000 groups, all byte-identical.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

sys.path.insert(0, str(pathlib.Path(__file__).parent))

HERE = pathlib.Path(__file__).parent
CORPUS = HERE / "corpus.json"
GOLDEN = HERE / "golden_baseline.json"


def serialize_error(run_index, schema, instance, errors):
    if errors and isinstance(errors[0], str):  # exception marker
        return {
            "run": run_index,
            "schema": json.dumps(schema, default=repr, sort_keys=True),
            "instance": json.dumps(instance, default=repr, sort_keys=True),
            "raised": errors[0],
        }
    out = []
    for e in errors:
        out.append(
            {
                "validator": e.validator,
                "validator_value": json.dumps(
                    e.validator_value, default=repr, sort_keys=True
                ),
                "instance": json.dumps(e.instance, default=repr, sort_keys=True),
                "message": e.message,
                "path": [str(p) for p in e.path],
                "schema_path": [str(p) for p in e.schema_path],
                "context": len(e.context),
            }
        )
    return {
        "run": run_index,
        "schema": json.dumps(schema, default=repr, sort_keys=True),
        "instance": json.dumps(instance, default=repr, sort_keys=True),
        "n_errors": len(errors),
        "errors": out,
    }


def main():
    from jsonschema.validators import Draft202012Validator

    corpus = json.load(open(CORPUS))
    golden = json.load(open(GOLDEN))
    assert len(corpus) >= 1000, "corpus too small"

    def validate(schema, instance):
        try:
            errors = list(Draft202012Validator(schema).iter_errors(instance))
            return errors
        except Exception as exc:
            return [f"RAISED:{type(exc).__name__}:{exc}"]

    n_identical = 0
    n_diff = 0
    failures = []
    for idx, (schema, instance) in enumerate(corpus):
        errors = validate(schema, instance)
        res = serialize_error(idx, schema, instance, errors)
        ref = golden[idx]
        if json.dumps(res, sort_keys=True) == json.dumps(ref, sort_keys=True):
            n_identical += 1
        else:
            n_diff += 1
            if len(failures) < 5:
                failures.append((idx, res, ref))

    print(f"diff cases: {len(corpus)}  identical: {n_identical}  different: {n_diff}")
    assert len(corpus) >= 1000, "must run >=1000 groups"
    for idx, res, ref in failures:
        print(f"FAIL case {idx}:\n  got {json.dumps(res, sort_keys=True)[:300]}\n  want {json.dumps(ref, sort_keys=True)[:300]}")
    assert n_diff == 0, f"G2 FAILED: {n_diff} byte differences out of {len(corpus)}"
    print("G2 PASS: all", len(corpus), "groups byte-identical")


if __name__ == "__main__":
    main()