# 项目完整 Pipeline 映射（2026-05-22）

本文档为首次深度代码探索的结果，覆盖 ASIP Evidence Workbench 的核心数据流。

---

## 1. 整体数据流（端到端）

```
源代码/文档/PDF
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                    Indexing                          │
│  (workbench.py: index_configured_corpora)           │
│                                                     │
│  1. scan_corpora() → 列出所有 corpus 源文件          │
│  2. index_chunks() → 切分成 chunks（80行 code/40行 doc）│
│  3. _index_chunk_evidence() → 用 resolver profile   │
│     提取 symbol、entity_type、access_type、confidence   │
│  4. _index_chunk_embedding() → 生成向量嵌入          │
│  5. 写入 SQLite：chunks / evidence / embeddings 表   │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              Deterministic Graph                     │
│  (storage.py: AsipStore)                             │
│                                                     │
│  1. evidence 行 → add_edge() 写入 edges 表           │
│  2. _kind_for_graph_evidence() → 确定 node kind     │
│  3. 关系：reads/writes/sets_field/maps_base/calls   │
│  4. 写入 edges 表，stage='deterministic'             │
│  5. global_graph_networkx() / expand_graph_networkx()│
│     → 用 NetworkX 构建图 → 序列化为 JSON              │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              Semantic Graph (LLM 生成)                │
│                                                      │
│  ┌─ Semantic Edges ──────────────────────────┐      │
│  │ 1. _semantic_edge_batch_candidates()       │      │
│  │    → 从 evidence 表选候选                   │      │
│  │    → _augment..._with_graph_context()      │      │
│  │      → 从 deterministic edges 取邻近关系    │      │
│  │ 2. _semantic_edge_batch_prompt() → LLM     │      │
│  │ 3. OllamaEdgeProvider /                    │      │
│  │    OpenAICompatibleEdgeProvider 生成        │      │
│  │ 4. _persist_generated_edges() 写入 edges    │      │
│  │    stage='semantic', source='llm'           │      │
│  └────────────────────────────────────────────┘      │
│                                                      │
│  ┌─ Doc Nodes (BoxMatrix) ──────────────────┐      │
│  │ 1. generate_doc_nodes_batch()             │      │
│  │    → 从 evidence 表选 doc chunk 候选       │      │
│  │ 2. _doc_node_batch_prompt() → LLM          │      │
│  │    Schema: documents[].boxes[].relationships│      │
│  │ 3. OllamaDocNodeProvider /                 │      │
│    OpenAICompatibleDocNodeProvider 生成        │      │
│  │ 4. _persist_doc_nodes() 写入 edges          │      │
│  │    → 节点 id: path#box-{slug}              │      │
│      → 关系: contains_box / 自定义关系         │      │
│  └────────────────────────────────────────────┘      │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│               Graph 导出 (输出 JSON)                   │
│                                                      │
│  三种视图：                                           │
│  ┌─ global_graph() ──────────────────────────┐      │
│  │ store.global_graph_networkx(limit, ...)    │      │
│  │ → 用 NetworkX 构建全局图投影                │      │
│  │ → 受 edge_budget / evidence_row_cap 限制   │      │
│  │ → 输出 {nodes, edges, source, runtime}     │      │
│  └────────────────────────────────────────────┘      │
│                                                      │
│  ┌─ expand_query_graph(symbol) ─────────────┐      │
│  │ store.expand_graph_networkx(seed, hops)   │      │
│  │ → 以某个符号为中心 hops 跳跃展开            │      │
│  │ → 受 default_hops 限制                     │      │
│  └────────────────────────────────────────────┘      │
│                                                      │
│  ┌─ graph_for_rows(rows) ────────────────────┐      │
│  │ store.expand_graph_networkx_many(seeds)    │      │
│  │ + section_overlay_graph_for_evidence_rows()│      │
│  │ → 搜索结果行关联图                          │      │
│  └────────────────────────────────────────────┘      │
│                                                      │
│  JSON 输出到 stdout（CLI graph 命令）                 │
│  由外部脚本重定向到 /tmp/asip-graph-data.json          │
└──────────────────────────────────────────────────────┘
```

