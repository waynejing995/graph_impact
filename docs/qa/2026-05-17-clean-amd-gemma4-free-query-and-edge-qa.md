# Clean AMD Gemma4 Free Query And Graph QA

Generated: 2026-05-17T14:12:01+00:00
DB: `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db`

## Summary

- Queries: 6
- Non-empty queries: 6
- Source types seen: code, doc, pdf, register
- Global graph: nodes=2822 edges=4725 runtime=networkx elapsed_ms=686.7
- Node kinds: {"function": 1213, "register": 1609}
- Edge relations: {"maps_base": 679, "reads": 1260, "sets_field": 749, "writes": 2037}
- Edge stages: {"deterministic": 4725}
- Counts: documents=124 chunks=21884 evidence=860516 edges=10019 embeddings=32
- Provider checks: embedding=nomic-embed-text:latest semantic_edge=gemma4:e4b

## Query Results

### Who reads or writes regGCVM_L2_CNTL?

- elapsed_ms: 1306.3
- row_count: 24
- source_types: code, register
- retrieval_sources: fts5, lexical
- graph: nodes=30 edges=58 runtime=networkx
- top evidence:
  - id=10 symbol=regGCVM_L2_CNTL source=code path=libgv/core/hw/navi3/gfx_v11_0.c score=0.95
  - id=673786 symbol=regGCVM_L2_CNTL source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_offset.h score=0.95
  - id=673795 symbol=regGCVM_L2_CNTL2 source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_offset.h score=0.95
  - id=673796 symbol=regGCVM_L2_CNTL2_BASE_IDX source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_offset.h score=0.95
  - id=666234 symbol=regGCVM_L2_CNTL2_DEFAULT source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_0_default.h score=0.95

### Which fields of GCVM_L2_CNTL enable L2 cache?

- elapsed_ms: 567.7
- row_count: 24
- source_types: code, doc, register
- retrieval_sources: fts5, lexical
- graph: nodes=22 edges=34 runtime=networkx
- top evidence:
  - id=3 symbol=ENABLE_L2_CACHE source=code path=libgv/core/hw/navi3/gfx_v11_0.c score=0.95
  - id=20576 symbol=ATC_L2_CNTL2__ENABLE_L2_CACHE_LRU_UPDATE_BY_WRITE_MASK source=register path=libgv/core/hw/AI/asic_reg/mi200/GC/gc_9_0_sh_mask.h score=0.95
  - id=20525 symbol=ATC_L2_CNTL2__ENABLE_L2_CACHE_LRU_UPDATE_BY_WRITE__SHIFT source=register path=libgv/core/hw/AI/asic_reg/mi200/GC/gc_9_0_sh_mask.h score=0.95
  - id=2 symbol=ENABLE_DEFAULT_PAGE_OUT_TO_SYSTEM_MEMORY source=code path=libgv/core/hw/navi3/gfx_v11_0.c score=0.95
  - id=4 symbol=ENABLE_L2_FRAGMENT_PROCESSING source=code path=libgv/core/hw/navi3/gfx_v11_0.c score=0.95

### Where is IH_RB_CNTL configured and which fields are modified?

- elapsed_ms: 4394.0
- row_count: 24
- source_types: code, doc, register
- retrieval_sources: fts5, lexical
- graph: nodes=43 edges=82 runtime=networkx
- top evidence:
  - id=50 symbol=IH_RB_CNTL source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c score=0.95
  - id=58 symbol=ih_rb_cntl source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c score=0.95
  - id=65 symbol=ih_rb_cntl source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c score=0.95
  - id=59 symbol=mmIH_RB_CNTL source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c score=0.95
  - id=66 symbol=mmIH_RB_CNTL source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c score=0.95

### Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL?

- elapsed_ms: 276.6
- row_count: 24
- source_types: code, doc, pdf, register
- retrieval_sources: fts5, lexical
- graph: nodes=14 edges=17 runtime=networkx
- top evidence:
  - id=71 symbol=SDMA0_QUEUE0_RB_CNTL source=code path=libgv/core/hw/navi3/navi32_sdma.c score=0.95
  - id=79 symbol=SDMA1_QUEUE0_RB_CNTL source=code path=libgv/core/hw/navi3/navi32_sdma.c score=0.95
  - id=860512 symbol=AMD source=pdf path=amdgpu-driver-source-tree.pdf score=0.95
  - id=854961 symbol=BDF source=doc path=smi-lib/cli/cpp/docs/external/README.md score=0.95
  - id=477576 symbol=AFMT0_AFMT_60958_0__AFMT_60958_CS_CATEGORY_CODE_MASK source=register path=libgv/core/hw/navi3/asic_reg/navi3/DCN/dcn_3_2_0_sh_mask.h score=0.95

### Show evidence connecting amdgpu documentation to the amdgpu driver source tree.

- elapsed_ms: 1124.9
- row_count: 24
- source_types: code, doc, pdf, register
- retrieval_sources: fts5, lexical
- graph: nodes=1 edges=0 runtime=networkx
- top evidence:
  - id=83 symbol=AMDGPU_NUM_VMID source=code path=drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c score=0.95
  - id=101 symbol=AMDGPU_RING_TYPE_GFX source=code path=drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c score=0.95
  - id=128 symbol=DOCUMENTATION source=doc path=README.md score=0.95
  - id=860512 symbol=AMD source=pdf path=amdgpu-driver-source-tree.pdf score=0.95
  - id=359108 symbol=BIF_BX0_DRIVER_SCRATCH_0 source=register path=libgv/core/hw/AI/asic_reg/mi300/NBIO/nbio_7_9_0_sh_mask.h score=0.95

### Explain WREG32_SOC15 regGCVM_L2_CNTL macro expansion chain.

- elapsed_ms: 1047.4
- row_count: 24
- source_types: doc, register
- retrieval_sources: fts5, lexical
- graph: nodes=0 edges=0 runtime=networkx
- top evidence:
  - id=858348 symbol=AFID source=doc path=smi-lib/docs/reference/amdsmi_py_api.md score=0.95
  - id=377935 symbol=BIFC_A2S_CNTL_SW0__SDP_DYNAMIC_VC_WR_CHAIN_DIS_MASK source=register path=libgv/core/hw/AI/asic_reg/mi300/NBIO/nbio_7_9_0_sh_mask.h score=0.95
  - id=377898 symbol=BIFC_A2S_CNTL_SW0__SDP_DYNAMIC_VC_WR_CHAIN_DIS__SHIFT source=register path=libgv/core/hw/AI/asic_reg/mi300/NBIO/nbio_7_9_0_sh_mask.h score=0.95
  - id=377936 symbol=BIFC_A2S_CNTL_SW0__SDP_WR_CHAIN_DIS_MASK source=register path=libgv/core/hw/AI/asic_reg/mi300/NBIO/nbio_7_9_0_sh_mask.h score=0.95
  - id=377899 symbol=BIFC_A2S_CNTL_SW0__SDP_WR_CHAIN_DIS__SHIFT source=register path=libgv/core/hw/AI/asic_reg/mi300/NBIO/nbio_7_9_0_sh_mask.h score=0.95
