"""Shared configuration object for ScanBase and the Constellation receiver.

This module defines a plain data object that ScanBase can construct 
and then pass to the HDF5 writer.
"""

from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any
import numpy as np
import tables as tb

MIN_INT64 = -(2**63)
MAX_UINT64 = 2**64 - 1

FILTER_RAW_DATA = tb.Filters(complib="blosc", complevel=5, fletcher32=False)
FILTER_TABLES = tb.Filters(complib="zlib", complevel=5, fletcher32=False)


class RunConfigTable(tb.IsDescription):
    attribute = tb.StringCol(64)
    value = tb.StringCol(512)


class RegisterTable(tb.IsDescription):
    register = tb.StringCol(64)
    value = tb.StringCol(256)

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
    """Serialise ScanConfig for a Constellation BOR/EOR payload."""
    return _serialise({
        "run_config": cfg.run_config,
        "scan_config": cfg.scan_config,
        "chip_settings": cfg.chip_settings,
        "module_settings": cfg.module_settings,
        "registers": cfg.registers,
        "masks": cfg.masks,
        "use_pixel": cfg.use_pixel,
        "bench_config": cfg.bench_config,
    })

def scan_config_from_payload(payload: Mapping[str, Any]) -> ScanConfig:
    """Deserialise ScanConfig received in a Constellation BOR/EOR payload."""
    data = _deserialise(payload)

    return ScanConfig(
        run_config=data.get("run_config", {}),
        scan_config=data.get("scan_config", {}),
        chip_settings=data.get("chip_settings", {}),
        module_settings=data.get("module_settings", {}),
        registers=data.get("registers", {}),
        masks=data.get("masks", {}),
        use_pixel=data.get("use_pixel"),
        bench_config=data.get("bench_config", {}),
    )

def _serialise(value: Any) -> Any:
    """Convert values into objects accepted by the BOR/EOR serializer."""
    if isinstance(value, Mapping):
        return {
            str(key): _serialise(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_serialise(item) for item in value]

    if isinstance(value, np.ndarray):
        return {
            "__numpy__": True,
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "data": _serialise(value.tolist()),
        }

    if isinstance(value, np.generic):
        return _serialise(value.item())

    if isinstance(value, int):
        if value < MIN_INT64 or value > MAX_UINT64:
            return {
                "__integer__": True,
                "value": str(value),
            }

    return value

def _deserialise(value: Any) -> Any:
    """Restore arrays and integers encoded for BOR/EOR transport."""
    if isinstance(value, Mapping):
        if value.get("__integer__") is True:
            return int(value["value"])

        if value.get("__numpy__") is True:
            array = np.asarray(
                _deserialise(value["data"]),
                dtype=np.dtype(value["dtype"]),
            )
            return array.reshape(tuple(value["shape"]))

        return {
            key: _deserialise(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_deserialise(item) for item in value]

    return value

def _decode_array(value: Any) -> Any:
    if isinstance(value, dict) and value.get("__numpy__"):
        arr = np.asarray(value["data"], dtype=np.dtype(value["dtype"]))
        return arr.reshape(tuple(value["shape"]))
    return value

def find_out_of_range_integers(
    value: Any,
    path: str = "root",
) -> list[tuple[str, int]]:
    found = []

    if isinstance(value, Mapping):
        for key, item in value.items():
            found.extend(
                find_out_of_range_integers(item, f"{path}.{key}")
            )
        return found

    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(
                find_out_of_range_integers(item, f"{path}[{index}]")
            )
        return found

    if isinstance(value, np.ndarray):
        return find_out_of_range_integers(value.tolist(), path)

    if isinstance(value, np.integer):
        value = int(value)

    if isinstance(value, int):
        if value < MIN_INT64 or value > MAX_UINT64:
            found.append((path, value))

    return found
