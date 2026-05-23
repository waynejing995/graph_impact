#!/usr/bin/env bash
# =============================================================================
# graph-data-gate.sh — Pre-ship graph data integrity gate
#
# Reads an ASIP graph-data JSON file and runs a battery of structural
# and semantic validation checks. Prints a PASS/FAIL JSON result to
# stdout and returns exit code 0 (pass) or 1 (fail).
#
# Usage:
#   bash docs/qa/graph-data-gate.sh [path-to-graph-data.json]
#   Default: /tmp/asip-graph-data.json
# =============================================================================
set -euo pipefail

FPATH="${1:-/tmp/asip-graph-data.json}"
CHECKS=()
ALL_PASSED=true

# ── helpers ──────────────────────────────────────────────────────────────────
pass() { CHECKS+=("$(printf '{"name":"%s","passed":true,"detail":"%s"}' "$1" "$2")"); }
fail() { CHECKS+=("$(printf '{"name":"%s","passed":false,"detail":"%s"}' "$1" "$2")"); ALL_PASSED=false; }
detail_escape() { python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))"; }

# ── 0. File existence ────────────────────────────────────────────────────────
if [ ! -f "$FPATH" ]; then
  fail "file-exists" "File not found: $FPATH"
  echo '{"gate":"graph-data-integrity","timestamp":"'"$(date -Iseconds)"'","passed":false,"checks":[{"name":"file-exists","passed":false,"detail":"File not found"}],"summary":"File not found"}'
  exit 1
fi

# Counters
N_NODES=0
N_EDGES=0
N_FUNC=0
N_REG=0
N_DOC=0

