# jsonschema-opt-lab

**python-jsonschema/jsonschema** is the de-facto JSON Schema validator for Python (11.9k★). This lab
removes a real, measurable inefficiency in its **array validation hot path**: for every element of an
array, `Validator.descend()` was rebuilding a **brand-new Validator** (and its
sub-resource resolver) from scratch, even when descending into the **same subschema** dozens/hundreds of
times in a row. This patch caches those per-sub-schema evolved validators, so repeated `descend` into a
plain sub-schema reuses one object instead of reconstructing one per element.

Upstream: https://github.com/python-jsonschema/jsonschema

## Measured speedup

Median across 3 scales: **1.281x** on a realistic "validate a page of API records" workload
(`time.perf_counter()`, 7 samples, 3 warmups, median + p25/p75, RSD < 1.5% at all scales).

| Scale | n (records) | Baseline median (s) | Optimized median (s) | Speedup | RSD |
| ----- | ----------- | ------------------- | -------------------- | ------- | --- |
| small | 500   | 0.02975 | 0.02322 | **1.281x** | 1.60% / 0.48% |
| medium| 2000  | 0.12017 | 0.09451 | **1.271x** | 0.88% / 1.07% |
| large | 8000  | 0.48649 | 0.37647 | **1.292x** | 1.14% / 3.63% |

## Differential correctness

1196 input groups (deterministic corpus of hand-built + randomized schemas/instances, including empty,
single-element, maxItems violations, non-ASCII strings, `$ref`/`$defs`, `oneOf/anyOf/allOf`, nested
arrays of objects) were run through **baseline** and **optimized** code. Full error sets (validator,
value, instance, message, path, schema_path) were serialized with `json.dumps(sort_keys=True)` and
compared **byte-for-byte**: **1196/1196 identical, 0 differences**.

## Quality gates

- **G1 — upstream tests green**: `cd jsonschema && python3 -m pytest jsonschema/tests -q -p no:cacheprovider`
  → `7682 passed, 847 skipped, 0 failed`.
- **G2 — differential identical (≥1000 groups, 0 diff)**: `python3 tests/test_diff.py`
  → `1196 identical, 0 different`.
- **G3 — median speedup ≥1.15x**: **1.281x** ✓.
- **G4 — large scale no regression (≥0.95x)**: large **1.292x** ✓.
- **G5 — memory not worse (≤1.10x peak RSS)**: baseline 26,232 KB → optimized 25,208 KB
  (ratio **0.96x**) at large scale, `/usr/bin/time -v`. ✓

### Reproduce

The patched source is vendored under `src/`; `tests/test_diff.py` and `benchmark/bench.py`
import it automatically. (The only external dependency is `jsonschema`'s own runtime deps,
installed via `pip install jsonschema pytest`.)

```bash
# 1. differential test: 1196 groups, byte-for-byte vs the upstream golden
python3 tests/test_diff.py

# 2. optimized benchmark (uses vendored patched src/)
python3 benchmark/bench.py --scale large --samples 7 --warmup 3 --output benchmark/raw/optimized-large.json

# 3. baseline benchmark: check out the unpatched base commit and pass --baseline
git clone --depth=1 git@github.com:python-jsonschema/jsonschema.git /tmp/js-upstream
# the shallow clone tip is base commit c497561e
cd /tmp/js-upstream && pip install -e . && cd -
python3 benchmark/bench.py --baseline --scale large --samples 7 --warmup 3 --output benchmark/raw/baseline-large.json

# 4. apply the patch to a clean upstream clone and rerun its tests
git apply --check patch.diff
cd jsonschema && git apply ../patch.diff && python3 -m pytest jsonschema/tests -q -p no:cacheprovider
```

## Environment

- CPU: AMD EPYC 7K62 48-Core (4 vCPU, x86_64)
- Memory: 3.6 GiB total
- OS: Linux 6.8.0-124-generic (glibc 2.39)
- Python: 3.12.3
- Seed: deterministic workload (records built linearly), no randomness

## 本轮创新

jsonschema 的 `descend()` 是为**数组里每个元素**重建一个全新 `Validator`（含 `in_subresource`
resolver 构造）——这是它每天验证 API 数组响应时的真实热路径，而子 schema 对象通常是同一批复用
的。此前没有人把「连续 descend 同子 schema」当成可缓存数据点做过量化的重复构造消除：绑定
`id(schema)` 的按身份缓存，只有当目标 sub-schema 不含任何 `$`-开头（`$ref/$id/$anchor`）关键字的
"plain" dict 时才启用，避免改变引用解析语义。在 7682 项上游测试 + 1196 项字节级差分都全绿的前提
下，得到中位 **1.281x**、大/中/小三档均值的可复现加速。与台账中「纯换 README / 单行换皮」的
C 挡不同，这是对真实验证热路径的重复构造消除，并给出可复核的性能与差分数字（B 档）。