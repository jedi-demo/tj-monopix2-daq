"""Shared configuration object for ScanBase and the Constellation receiver.

This module defines a plain data object that ScanBase can construct 
and then pass to the HDF5 writer.
"""

from dataclasses import dataclass, field
from typing import Any
import numpy as np


@dataclass(frozen=True)
class ScanConfig:
    """
    Configuration object.
    """

    # Top-level scan configuration
    scan_config: dict[str, Any] = field(default_factory=dict)

    # Run-level meta data
    run_config: dict[str, Any] = field(default_factory=dict)

    # Chip-level configuration
    chip_settings: dict[str, Any] = field(default_factory=dict)
    module_settings: dict[str, Any] = field(default_factory=dict)
    registers: dict[str, Any] = field(default_factory=dict)
    masks: dict[str, Any] = field(default_factory=dict)
    use_pixel: Any | None = None  # encoded array or None

    # Testbench-level configuration
    bench_config: dict[str, Any] = field(default_factory=dict)


def scan_config_to_payload(cfg: ScanConfig) -> dict[str, Any]:
    """Serialise ScanConfig"""
    return {
        "run_config": _serialise_dict(cfg.run_config),
        "scan_config": _serialise_dict(cfg.scan_config),
        "chip_settings": _serialise_dict(cfg.chip_settings),
        "module_settings": _serialise_dict(cfg.module_settings),
        "registers": _serialise_dict(cfg.registers),
        "masks": _serialise_dict(cfg.masks),
        "use_pixel": _encode_array(cfg.use_pixel) if cfg.use_pixel is not None else None,
        "bench_config": _serialise_dict(cfg.bench_config),
    }

def scan_config_from_payload(payload: dict[str, Any]) -> ScanConfig:
    """Deserialise ScanConfig"""
    return ScanConfig(
        run_config=payload.get("run_config", {}),
        scan_config=payload.get("scan_config", {}),
        chip_settings=payload.get("chip_settings", {}),
        module_settings=payload.get("module_settings", {}),
        registers=payload.get("registers", {}),
        masks=payload.get("masks", {}),
        use_pixel=_decode_array(payload.get("use_pixel")),
        bench_config=payload.get("bench_config", {}),
    )

def _serialise_dict(d: dict[str, Any]) -> dict[str, Any]:
    return {k: _encode_array(v) if isinstance(v, np.ndarray) else v
            for k, v in d.items()}

def _encode_array(value: Any) -> Any:
    if not isinstance(value, np.ndarray):
        return value
    return {
        "__numpy__": True,
        "dtype": str(value.dtype),
        "shape": list(value.shape),
        "data": value.tolist(),
    }

def _decode_array(value: Any) -> Any:
    if isinstance(value, dict) and value.get("__numpy__"):
        arr = np.asarray(value["data"], dtype=np.dtype(value["dtype"]))
        return arr.reshape(tuple(value["shape"]))
    return value
