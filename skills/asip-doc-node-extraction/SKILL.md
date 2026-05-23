---
name: asip-doc-node-extraction
description: Use when writing or reviewing BoxMatrix-style doc node extraction prompts for the ASIP document graph pipeline. Defines exact rules for extracting each attribute (name, summary, inputs, outputs, constraints, evidence, confidence, relationships) from document text.
---

# ASIP Doc Node Extraction Rules

## Overview

Each document chunk is sent to an LLM to extract **boxes** (self-contained hardware concepts,
register behaviors, workflows, constraints) and **relationships** (links between boxes and
indexed symbols). Every box has 7 attributes. This skill defines exactly what goes into each.

## Schema

```json
{
  "documents": [
    {
      "id": "<exact document candidate id>",
      "boxes": [
        {
          "id": "<unique box id within this document>",
          "name": "<short label>",
          "summary": "<1-3 sentence description>",
          "inputs": ["<trigger condition / incoming data>"],
          "outputs": ["<emitted signal / side-effect>"],
          "constraints": ["<latency / ordering / precondition>"],
          "confidence": 0.0-1.0,
          "evidence": "<source text excerpt proving the box>"
        }
      ],
      "relationships": [
        {
          "src": "<box id or linked symbol>",
          "relation": "reads|writes|calls|sets_field|maps_base|triggers|depends_on|reports_on|contains",
          "dst": "<box id or linked symbol>",
          "confidence": 0.0-1.0,
          "evidence": "<source text excerpt proving the edge>"
        }
      ]
    }
  ]
}
```

---

## Attribute: `name`

**Purpose**: Short human-readable label (3-8 words max).

**Extraction rule by document type**:

| Document type | name strategy | Example |
|---|---|---|
| **Register definition** (`#define REG_NAME field_mask`) | `"{REG_NAME} register fields"` | `"IH_RB_CNTL control register"` |
| **Register access function** (RREG32/WREG32 call sites) | `"{function_name} register access"` | `"mi200_ih_iv_ring_hw_init RB_CNTL access"` |
| **C enum** (`enum Foo { A, B, C }`) | `"{EnumTypeName} enumeration values"` | `"AmdSmiEventCategoryReset enumeration"` |
| **API function doc** (with Input/Output sections) | `"{function_name} API"` | `"amdsmi_get_gpu_metrics API"` |
| **API event/error category list** (category table) | `"{CategoryName} event category"` | `"RESET Event Category"` |
| **Hardware IP block description** | `"{IP_name} hardware block"` | `"NBIO v7_4 doorbell interface"` |
| **Telemetry/metric enum** | `"{MetricGroup} metric group"` | `"AmdSmiMetricUnit measurement units"` |
| **Workflow/procedure** (multi-step process) | `"{workflow name} workflow"` | `"GPU reset sequence"` |
| **Constraint/latency spec** | `"{spec name} constraint"` | `"MMSCH firmware timeout constraint"` |

**Rules**:
- Capitalize as a title (not ALL_CAPS unless the source convention demands it).
- Do not use file paths, line numbers, or chunk IDs as names.
- If the text has no clear concept boundary, use a descriptive noun phrase from the text.

---

## Attribute: `summary`

**Purpose**: 1-3 sentences capturing **what this box is** from the source text. No extrapolation.

**Extraction rule**: Take the nearest descriptive sentence, paragraph header, or table caption
that introduces the concept. Do not infer purpose that isn't stated.

**Examples**:

