#!/usr/bin/env python3
"""Differential harness: run a corpus through jsonschema and serialize errors.

Used to prove the optimized patch produces byte-for-byte identical validation
results to the unpatched upstream on a large, diverse corpus.
"""
import json
import sys

import jsonschema
from jsonschema.validators import validator_for, Draft202012Validator


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
                "validator_value": json.dumps(e.validator_value, default=repr, sort_keys=True),
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
    corpus_file, out_file = sys.argv[1], sys.argv[2]
    corpus = json.load(open(corpus_file))

    def validate(schema, instance):
        # Normalize $defs/$ref-bearing schemas via a draft202012 validator.
        try:
            validator = Draft202012Validator(schema)
            errors = list(validator.iter_errors(instance))
            return errors
        except Exception as exc:  # schema or instance not usable -> record
            return [f"RAISED:{type(exc).__name__}:{exc}"]

    results = []
    for idx, (schema, instance) in enumerate(corpus):
        errors = validate(schema, instance)
        results.append(serialize_error(idx, schema, instance, errors))
    json.dump(results, open(out_file, "w"))
    print(f"wrote {len(results)} results to {out_file}")


if __name__ == "__main__":
    main()