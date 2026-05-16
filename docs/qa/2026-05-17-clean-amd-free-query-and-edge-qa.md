# Clean AMD Free Query And Semantic Edge QA

Generated: 2026-05-16T22:57:29Z
DB: `/tmp/asip-clean-amd-qwen35-provider-2026-05-17.db`

## Summary

- Queries: 6
- Non-empty queries: 6
- Source types seen: code, doc, pdf, register
- Semantic edge generated jobs: 2
- Global graph: nodes=38 edges=28 runtime=networkx elapsed_ms=0.6
- Counts: documents=124 chunks=21884 evidence=860543 edges=35 embeddings=961

## Query Results

### Who reads or writes regGCVM_L2_CNTL?

- elapsed_ms: 6226.2
- row_count: 24
- source_types: code, register
- retrieval_sources: fts5, lexical
- graph: nodes=3 edges=2 runtime=networkx
- top evidence:
  - id=14 symbol=regGCVM_L2_CNTL source=code path=libgv/core/hw/navi3/gfx_v11_0.c rank=8.95
  - id=673813 symbol=regGCVM_L2_CNTL source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_offset.h rank=6.95
  - id=673822 symbol=regGCVM_L2_CNTL2 source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_offset.h rank=6.95
  - id=673823 symbol=regGCVM_L2_CNTL2_BASE_IDX source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_offset.h rank=6.95
  - id=666261 symbol=regGCVM_L2_CNTL2_DEFAULT source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_0_default.h rank=6.95

### Which fields of GCVM_L2_CNTL enable L2 cache?

- elapsed_ms: 7643.9
- row_count: 24
- source_types: doc, register
- retrieval_sources: fts5, lexical
- graph: nodes=2 edges=1 runtime=networkx
- top evidence:
  - id=695586 symbol=GCVM_L2_CNTL__ENABLE_L2_CACHE_MASK source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_sh_mask.h rank=14.95
  - id=695587 symbol=GCVM_L2_CNTL__ENABLE_L2_CACHE__SHIFT source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_sh_mask.h rank=14.95
  - id=695590 symbol=GCVM_L2_CNTL__ENABLE_L2_PDE0_CACHE_LRU_UPDATE_BY_WRITE_MASK source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_sh_mask.h rank=14.95
  - id=695591 symbol=GCVM_L2_CNTL__ENABLE_L2_PDE0_CACHE_LRU_UPDATE_BY_WRITE__SHIFT source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_sh_mask.h rank=14.95
  - id=695592 symbol=GCVM_L2_CNTL__ENABLE_L2_PTE_CACHE_LRU_UPDATE_BY_WRITE_MASK source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_sh_mask.h rank=14.95

### Where is IH_RB_CNTL configured and which fields are modified?

- elapsed_ms: 7196.7
- row_count: 24
- source_types: code, doc, pdf, register
- retrieval_sources: fts5, lexical
- graph: nodes=2 edges=1 runtime=networkx
- top evidence:
  - id=60 symbol=IH_RB_CNTL source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c rank=8.95
  - id=75 symbol=IH_RB_CNTL source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c rank=8.95
  - id=71 symbol=ih_rb_cntl source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c rank=8.95
  - id=81 symbol=ih_rb_cntl source=code path=libgv/core/hw/AI/mi200/mi200_irqmgr.c rank=8.95
  - id=860540 symbol=ASIP source=pdf path=amdgpu-driver-source-tree.pdf rank=1.95

### Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL?

- elapsed_ms: 7650.7
- row_count: 24
- source_types: code, doc, pdf, register
- retrieval_sources: fts5, lexical
- graph: nodes=2 edges=1 runtime=networkx
- top evidence:
  - id=89 symbol=SDMA0_QUEUE0_RB_CNTL source=code path=libgv/core/hw/navi3/navi32_sdma.c rank=8.95
  - id=100 symbol=SDMA1_QUEUE0_RB_CNTL source=code path=libgv/core/hw/navi3/navi32_sdma.c rank=8.95
  - id=92 symbol=regSDMA0_QUEUE0_RB_CNTL source=code path=libgv/core/hw/navi3/navi32_sdma.c rank=8.95
  - id=860542 symbol=PDF source=pdf path=amdgpu-driver-source-tree.pdf rank=3.95
  - id=683915 symbol=SDMA0_FED_STATUS__SELFLOAD_UCODE_ECC_MASK source=register path=libgv/core/hw/navi3/asic_reg/navi3/GC/gc_11_0_3_sh_mask.h rank=7.95

### Show evidence connecting amdgpu documentation to the amdgpu driver source tree.

- elapsed_ms: 12345.0
- row_count: 24
- source_types: code, doc, pdf, register
- retrieval_sources: fts5, lexical
- graph: nodes=1 edges=0 runtime=networkx
- top evidence:
  - id=105 symbol=AMDGPU_NUM_VMID source=code path=drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c rank=13.95
  - id=121 symbol=AMDGPU_RING_TYPE_GFX source=code path=drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c rank=13.95
  - id=359135 symbol=BIF_BX0_DRIVER_SCRATCH_0 source=register path=libgv/core/hw/AI/asic_reg/mi300/NBIO/nbio_7_9_0_sh_mask.h rank=7.95
  - id=855036 symbol=AMDGPUV source=doc path=smi-lib/cli/cpp/docs/external/README.md rank=12.95
  - id=858169 symbol=VF_AMDGPU_INIT_FAIL source=doc path=smi-lib/docs/reference/amdsmi_py_api.md rank=11.95

### Explain WREG32_SOC15 regGCVM_L2_CNTL macro expansion chain.

- elapsed_ms: 7125.7
- row_count: 24
- source_types: code, doc, register
- retrieval_sources: fts5, lexical
- graph: nodes=3 edges=2 runtime=networkx
- top evidence:
  - id=13 symbol=WREG32_SOC15 source=code path=libgv/core/hw/navi3/gfx_v11_0.c rank=9.95
  - id=26 symbol=WREG32_SOC15 source=code path=libgv/core/hw/navi3/navi32_reset.c rank=8.95
  - id=90 symbol=WREG32_SOC15 source=code path=libgv/core/hw/navi3/navi32_sdma.c rank=8.95
  - id=101 symbol=WREG32_SOC15 source=code path=libgv/core/hw/navi3/navi32_sdma.c rank=8.95
  - id=129 symbol=WREG32_SOC15 source=code path=drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c rank=8.95

## Semantic Edge Jobs

- id=5 status=failed message=Ollama edge generation failed: qwen3.5:4b: Ollama returned no parseable JSON content: ```json\n{"cases":[{"id":"workbench-query","edges":[{"src":"regGCVM_L2_CNTL","relation":"reads","dst":"GCVM_L2_CNTL__ENABLE_L2_CACHE_MASK","confidence":0.9,"evidence":"Line 323: tmp = RREG32(SOC15_REG_OFFSET(GC, 0, regGCVM_L2_CNTL));"},{"src
- id=6 status=generated message=Generated 6 semantic edges
- id=7 status=generated message=Generated 6 semantic edges
