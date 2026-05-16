# Full-Corpus Semantic Edge Generation QA

Model: `qwen3.5:4b`
Duration: `99.83s`

## Corpora

- `mxgpu` `https://github.com/amd/MxGPU-Virtualization` commit=`f603f87` files=`703` scan_root=`/tmp/asip-mxgpu`
- `linux-amdgpu` `https://github.com/torvalds/linux` commit=`6916d57` files=`625` scan_root=`/tmp/asip-linux-amdgpu/drivers/gpu/drm/amd/amdgpu`

## Summary

- Query count: `9`
- Resolved query count: `9`
- Total files scanned: `1328`
- Passed: `7`
- Failed: `2`
- Ollama after run: `NAME          ID              SIZE      PROCESSOR    CONTEXT    UNTIL       
qwen3.5:4b    2a654d98e6fb    5.7 GB    100% GPU     2048       Stopping...`

## Interpretation And Risk

This run is useful evidence that the full-corpus path can execute against the
two AMD corpora with `qwen3.5:4b`, but it is not proof that semantic edge
generation is production-ready.

- Scope: the run covered `9` MVP queries across `1328` files and produced
  `7` pass / `2` fail.
- Current pass logic is limited: a query passes when the generated output
  includes the expected terms and at least one source reference. It does not
  yet prove that each generated edge is grounded in the cited snippet, that the
  relation label is semantically correct, or that no unsupported edges were
  emitted alongside the expected terms.
- The two failures show that full-corpus retrieval plus generation can still
  miss required symbols even when the query is resolved to a source snippet.
- Follow-up work is required before treating this as a completed goal:
  grounding validation for every emitted edge, fallback retry behavior for
  missing required terms, and precise `include` glob semantics so corpus scope
  is explicit and reproducible.

## Query Results

- `PASS` `query_mxgpu_gcvm_l2_cntl_fields` corpus=`mxgpu` edges=`3` sources=`1` missing=`` source_refs=`libgv/core/hw/navi3/gfx_v11_0.c:322-330`
- `PASS` `query_mxgpu_rlc_fed_pending` corpus=`mxgpu` edges=`3` sources=`1` missing=`` source_refs=`libgv/core/hw/navi3/navi32_reset.c:1322-1330`
- `FAIL` `query_mxgpu_reg_offset_gc_base` corpus=`mxgpu` edges=`0` sources=`1` missing=`adapt->reg_offset, GC_HWIP, GC_BASE` source_refs=`libgv/core/hw/AI/mi200/mi200_reg_init.c:37-45`
- `PASS` `query_mxgpu_doorbell_interrupt_disable` corpus=`mxgpu` edges=`1` sources=`1` missing=`` source_refs=`libgv/core/hw/AI/mi200/nbio_v7_4.c:90-98`
- `FAIL` `query_linux_gds_vmid_writes` corpus=`linux-amdgpu` edges=`1` sources=`1` missing=`mmGDS_VMID0_SIZE` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5225-5233`
- `PASS` `query_linux_grbm_soft_reset_rlc` corpus=`linux-amdgpu` edges=`1` sources=`1` missing=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5478-5486`
- `PASS` `query_linux_cp_vmid_reset_queues` corpus=`linux-amdgpu` edges=`3` sources=`1` missing=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:3845-3853`
- `PASS` `query_linux_cp_int_cntl_ring0_fields` corpus=`linux-amdgpu` edges=`3` sources=`1` missing=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5433-5441`
- `PASS` `query_linux_cp_me_ic_invalidate` corpus=`linux-amdgpu` edges=`1` sources=`1` missing=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5889-5897`