---

## 2. 图节点分类体系

### 2.1 `product_endpoint_kind()` — 产品图分类核心
**文件**: `graph_schema.py:106-133`

决定符号是 `function`/`register`/`doc`/`None`(被过滤)

| 输入模式 | 分类结果 | 示例 |
|----------|----------|------|
| `:doc:xxx` / `:fn:xxx` / `:reg:xxx` | doc / function / register | `:fn:gfx_v9_0_init` |
| `path#ext` + `.md/.rst/.txt/.pdf` | doc | `docs/guide.md#section` |
| `regXXX` / `mmXXX` / `smnXXX` (len>3) | register | `regSCRATCH_RAM_BASE` |
| ALL_CAPS + 含 CNTL/CTRL/STATUS/BASE/RESET | register | `CONTROL_PWR_MGMT` |
| 含下划线 + 非全大写 | function | `gfx_v9_0_do_xxx()` |
| wrapper 名称 / 局部变量 | None（过滤） | 各种 helper/provider 名 |

### 2.2 `_kind_for_graph_symbol()` — 存储层宽分类
**文件**: `storage.py:3403-3425`

| 输入特征 | 结果 |
|----------|------|
| `box-`前缀 + `.md/.rst/.txt/.pdf`路径 | `doc_box` |
| `.md/.rst/.txt#` 路径 | `doc_section` |
| `.pdf#` 路径 | `pdf_section` |
| `.md/.rst/.txt` 结尾 | `doc` |
| `.pdf` 结尾 | `pdf` |
| 含 ENABLE/DISABLE/MASK/SHIFT/FIELD | `field` |
| `CP_HQD_` 前缀 | `register` |
| 含 CNTL/CONTROL/STATUS/RESET/BASE/SIZE/VMID/DOORBELL/QUEUE/REGISTER | `register` |
| `reg`/`mm`/`smn` 前缀 + 大写后续 | `register` |
| 其他 | `code` |

### 2.3 `_kind_for_graph_evidence()` — 证据行分类组合
**文件**: `storage.py:3439-3445`

```
if entity_type ∈ {register, field, macro, context} → 直接使用 entity_type
else → _kind_for_graph_symbol(symbol)
         if != "code" → 使用推断结果
         else → source_type 归一化
```

---

## 3. Resolver Profile 体系

**文件**: `resolver_profiles.py`（584行完整文件）

### 3.1 配置结构（YAML → dataclass）

```
ResolverProfile
├── id, language, aliases
├── wrappers: Dict[str, WrapperRule]
│   ├── symbol_arg: int        # 第几个参数是符号
│   ├── access: str            # read/write/field_set/...
│   └── symbol_args: tuple     # 多个参数位置
├── symbol_prefixes: List[str] # reg/mm/smn 等前缀（自动剥离）
├── context_vars: List[str]
├── python_extractors: List[str]  # Python 提取器函数名
└── graph: GraphNormalizationConfig
    ├── function_normalization
    │   ├── enabled: bool
    │   └── rules: List[{
    │       id, match(regex), canonical(归一化名),
    │       merge_policy: {mode, warn_register_overlap_below, split_register_overlap_below}
    │   }]
    ├── register_normalization
    │   └── {identity, merge_across_repos...}
    └── access_relation_map: Dict[str, str]
```

### 3.2 符号提取流程

```
resolve_cpp_register_calls(source, profile)
→ _iter_configured_cpp_calls()
  → 正则匹配 profile.wrappers 中的函数名
  → 递归解析嵌套调用
→ 对每个参数位：
  → _symbols_for_argument()
    → 1. 递归解析嵌套调用
    → 2. _prefixed_symbols_in_expression() （匹配 symbol_prefixes）
    → 3. _fallback_symbol_for_argument() （纯字母大写保留）
```

### 3.3 函数归一化规则

