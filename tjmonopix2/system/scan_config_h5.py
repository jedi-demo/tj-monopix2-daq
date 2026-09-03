"""
HDF5 writer for ScanConfig.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import tables as tb

from tjmonopix2.scan_base import (
    FILTER_RAW_DATA,
    FILTER_TABLES,
    RunConfigTable,
    RegisterTable,
)
from tjmonopix2.scan_config import ScanConfig


def write_scan_config_to_h5(
    h5file: tb.File,
    node: tb.Group,
    cfg: ScanConfig,
) -> None:
    """
    Write a ScanConfig to HDF5 in the ScanBase layout.
    """

    # Scan
    scan_node = h5file.create_group(node, "scan", "Scan configuration")

    _run_config_table = h5file.create_table(
        scan_node,
        "run_config",
        description=RunConfigTable,
        title="Run config",
        filters=FILTER_TABLES,
    )
    for attr, value in cfg.run_config.items():
        row = _run_config_table.row
        row["attribute"] = attr
        row["value"] = value
        row.append()
    _run_config_table.flush()

    _write_dict_to_table(
        cfg.scan_config,
        h5file.create_table(
            scan_node,
            "scan_config",
            description=RunConfigTable,
            title="Scan configuration",
            filters=FILTER_TABLES,
        ),
    )

    # Chip
    chip_node = h5file.create_group(node, "chip", "Chip configuration")

    _write_dict_to_table(
        cfg.chip_settings,
        h5file.create_table(
            chip_node,
            "settings",
            description=RunConfigTable,
            title="Chip settings from test bench",
            filters=FILTER_TABLES,
        ),
    )
    _write_dict_to_table(
        cfg.module_settings,
        h5file.create_table(
            chip_node,
            "module",
            description=RunConfigTable,
            title="Module settings from test bench",
            filters=FILTER_TABLES,
        ),
    )

    registers_table = h5file.create_table(
        chip_node,
        "registers",
        description=RegisterTable,
        title="Registers",
        filters=FILTER_TABLES,
    )
    for name, value in _mapping(cfg.registers).items():
        row = registers_table.row
        row["register"] = name
        row["value"] = value
        row.append()
    registers_table.flush()

    if cfg.masks:
        masks_node = h5file.create_group(chip_node, "masks", "Pixel masks")
        for name, value in cfg.masks.items():
            arr = _decode_array(value)
            h5file.create_carray(
                masks_node,
                name=str(name),
                atom=tb.Atom.from_dtype(arr.dtype),
                title=str(name).capitalize(),
                obj=arr,
                filters=FILTER_RAW_DATA,
            )

    if cfg.use_pixel is not None:
        arr = _decode_array(cfg.use_pixel)
        h5file.create_carray(
            chip_node,
            "use_pixel",
            atom=tb.Atom.from_dtype(arr.dtype),
            title="Select pixels to be used in scans",
            obj=arr,
            filters=FILTER_RAW_DATA,
        )

    # Bench
    bench_node = h5file.create_group(node, "bench", "Test bench settings")
    for name, values in _mapping(cfg.bench_config).items():
        _write_dict_to_table(
            values,
            h5file.create_table(
                bench_node,
                str(name),
                description=RunConfigTable,
                title=str(name).capitalize(),
                filters=FILTER_TABLES,
            ),
        )


# ------
def _write_dict_to_table(values: Any, table: tb.Table) -> None:
    for attribute, value in _mapping(values).items():
        row = table.row
        row["attribute"] = attribute
        row["value"] = str(value)
        row.append()
    table.flush()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _decode_array(value: Any) -> np.ndarray:
    if isinstance(value, Mapping) and value.get("__numpy__") is True:
        array = np.asarray(value["data"], dtype=np.dtype(value["dtype"]))
        return array.reshape(tuple(value["shape"]))
    return np.asarray(value)