# ── 1. Node count check ──────────────────────────────────────────────────────
node_count_block=$(python3 -c "
import json
with open('$FPATH') as f:
    data = json.load(f)
nodes = data.get('nodes', [])
edges = data.get('edges', [])
nk = {'function':0,'register':0,'doc':0}
for n in nodes:
    k = n.get('kind','')
    if k in nk: nk[k] += 1
print(f'{len(nodes)},{len(edges)},{nk[\"function\"]},{nk[\"register\"]},{nk[\"doc\"]}')
")
IFS=',' read -r N_NODES N_EDGES N_FUNC N_REG N_DOC <<< "$node_count_block"

if [ "$N_NODES" -ge 100 ]; then
  pass "node-count" "$N_NODES nodes found (func=$N_FUNC reg=$N_REG doc=$N_DOC)"
else
  fail "node-count" "Only $N_NODES nodes (min 100 required)"
fi

# ── 2. Kind validity check ───────────────────────────────────────────────────
kind_check=$(python3 -c "
import json
with open('$FPATH') as f:
    data = json.load(f)
bad_kinds = set()
for n in data.get('nodes', []):
    k = n.get('kind','')
    if k not in ('function','register','doc'):
        bad_kinds.add(k)
if bad_kinds:
    print('FAIL:' + ','.join(bad_kinds))
else:
    print('PASS')
")
if [ "$kind_check" = "PASS" ]; then
  pass "kind-validity" "all node kinds in [function, register, doc]"
else
  fail "kind-validity" "invalid kinds: ${kind_check#FAIL:}"
fi

# ── 3. Node classification check ─────────────────────────────────────────────
class_check=$(python3 -c "
import json
with open('$FPATH') as f:
    data = json.load(f)
issues = []
for n in data.get('nodes', []):
    kind = n.get('kind','')
    label = n.get('label','')
    # function nodes should NOT have ALL_CAPS labels
    if kind == 'function' and label.isupper() and len(label) > 1:
        issues.append(f'FUNC_ALL_CAPS:{n[\"id\"]}')
    # register nodes should NOT be single-word (likely misclass)
    if kind == 'register':
        if '_' not in label and ' ' not in label and len(label) > 1:
            issues.append(f'REG_SINGLE_WORD:{n[\"id\"]}')
if issues:
    print('FAIL:' + '|'.join(issues))
else:
    print('PASS')
")
if [ "$class_check" = "PASS" ]; then
  pass "node-classification" "no misclassification errors"
else
  issues="${class_check#FAIL:}"
  count=$(echo "$issues" | tr '|' '\n' | wc -l | tr -d ' ')
  fail "node-classification" "$count classification issues: $issues"
fi

# ── 4. Edge semantic check ───────────────────────────────────────────────────
edge_check=$(python3 -c "
import json
with open('$FPATH') as f:
    data = json.load(f)
# Build node kind lookup
nk = {}
for n in data.get('nodes', []):
    nk[n['id']] = n.get('kind', 'unknown')

# Expected relation→(src_kind,dst_kind) mappings
func_to_reg = {'reads','writes','sets_field','maps_base'}
func_to_func = {'calls'}
doc_to_doc   = {'contains'}

violations = []
for e in data.get('edges', []):
    rel = e.get('relation','?')
    src = e.get('src','')
    dst = e.get('dst','')
    sk = nk.get(src, 'unknown')
    dk = nk.get(dst, 'unknown')

    # skip 'relates_to' which we don't validate directionally
    if rel in ('relates_to',):
        continue

    if rel in func_to_reg:
        if sk != 'function' or dk != 'register':
            violations.append(f'{rel}:{src}->{dst} (src={sk} dst={dk})')
    elif rel in func_to_func:
        if sk != 'function' or dk != 'function':
            violations.append(f'{rel}:{src}->{dst} (src={sk} dst={dk})')
    elif rel in doc_to_doc:
        if sk != 'doc' or dk != 'doc':
            violations.append(f'{rel}:{src}->{dst} (src={sk} dst={dk})')
    else:
        # Unknown relation type
        violations.append(f'unknown_rel:{rel}:{src}->{dst}')

if violations:
    print('FAIL:' + str(len(violations)))
    # Print first 5 for detail
    for v in violations[:5]:
        print('V:' + v)
else:
    print('PASS')
")
if [ "$(echo "$edge_check" | head -1)" = "PASS" ]; then
  pass "edge-semantic" "all edges follow expected src/dst kind patterns"
else
  nviolations=$(echo "$edge_check" | head -1 | sed 's/FAIL://')
  # Gather first few violation details
  vdetails=$(echo "$edge_check" | grep '^V:' | head -3 | sed 's/^V://' | paste -sd '; ' -)
  fail "edge-semantic" "$nviolations semantic violations (e.g. $vdetails)"
fi

# ── 5. Doc node completeness (boxmatrix_box) ─────────────────────────────────
doc_check=$(python3 -c "
import json
with open('$FPATH') as f:
    data = json.load(f)
missing = []
for n in data.get('nodes', []):
    if n.get('kind') == 'doc' and n.get('attr',{}).get('doc_kind') == 'boxmatrix_box':
        attr = n.get('attr', {})
        for field in ('inputs','outputs','constraints'):
            if field not in attr:
                missing.append(f'{n[\"id\"]}:{field}')
if missing:
    print('FAIL:' + '|'.join(missing))
else:
    print('PASS')
")
if [ "$(echo "$doc_check" | head -1)" = "PASS" ]; then
  pass "doc-completeness" "all boxmatrix_box nodes have inputs, outputs, constraints"
else
  n_missing=$(echo "$doc_check" | head -1 | sed 's/FAIL://' | tr '|' '\n' | wc -l | tr -d ' ')
  missing_list=$(echo "$doc_check" | head -1 | sed 's/FAIL://')
  fail "doc-completeness" "$n_missing missing fields in boxmatrix_box nodes: $missing_list"
fi

# ── 6. Edge count check ──────────────────────────────────────────────────────
if [ "$N_EDGES" -ge 10 ]; then
  pass "edge-count" "$N_EDGES edges found"
else
  fail "edge-count" "Only $N_EDGES edges (min 10 required)"
fi

# ── 7. Kind presence check ───────────────────────────────────────────────────
kind_presence_block=$(python3 -c "
import json
with open('$FPATH') as f:
    data = json.load(f)
kinds = set(n.get('kind','') for n in data.get('nodes',[]))
missing = []
for k in ('function','register','doc'):
    if k not in kinds:
        missing.append(k)
if missing:
    print('FAIL:' + ','.join(missing))
else:
    print('PASS')
")
if [ "$kind_presence_block" = "PASS" ]; then
  pass "kind-presence" "at least one node of each kind (function, register, doc)"
else
  missing="${kind_presence_block#FAIL:}"
  fail "kind-presence" "missing node kind(s): $missing"
fi

# ── Assemble output ──────────────────────────────────────────────────────────
CHECKS_JSON="["
sep=""
for c in "${CHECKS[@]}"; do
  CHECKS_JSON+="$sep$c"
  sep=","
done
CHECKS_JSON+="]"

N_FAIL=0
for c in "${CHECKS[@]}"; do
  if echo "$c" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); exit(0 if d.get('passed') else 1)" 2>/dev/null; then
    :
  else
    N_FAIL=$((N_FAIL + 1))
  fi
done

if $ALL_PASSED; then
  SUMMARY="All checks passed"
else
  SUMMARY="$N_FAIL check(s) failed"
fi

cat <<OUT
{
  "gate": "graph-data-integrity",
  "timestamp": "$(date -Iseconds)",
  "passed": $ALL_PASSED,
  "checks": $CHECKS_JSON,
  "summary": "$SUMMARY"
}
OUT

if $ALL_PASSED; then
  exit 0
else
  exit 1
fi