当 `function_view="concept"` 时：
- `match` 是正则，匹配的函数名被归类到 `canonical` 概念名
- 所有匹配同一 canonical 的函数节点在图中合并为一个概念节点
- `merge_policy.mode = "concept_with_implementations"` 表示保留实现列表
- 图节点 attr 中会包含 `implementations` 数组

### 3.4 Profile 加载

- 从 `configs/resolvers/*.yaml` 加载
- 也可以从 Web UI 内联配置（通过 `add_resolver_profile()`）
- 验证：`validate_resolver_profile()` 实际解析一个源文件并返回符号列表

---

## 4. Semantic Edges（语义边）

**文件**: `semantic_edges.py`（1187行）

### 4.1 Provider 层级

```
EdgeProvider (Protocol)
├── FakeEdgeProvider        # 测试用，确定性
├── OllamaEdgeProvider      # Ollama /api/chat
│   └── OllamaDocNodeProvider  # BoxMatrix 提取（不同 system prompt）
├── OpenAICompatibleEdgeProvider  # OpenAI /v1/chat/completions
│   └── OpenAICompatibleDocNodeProvider  # BoxMatrix 提取
```

### 4.2 工厂函数

```python
create_edge_provider(model)     # → Semantic Edge 生成
create_doc_node_provider(model) # → BoxMatrix 文档节点提取
```

### 4.3 Semantic Edge Prompt

System prompt 指令：
- JSON-only, 无 markdown fences
- 保留精确的 C 标识符
- src/dst 必须是 function/register/doc 标识符（非路径、字段、helper）
- 每个 TERMS 标识符必须在至少一条边中出现
- 每条 case 最多 6 条边
- evidence 不超过 12 词

### 4.4 Doc Node (BoxMatrix) Prompt

System prompt 指令：
- Box = 自包含的概念/需求/寄存器行为/工作流/约束
- Matrix = box 与索引硬件符号的关系网络
- 每个文档最多一个 box、一个 relationship
- fields/enum values 放在 box inputs/outputs/constraints 中
- 关系端点来自 LINKED SYMBOLS

#### 4.4.1 Doc Node 持久化

`_persist_doc_nodes()` (workbench.py:2720):
1. 遍历每个 document.boxes[]
2. 为每个 box 创建 `doc_box` 节点（`path#box-{slug}`）
3. 写入 `document → contains_box → box_node` 边（semantic stage）
4. 遍历 relationships[] → 写入自定义关系边
5. provenance 中包含：extractor=doc_nodes, box_id, box_name, summary, inputs, outputs, constraints, evidence

---

## 5. 图 JSON 导出路径

JSON 输出不直接写入文件，而是由 **CLI `graph` 命令** `print(json.dumps(...))` 输出到 stdout，外部脚本重定向到 `/tmp/asip-graph-data.json`。

### graph-data-gate.sh 验证 7 项

| 检查 | 阈值 | 描述 |
|------|------|------|
| 节点数量 | ≥ 100 | 总节点数 |
| Kind 合法性 | 0 非法 | kind ∈ {function, register, doc} |
| 分类正确性 | 0 错误 | function 不能全大写，register 必须有下划线 |
| 边语义 | 0 违规 | reads/writes/sets_field/maps_base → function→register |
| Box 完整性 | 0 缺失 | boxmatrix_box 必须有 inputs/outputs/constraints |
| 边数量 | ≥ 10 | 总边数 |
| Kind 覆盖率 | 3种都有 | function + register + doc |

---

## 6. 关键文件与函数索引

