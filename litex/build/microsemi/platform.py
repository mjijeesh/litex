#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import GenericPlatform
from litex.build.microsemi import common, libero_soc 

# MicrosemiPlatform --------------------------------------------------------------------------------

class MicrosemiPlatform(GenericPlatform):
    _bitstream_ext = ".bit"
    _jtag_support  = False

    _supported_toolchains = ["libero_soc"]

    def __init__(self, *args, toolchain="libero_soc", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        
        # --- MODIFIED ---
        # List to store (instance, x, y) tuples
        self.placement_constraints = []
        # --- END ---

        if toolchain == "libero_soc":
             self.toolchain = libero_soc.MicrosemiLiberoSoCToolchain()        
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict()
        so.update(self.toolchain.special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs
        )

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    # --- MODIFIED METHOD ---
    def add_placement_constraint(self, instance, x, y):
        """
        Adds a Libero location constraint (PDC) for a specific instance
        using X/Y coordinates.
        This list is processed by the toolchain during the build phase.

        Parameters:
        -----------
        instance : str
            The hierarchical instance path from the top module
            (e.g., "my_ram_wrapper_0/bram_instance").
        x : str or int
            The X coordinate for the placement.
        y : str or int
            The Y coordinate for the placement.
        """
        self.placement_constraints.append((instance, x, y))
    # --- END OF MODIFIED METHOD ---

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        from_.attr.add("keep")
        to.attr.add("keep")
        self.toolchain.add_false_path_constraint(self, from_, to)
        


class MicrosemiPolarfirePlatform(MicrosemiPlatform):
    device_family = "mpf"
class MicrosemiSmartFusion2Platform(MicrosemiPlatform):
    device_family = "m2s"
class MicrosemiIGLOO2Platform(MicrosemiPlatform):
    device_family = "m2gl"