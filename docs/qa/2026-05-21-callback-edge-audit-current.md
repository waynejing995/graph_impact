# Callback Edge Audit Current

- Artifact: `docs/qa/2026-05-21-callback-edge-audit-current.json`
- Source: `asip.callback_edge_audit`
- Database: `data/asip.db`
- Gate status: `pass`

## Summary

- Callback/vtable edges: `4601`
- Ambiguous callback edges: `4530`
- Explained dynamic dispatch edges: `4530`
- Unexplained ambiguous callback edges: `0`
- Parser pollution candidates: `0`
- Real callback/vtable oracles: `7/7`

## Notes

The strict audit is run with `--assert-no-parser-pollution` and
`--max-ambiguous-fanout 2`. It now also requires real oracle hits across
amdgpu, MxGPU, and GIM callback/vtable surfaces:

- `gfx_v10_0_ring_preempt_ib` matched-slot `kiq_pm4_funcs` callback
- `amdgpu_device_fw_loading` common IP-block dispatch
- `amdgpu_perf_start` narrow generic-slot dispatch
- `amdgv_device_func_hw_init` typed MxGPU init callback array
- `amdgv_sched_world_switch_init` named ops/table-alias dispatch
- `amdgv_ecc_import_live_data` hardware ops table dispatch
- `snprintf_realloc` GIM interface callback

The previously suspicious `aca_bank_parser` and `aca_bank_is_valid` fanout is
now classified as typed `aca_bank_ops` dynamic dispatch rather than unexplained
parser overlinking.