| 文件 | 关键函数 | 行号 | 作用 |
|------|---------|------|------|
| `graph_schema.py` | `product_endpoint_kind()` | 106 | **产品图分类核心** |
| `graph_schema.py` | `is_graph_entity_endpoint()` | 80 | 是否可作图节点 |
| `graph_schema.py` | `ALLOWED_PRODUCT_RELATIONS` | 15 | 允许的关系名集合 |
| `storage.py` | `_kind_for_graph_symbol()` | 3403 | 存储层宽分类 |
| `storage.py` | `_kind_for_graph_evidence()` | 3439 | 证据行分类组合 |
| `storage.py` | `global_graph_networkx()` | 1532 | NetworkX 全局图构建 |
| `storage.py` | `expand_graph_networkx()` | 1272 | NetworkX 展开图构建 |
| `storage.py` | `add_edge()` | ~1970 | 写入边到 SQLite |
| `workbench.py` | `global_graph()` | 820 | 全局图 API |
| `workbench.py` | `expand_query_graph()` | 764 | 展开图 API |
| `workbench.py` | `graph_for_rows()` | 865 | 搜索关联图 |
| `workbench.py` | `generate_doc_nodes_batch()` | 1995 | BoxMatrix 批量提取 |
| `workbench.py` | `_doc_node_batch_prompt()` | 2689 | BoxMatrix LLM prompt |
| `workbench.py` | `_persist_doc_nodes()` | 2720 | BoxMatrix 结果持久化 |
| `workbench.py` | `_semantic_edge_batch_candidates()` | 2443 | 语义边候选选取 |
| `workbench.py` | `_semantic_edge_batch_prompt()` | 2568 | 语义边 LLM prompt |
| `workbench.py` | `_persist_generated_edges()` | 2841 | 语义边结果持久化 |
| `workbench.py` | `_graph_node_payload()` | 4236 | 图节点 JSON 序列化 |
| `resolver_profiles.py` | `ResolverProfile` dataclass | 65 | Profile 数据类 |
| `resolver_profiles.py` | `resolver_profile_from_config()` | 103 | YAML→Profile |
| `resolver_profiles.py` | `resolve_cpp_register_calls()` | 157 | C++ 符号提取 |
| `semantic_edges.py` | `create_edge_provider()` | 292 | Edge provider 工厂 |
| `semantic_edges.py` | `create_doc_node_provider()` | 301 | Doc provider 工厂 |
| `semantic_edges.py` | `run_full_corpus_generation()` | 754 | 全 corpus 语义边生成 |
| `docs/qa/graph-data-gate.sh` | — | 全文件 | 7 项图数据完整性检查 |

---

## 7. 数据流向图（SQLite 表）

```
corpora ──────────────────────────────────────────┐
     │                                            │
     ├─── sources ──→ chunks ──→ evidence         │
     │                      ├──→ embeddings        │
     │                      └──→ edges (deterministic)│
     │                                            │
     ├─── resolver_profiles                       │
     └─── indexing_jobs                           │
                                                  │
edges 表的关键字段：
  - src / dst / relation
  - stage: 'deterministic' | 'semantic'
  - source: 'extractor' | 'llm'
  - provenance_json: extractor, evidence, case_id, box_id, ...
  - confidence: float
  - path / line_start / line_end
```

---

## 8. 关键观察

1. **区分两个分类系统**：`product_endpoint_kind()` 用于产品图节点显示（严格过滤），`_kind_for_graph_symbol()` 用于存储层宽分类（更宽松），前者被后者回调引用。

2. **两阶段图构建**：deterministic（从 evidence 自动提取）→ semantic（LLM 生成的边和 BoxMatrix doc 节点），stage 字段区分，UI 中可以独立过滤和计数。

3. **function_view 概念/实现**：概念模式用 resolver profile 归一化函数名，实现模式显示原始函数名；概念节点属性中保留 `implementations` 数组。

4. **四层 Provider**：Ollama vs OpenAI-compatible × Semantic Edges vs Doc Nodes = 4 种组合。

5. **/tmp/asip-graph-data.json 不是由代码直接写入的**，而是 CLI stdout 重定向，或由 `docs/qa/graph-data-gate.sh` 作为输入引用。

6. **BoxMatrix doc 节点** 以 `path#box-{slug}` 为 ID，存储在 edges 表中但实际上是特殊的 doc 节点（`doc_box` kind），通过 `contains_box` 边与文档关联。

7. **安全阀**：`_semantic_edge_provider_guard` 检查 edges 表是否有 deterministic 数据，没有则不执行语义边生成。
