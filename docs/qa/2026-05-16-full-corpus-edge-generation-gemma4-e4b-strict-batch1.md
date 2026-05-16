# Full-Corpus Semantic Edge Generation QA

Model: `gemma4:e4b`
Duration: `199.01s`

## Corpora

- `mxgpu` `https://github.com/amd/MxGPU-Virtualization` commit=`f603f87` files=`703` scan_root=`/tmp/asip-mxgpu`
- `linux-amdgpu` `https://github.com/torvalds/linux` commit=`6916d57` files=`625` scan_root=`/tmp/asip-linux-amdgpu/drivers/gpu/drm/amd/amdgpu`

## Summary

- Query count: `9`
- Resolved query count: `9`
- Total files scanned: `1328`
- Passed: `7`
- Failed: `2`
- Ollama after run:

```text
NAME          ID              SIZE     PROCESSOR    CONTEXT    UNTIL
gemma4:e4b    c6eb396dbd59    10 GB    100% GPU     2048       Stopping...
```

## Query Results

- `PASS` `query_mxgpu_gcvm_l2_cntl_fields` corpus=`mxgpu` edges=`5` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`libgv/core/hw/navi3/gfx_v11_0.c:322-330`
- `PASS` `query_mxgpu_rlc_fed_pending` corpus=`mxgpu` edges=`5` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`libgv/core/hw/navi3/navi32_reset.c:1322-1330`
- `PASS` `query_mxgpu_reg_offset_gc_base` corpus=`mxgpu` edges=`1` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`libgv/core/hw/AI/mi200/mi200_reg_init.c:37-45`
- `PASS` `query_mxgpu_doorbell_interrupt_disable` corpus=`mxgpu` edges=`2` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`libgv/core/hw/AI/mi200/nbio_v7_4.c:90-98`
- `PASS` `query_linux_gds_vmid_writes` corpus=`linux-amdgpu` edges=`3` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5225-5233`
- `PASS` `query_linux_grbm_soft_reset_rlc` corpus=`linux-amdgpu` edges=`2` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5478-5486`
- `FAIL` `query_linux_cp_vmid_reset_queues` corpus=`linux-amdgpu` edges=`0` sources=`1` missing=`CP_VMID_RESET, RESET_REQUEST, PIPE0_QUEUES, PIPE1_QUEUES` missing_in_sources=`` ungrounded_edges=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:3845-3853`
- `PASS` `query_linux_cp_int_cntl_ring0_fields` corpus=`linux-amdgpu` edges=`3` sources=`1` missing=`` missing_in_sources=`` ungrounded_edges=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5433-5441`
- `FAIL` `query_linux_cp_me_ic_invalidate` corpus=`linux-amdgpu` edges=`0` sources=`1` missing=`CP_ME_IC_OP_CNTL, INVALIDATE_CACHE` missing_in_sources=`` ungrounded_edges=`` source_refs=`drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:5889-5897`

## Verified Edge Examples

- `mxgpu_gcvm_l2_cntl_fields`: `tmp reads regGCVM_L2_CNTL`; `tmp writes regGCVM_L2_CNTL`.
- `mxgpu_rlc_fed_pending`: `reg_data sets_field RLC_FED_DRVR_STATUS`; `RLC_FED_DRVR_STATUS checks_mask PENDING`.
- `mxgpu_reg_offset_gc_base`: `adapt writes adapt->reg_offset[GC_HWIP][i]`.
- `linux_gds_vmid_writes`: `WREG32_SOC15_OFFSET writes mmGDS_VMID0_BASE`; `WREG32_SOC15_OFFSET writes mmGDS_VMID0_SIZE`; `WREG32_SOC15_OFFSET writes mmGDS_GWS_VMID0`.
- `linux_grbm_soft_reset_rlc`: `WREG32_FIELD15 writes GRBM_SOFT_RESET`.
- `linux_cp_int_cntl_ring0_fields`: `tmp writes CP_INT_CNTL_RING0` for `CNTX_BUSY_INT_ENABLE`, `CNTX_EMPTY_INT_ENABLE`, and `CMP_BUSY_INT_ENABLE`.

## Failed Batch Diagnostics

- `linux_cp_vmid_reset_queues` found the source snippet, but Gemma returned truncated JSON while generating the `CP_VMID_RESET` edges.
- `linux_cp_me_ic_invalidate` found the source snippet, but Gemma returned truncated JSON while generating the `CP_ME_IC_OP_CNTL` / `INVALIDATE_CACHE` edges.

## Local Runtime Observations

- Ollama version during run: `0.24.0`.
- Model: `gemma4:e4b`, `10 GB`, `100% GPU`, `context=2048`.
- Resource monitor samples: `13`.
- Max observed runner CPU: `28.6%`.
- Max observed runner memory: `38.8%`.
- Max observed runner RSS: `9528.4 MB`.
- Min observed free memory pages: `4234` pages, about `66.2 MB`.
- Raw resource sample log: `/tmp/asip-gemma-resource.log`.
- Raw Ollama log stream sample: `/tmp/asip-gemma-ollama-log.txt`.
