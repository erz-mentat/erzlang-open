# erzlang

`erzlang` is a deterministic DSL and runtime for agent policies, event routing, and replayable evaluation.

It is built for cases where "the model decided something" is not enough.
You want:
- a compact policy language
- deterministic execution
- machine-readable traces
- strict replay and drift detection
- small, testable building blocks instead of prompt soup

## What it is

`erzlang` lets you express event-driven rules in a small DSL, then run them through a deterministic runtime.

Typical use cases:
- route incoming events to actions
- normalize or classify structured inputs
- replay fixed fixtures against a policy
- compare candidate outputs against a baseline
- gate CI with strict contracts instead of vibes

This is not a general-purpose programming language.
It is a narrow operational language for deterministic policy evaluation.

## Why it exists

A lot of agent systems still have a bad boundary between:
- probabilistic generation
- deterministic policy
- auditability

`erzlang` is an attempt to make that boundary explicit.

The core idea is simple:
- generation can stay fuzzy upstream
- policy execution should not be fuzzy downstream
- the runtime should explain what matched and why

## Current scope

Current focus:
- compact policy syntax
- canonical parse/format cycle
- deterministic `eval`
- replayable batch evaluation
- strict batch contracts
- checked-in program packs for real examples
- traceable compare / verify lanes for artifacts

Current non-goals:
- functions
- loops
- modules
- type inference
- general-purpose language expansion

## Quickstart

### 1. Install locally

```bash
python3 -m pip install -e .
```

or run directly without installation:

```bash
python3 -m cli.main --help
```

### 2. Validate and format a sample

```bash
erz validate examples/sample.erz
erz fmt examples/sample.erz
erz parse examples/sample.erz
```

### 3. Run a single policy evaluation

```bash
erz eval examples/eval/program.erz --input examples/eval/event-ok.json
erz eval examples/eval/program.erz --input examples/eval/event-ok.json --summary
```

### 4. Run a deterministic batch replay

```bash
erz eval examples/eval/program.erz --batch examples/eval/batch --summary
```

### 5. Run checked-in program packs

```bash
erz pack-replay examples/program-packs --summary
erz pack-replay examples/program-packs/dedup-cluster --summary
erz pack-replay examples/program-packs/alert-routing --summary --strict-profile alert-routing-clean
```

### 6. Run the shipped quality checks

```bash
./scripts/check.sh
```

## Small example

```erz
erz{v:1}
rl{
  id:"route_ops",
  when:["event_type_equals:incident","payload_path_equals:severity=high"],
  then:[
    {kind:"notify",params:{channel:"ops",priority:"p1"}}
  ]
}
```

Event:

```json
{
  "type": "incident",
  "payload": {
    "severity": "high"
  }
}
```

Result shape:

```json
{
  "actions": [
    {
      "kind": "notify",
      "params": {
        "channel": "ops",
        "priority": "p1"
      }
    }
  ],
  "trace": [
    {
      "rule_id": "route_ops",
      "matched_clauses": [
        "event_type_equals:incident",
        "payload_path_equals:severity=high"
      ],
      "score": 1.0
    }
  ]
}
```

## What makes it useful

### Deterministic runtime
The same supported input should produce the same output shape.
That includes normal results, trace data, and runtime error envelopes.

### Strict replay
You can freeze expected fixture sets, pack selections, batch selections, and compare outcomes.
That makes growth, shrink, selector drift, and artifact drift visible instead of silent.

### Trace by default
The runtime returns not only actions, but also why those actions happened.
That matters for debugging, CI, and operator trust.

### Program packs
The repo includes checked-in example packs that are closer to real policy work than toy parser demos:
- ingest + normalize
- dedup / cluster policy
- alert routing by thresholds

See:
- `examples/eval/README.md`
- `examples/program-packs/README.md`

## Public entry points

If you are new, start here:
- `examples/sample.erz`
- `examples/eval/program.erz`
- `examples/eval/README.md`
- `examples/program-packs/README.md`
- `scripts/check.sh`

If you care about runtime behavior and contracts:
- `docs/runtime-determinism.md`
- `docs/acceptance-metrics.md`
- `docs/calibration-v0.md`

## Repository layout

- `cli/`, command-line entrypoint
- `compact.py` + `transform.py`, parse / format / transform pipeline
- `runtime/`, deterministic evaluation runtime
- `examples/`, sample policies, eval fixtures, program packs
- `docs/`, deeper design notes and contract docs
- `scripts/`, shipped quality checks and support utilities
- `ir/` + `schema/`, canonical model and IR contract surface
- `bench/`, token-efficiency support lane and benchmark artifacts

## Status

This project is active and still evolving.
The runtime and replay lanes are already useful, but the language is intentionally narrow.
The goal is not to become a full language, but to become a reliable policy layer.

This public repository is a lean slice.
It is meant to show the runtime, examples, and operator-facing contracts without dragging along every private work log or heavy internal lane.

## Design stance

The point of `erzlang` is not to be clever.
The point is to be boring in the right places:
- deterministic
- inspectable
- replayable
- strict when needed

That is where a lot of agent systems still break.

## License

No public license has been declared yet.
Until one is added, treat the code as all rights reserved by default.