| Source text type | Acceptable summary | Not acceptable |
|---|---|---|
| `RESET | events/notifications regarding RESET executed by the GPU` | "Events/notifications regarding RESET executed by the GPU." | "Fires when a GPU reset is triggered." (adds unstated causal model) |
| `enum AmdSmiEventCategoryReset { RESET_GPU, ... }` | "Enumeration for reset event categories." | "Categories of reset events that can occur during GPU operation." (vague) |
| `Input parameters: processor handle` / `Output: Dictionary` | "Gets GPU metric information." (from "Description: Gets GPU metric information") | "Queries GPU performance counters." (extrapolation) |
| `#define IH_RB_CNTL 0x1234` with comment | "Interrupt ring buffer control register at offset 0x1234." | "Controls the interrupt ring buffer." (if the text doesn't say "controls") |

**Rules**:
- Prefer verbatim or near-verbatim text from the source.
- Do not add causal explanations ("this triggers that") unless the source text states the causality.
- If the text is a bare list/table with no explanatory paragraph, summarize what the table enumerates.

---

## Attribute: `inputs`

**Purpose**: Conditions, data, or triggers that **flow into** this concept to make it active or
produce a result. Hardware: register writes, doorbell rings, DMA descriptors, firmware
commands, function call parameters. Software: API input parameters, callback arguments.

**Extraction rule by document type**:

| Document type | What goes in `inputs` | Example |
|---|---|---|
| **Register field definition** | The field's bit range, write value, or the condition that sets it. | `"ENABLE_L2_CACHE=1"`, `"PENDING=0x2"` |
| **Function/code snippet** (RREG32/WREG32) | The register being **read** before write, or the input parameter. | `"Reads IH_RB_CNTL current value"` |
| **API function doc** with `Input parameters:` section | Each parameter listed under Input parameters. | `"processor handle: PF of a GPU device"`, `"severity_mask: AmdSmiCperErrorSeverity"` |
| **Hardware event/error** | The trigger condition (what causes this event) | `"GPU device lost condition"`, `"VF configuration change"` |
| **Enum definition (standalone)** | Conditions under which each enum value is set. If not documented, leave empty. | `[]` |
| **Event category table** (category list) | The triggering operation category. Only if the text describes what triggers it. | `"GPU reset executed"` for RESET category |
| **Workflow/procedure** | The entry condition or prerequisite. | `"GPU in reset state", "adapter handle"` |
| **Firmware/PHY/clock config** | The register value being programmed, or the requested state. | `"Link speed = PCIE_GEN4"` |

**If the source text has no input semantics** (e.g., a bare enum value list with no trigger
description), return `[]`. Do not fabricate inputs.

---

## Attribute: `outputs`

**Purpose**: Data, signals, side-effects, or status that **this concept emits or produces**.
Hardware: interrupt status bits, DMA completion, register values read back, telemetry counters.
Software: API return values, callbacks, status enums.

**Extraction rule by document type**:

| Document type | What goes in `outputs` | Example |
|---|---|---|
| **Register field definition** | The value read from the field, or the side-effect of setting it. | `"L2_CACHE_ENABLED=1"`, `"interrupt pending"` |
| **Function/code snippet** | The register written or modified, or the return value. | `"Writes IH_RB_CNTL with ENABLE_L2_CACHE=1"` |
| **API function doc** with `Output:` section | Each field of the output dictionary or return value. | `"fb_offset: framebuffer offset"`, `"fb_size: framebuffer size"` |
| **C enum with field table** | **Each enum member** as a separate output entry. | `"RESET_GPU"`, `"RESET_GPU_FAILED"`, `"RESET_FLR"`, `"RESET_FLR_FAILED"` |
| **Event/error enum** | The emitted event identifiers. | `"GPU_DEVICE_LOST"`, `"GPU_RMA"` |
| **Metric/telemetry enum** | Each metric name as an output entry. | `"CLK_GFX: gfx clock"`, `"TEMP_HOTSPOT_CURR: current hotspot temperature"` |
| **Event category table** | Leave empty — the category itself is the bucketing mechanism, not an output. | `[]` |
| **Workflow/procedure** | The completion state or output data. | `"Reset complete"`, `"Error code returned"` |

**Key rule for enums**: When the source text has a table mapping enum names to descriptions,
put each name in outputs. This is the one case where output extraction is always expected.

---

## Attribute: `constraints`

**Purpose**: Timing, ordering, precondition, or resource limits that **restrict when/how**
this concept can be used. Latency bounds, register write ordering, power state requirements,
alignment constraints, exclusivity, timeout limits.

**Extraction rule by document type**:

| Document type | What goes in `constraints` | Example |
|---|---|---|
| **Register field with noted constraint** | Explicit timing/ordering notes from comments. | `"Must be set when LINK_INIT == 0"`, `"Write only when IDLE=1"` |
| **API function doc** | Exceptions, preconditions, or "Note:" paragraphs. | `"Only works if no guest VM is running"`, `"This API cannot be called during reset"` |
| **Firmware/Power/Clock** | Power state requirements, clock gating restrictions. | `"SOC must be in D0 state"` |
| **Procedure workflow** | Step ordering, dependencies, timeout values. | `"Step 2 must complete before Step 3"` |
| **Enum / Event / Metric** | If no explicit constraint is documented, leave empty. | `[]` |
| **Hardware IP block** | Any "must", "shall", "should", "only if" language. | `"Doorbell writes must be 8-byte aligned"` |

**Rules**:
- Only extract explicit constraints from the source text. Do not infer latent constraints.
- Prefer near-verbatim text, not rephrased rules.
- If the text says "Note: ..." or "must ...", that is a constraint.

---

## Attribute: `confidence`

**Purpose**: How certain the extraction is, based on source clarity.

**Scale**:

| Score | When to use |
|---|---|
| `0.95` | The text has a clear definition, labeled table, or explicit description. The box content is directly stated. |
| `0.85` | The text has a clear name but the boundary is somewhat implicit (e.g., an enumeration without descriptions). |
| `0.70` | The text has partial information; the box content is inferred from context rather than stated. |
| `0.55` | The text is ambiguous; the box represents a best-guess extraction. |
| `< 0.50` | Avoid extracting as a box; prefer a relationship or skip. |

**Default**: `0.88` for standard table/API doc content. Lower for inferred content.

---

## Attribute: `evidence`

**Purpose**: The exact source text line(s) that justify the box extraction. 140 chars max.

**Extraction rule**:
- Prefer a single line or short span that contains the name and key descriptive text.
- Include the line number if available from the source.
- Do not reformat the text — keep it as close to verbatim as possible.

**Examples**:

| Box name | Acceptable evidence |
|---|---|
| `RESET Event Category` | `"3203: \`RESET\` | events/notifications regarding RESET executed by the GPU"` |
| `AmdSmiEventCategoryReset` | `"3241: \`AmdSmiEventCategoryReset\` | <table>..."` (truncated) |
| `IH_RB_CNTL control register` | `"322-330: ENABLE_L2_CACHE, CONTEXT1_IDENTITY_ACCESS_MODE"` |

---

## Relationships: `src`, `relation`, `dst`, `confidence`, `evidence`

**Purpose**: Links between boxes and indexed symbols (functions, registers, other boxes).

**Relation types** (use exact strings):

| Relation | When to use |
|---|---|
| `reads` | A function reads a register value |
| `writes` | A function writes to a register |
| `sets_field` | A function sets a specific field in a register |
| `calls` | A function calls another function |
| `maps_base` | A register maps to a base address |
| `triggers` | An event triggers a workflow or state change |
| `depends_on` | A box depends on another box or symbol |
| `reports_on` | A doc/box reports information about a symbol |
| `contains` | A document section contains a box (use doc→box `contains_box`) |

**src/dst rules**:
- src must be a box id (from the same document) or a **LINKED SYMBOL** (function or register identifier).
- dst must be a box id or LINKED SYMBOL.
- **Register fields** (like `FIELD_NAME_MASK`) must NOT be used as endpoints. Put them in `inputs`/`outputs`/`constraints` instead.
- Do not use file paths, chunk IDs, or line numbers as src/dst.
- Prefer LINKED SYMBOLS from the prompt's `LINKED SYMBOLS` section. Do not invent symbols.

**Relationship extraction priority**:
1. For code snippets: `reads`/`writes`/`sets_field` between function→register.
2. For API docs with Input/Output sections: `calls` between API function and implementation.
3. For enum docs: `reports_on` between the box and the linked register/symbol it documents.
4. For hardware docs: `depends_on` or `triggers` between relevant boxes.

---

## Complete Extraction Decision Tree

When processing a document chunk, determine the chunk type first:

```
Chunk type:
├── Code (RREG32/WREG32/REG_SET_FIELD/REG_GET_FIELD calls)
│   ├── box = register access site
│   ├── inputs = register values read
│   ├── outputs = register values written
│   ├── constraints = any explicit guard conditions
│   └── relationships = reads/writes/sets_field → register symbol
│
├── C enum definition (enum Foo { A, B, C } or Field | Description table)
│   ├── box = enum type
│   ├── inputs = [] (unless trigger conditions documented)
│   ├── outputs = each enum member as a string
│   ├── constraints = [] (unless explicit notes)
│   └── relationships = reports_on → any linked symbol
│
├── API function doc (Description / Input parameters / Output sections)
│   ├── box = API function
│   ├── inputs = each Input parameter with its type + description
│   ├── outputs = each Output field with its description
│   ├── constraints = Exceptions, Notes, precondition language
│   └── relationships = calls → implementation function if linked
│
├── Event/error category table (Category | Description table)
│   ├── box = best single category with strongest description
│   ├── inputs = trigger condition (if text describes it)
│   ├── outputs = [] (category is a grouping, not an output)
│   ├── constraints = [] (rare for categories)
│   └── relationships = reports_on → any linked register/symbol
│
├── Register macro definition (#define NAME value /* comment */)
│   ├── box = register with its address and comment
│   ├── inputs = [] (or field values if described)
│   ├── outputs = [] (or field values if described in same text)
│   ├── constraints = any noted restrictions
│   └── relationships = maps_base → base address if calculable
│
├── Telemetry/metric enum (Field | Description table of counters)
│   ├── box = metric group
│   ├── inputs = [] (metrics are read-only measurements)
│   ├── outputs = each metric field name + description
│   ├── constraints = [] (unless noted)
│   └── relationships = reports_on → the register/IP it measures
│
└── Workflow/procedure (numbered steps, state machine)
    ├── box = the workflow
    ├── inputs = entry condition
    ├── outputs = completion state or result
    ├── constraints = step ordering, timeout, dependency
    └── relationships = depends_on → prerequisites
```

---

## Verification Checklist

After extraction, verify each box attribute:

- [ ] `name` ≤ 8 words, capitalized as title, no file paths
- [ ] `summary` is factual from source, no extrapolation
- [ ] `inputs` contains only trigger conditions or parameters stated in text
- [ ] `outputs` contains emitted signals, return values, or enum members
- [ ] `constraints` contains only explicit preconditions/timing/restrictions
- [ ] `confidence` matches the source clarity (0.95 for explicit, 0.70+ for inferred)
- [ ] `evidence` is verbatim or near-verbatim source text ≤ 140 chars
- [ ] Relationship src/dst uses box ids or LINKED SYMBOLS only
- [ ] Register fields are in inputs/outputs, NOT as relationship endpoints
- [ ] At most one box and one relationship per document (per current batch limits)
