"""Write ScanConfig objects in the ScanBase HDF5 layout.

This module is a direct extraction of ScanBase._write_config_h5. It preserves
its HDF5 structure and writing behaviour; only the source of the values changes
from ScanBase instance attributes to a ScanConfig object.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import tables as tb

from tjmonopix2.system.scan_config import (
    FILTER_RAW_DATA,
    FILTER_TABLES,
    RegisterTable,
    RunConfigTable,
    ScanConfig,
)


def write_scan_config_to_h5(
    h5_file: tb.File,
    node: tb.Group,
    cfg: ScanConfig,
) -> None:
    """Write a ScanConfig using the original ScanBase HDF5 layout."""

    def write_dict_to_table(dictionary: Mapping[str, Any], table: tb.Table) -> None:
        for attribute, value in dictionary.items():
            row = table.row
            row["attribute"] = attribute
            try:
                row["value"] = value
            except (TypeError, ValueError):
                row["value"] = str(value)
            row.append()
        table.flush()

    # Scan configuration
    scan_node = h5_file.create_group(node, "scan", "Scan configuration")

    run_config_table = h5_file.create_table(
        scan_node,
        name="run_config",
        title="Run config",
        description=RunConfigTable,
        filters=FILTER_TABLES,
    )
    write_dict_to_table(cfg.run_config, run_config_table)

    scan_config_table = h5_file.create_table(
        scan_node,
        name="scan_config",
        title="Scan configuration",
        description=RunConfigTable,
        filters=FILTER_TABLES,
    )
    write_dict_to_table(cfg.scan_config, scan_config_table)

    # Chip configuration
    chip_node = h5_file.create_group(node, "chip", "Chip configuration")

    module_settings_table = h5_file.create_table(
        chip_node,
        name="module",
        title="Module settings from test bench",
        description=RunConfigTable,
        filters=FILTER_TABLES,
    )
    write_dict_to_table(cfg.module_settings, module_settings_table)

    settings_table = h5_file.create_table(
        chip_node,
        name="settings",
        title="Chip settings from test bench",
        description=RunConfigTable,
        filters=FILTER_TABLES,
    )
    write_dict_to_table(cfg.chip_settings, settings_table)

    register_table = h5_file.create_table(
        chip_node,
        name="registers",
        title="Registers",
        description=RegisterTable,
        filters=FILTER_TABLES,
    )
    for name, value in cfg.registers.items():
        row = register_table.row
        row["register"] = name
        row["value"] = value
        row.append()
    register_table.flush()

    mask_node = h5_file.create_group(
        chip_node,
        "masks",
        "Pixel masks",
    )
    for name, value in cfg.masks.items():
        h5_file.create_carray(
            mask_node,
            name=name,
            title=name.capitalize(),
            obj=np.asarray(value),
            filters=FILTER_RAW_DATA,
        )

    if cfg.use_pixel is not None:
        h5_file.create_carray(
            chip_node,
            name="use_pixel",
            title="Select pixels to be used in scans",
            obj=cfg.use_pixel,
            filters=FILTER_RAW_DATA,
        )

    # Test bench settings. This mirrors ScanBase: module settings are stored
    # separately above and are not repeated under configuration_in/bench.
    bench_node = h5_file.create_group(node, "bench", "Test bench settings")
    for setting, values in cfg.bench_config.items():
        if setting == "modules":
            continue

        table = h5_file.create_table(
            bench_node,
            name=setting,
            title=setting.capitalize(),
            description=RunConfigTable,
            filters=FILTER_TABLES,
        )
        write_dict_to_table(values, table)
