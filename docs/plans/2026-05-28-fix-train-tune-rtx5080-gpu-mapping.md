# Fix Train Tune RTX 5080 GPU Mapping

## Summary

Train Tune DDP failed because Ultralytics received `device=0,1`, which mapped to physical GPU `0` and `1` on this host. The host maps `nvidia-smi` index `0` to RTX 4090 and indexes `1,2` to RTX 5080, so High-Speed training was not using both RTX 5080 cards.

## Implementation

- Constrain Train Tune subprocesses with `CUDA_VISIBLE_DEVICES` before Ultralytics starts.
- Default the whole LabelLens backend to `CUDA_VISIBLE_DEVICES=1,2` so physical GPU `0` (RTX 4090) remains reserved for vLLM.
- Standard Mode defaults to physical GPU `1`, passed to Ultralytics as `device=1`.
- High-Speed Mode defaults to physical GPUs `1,2`, passed to Ultralytics as `device=1,2`.
- High-Speed Mode defaults AMP off to avoid RTX 5080 DDP illegal-instruction failures observed with YOLO26 segmentation.
- Emit startup training mapping diagnostics with `CUDA_DEVICE_ORDER`, `CUDA_VISIBLE_DEVICES`, local Ultralytics device string, visible CUDA count, and visible CUDA names.
- Patch Ultralytics-generated DDP temp files at runtime to use `find_unused_parameters=True`, which avoids YOLO26 segmentation unused-parameter failures without editing site-packages.
- Update README, AGENTS, and CLAUDE GPU documentation.

## Tests

- Add unit coverage for Standard and High-Speed device policy resolution.
- Add unit coverage that `actual_train()` passes the correct local device string to Ultralytics.
- Run a CUDA visibility smoke check with `CUDA_VISIBLE_DEVICES=1,2`.
