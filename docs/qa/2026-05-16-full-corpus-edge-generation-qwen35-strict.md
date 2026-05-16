# Full-Corpus Semantic Edge Generation QA

Model: `qwen3.5:4b`
Duration: `106.27s`

## Corpora

- `mxgpu` `https://github.com/amd/MxGPU-Virtualization` commit=`f603f87` files=`703` scan_root=`/tmp/asip-mxgpu`
- `linux-amdgpu` `https://github.com/torvalds/linux` commit=`6916d57` files=`625` scan_root=`/tmp/asip-linux-amdgpu/drivers/gpu/drm/amd/amdgpu`

## Summary

- Query count: `9`
- Resolved query count: `9`
- Total files scanned: `1328`
- Passed: `2`
- Failed: `7`
- Ollama after run:

```text
NAME          ID              SIZE      PROCESSOR    CONTEXT    UNTIL
qwen3.5:4b    2a654d98e6fb    5.7 GB    100% GPU     2048       Stopping...
```

## Query Results

- `FAIL` `query_mxgpu_gcvm_l2_cntl_fields` corpus=`mxgpu` edges=`3` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`libgv/core/hw/navi3/gfx_v11_0.c->regGCVM_L2_CNTL, libgv/core/hw/navi3/gfx_v11_0.c->GCVM_L2_CNTL, libgv/core/hw/navi3/gfx_v11_0.c->ENABLE_L2_CACHE` source_refs=`libgv/core/hw/navi3/gfx_v11_0.c:322-330`
- `FAIL` `query_mxgpu_rlc_fed_pending` corpus=`mxgpu` edges=`3` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`libgv/core/hw/navi3/navi32_reset.c->regRLC_FED_DRVR_STATUS, libgv/core/hw/navi3/navi32_reset.c->RLC_FED_DRVR_STATUS, libgv/core/hw/navi3/navi32_reset.c->PENDING` source_refs=`libgv/core/hw/navi3/navi32_reset.c:1322-1330`
- `FAIL` `query_mxgpu_reg_offset_gc_base` corpus=`mxgpu` edges=`0` sources=`1` missing=`adapt->reg_offset, GC_HWIP, GC_BASE` missing_in_sources=`` ungrounded_edges=`` source_refs=`libgv/core/hw/AI/mi200/mi200_reg_init.c:37-45`
- `PASS` `query_mxgpu_doorbell_interrupt_disable` corpus=`mxgpu` edges=`1` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`libgv/core/hw/AI/mi200/nbio_v7_4.c:90-98`
- `FAIL` `query_linux_gds_vmid_writes` corpus=`linux-amdgpu` edges=`1` sources=`1` missing=`mmGDS_VMID0_SIZE` missing_in_sources=`` ungrounded_edges=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5225-5233`
- `PASS` `query_linux_grbm_soft_reset_rlc` corpus=`linux-amdgpu` edges=`1` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5478-5486`
- `FAIL` `query_linux_cp_vmid_reset_queues` corpus=`linux-amdgpu` edges=`3` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`gfx_v10_0.c->CP_VMID_RESET, gfx_v10_0.c->CP_VMID_RESET, gfx_v10_0.c->CP_VMID_RESET` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:3845-3853`
- `FAIL` `query_linux_cp_int_cntl_ring0_fields` corpus=`linux-amdgpu` edges=`3` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`gfx_v10_0.c->CP_INT_CNTL_RING0, gfx_v10_0.c->CP_INT_CNTL_RING0, gfx_v10_0.c->CP_INT_CNTL_RING0` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5433-5441`
- `FAIL` `query_linux_cp_me_ic_invalidate` corpus=`linux-amdgpu` edges=`1` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`gfx_v10_0.c->CP_ME_IC_OP_CNTL` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5889-5897`
