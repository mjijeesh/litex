# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess
import shutil
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.generic_toolchain import GenericToolchain
from litex.build.microsemi import common

class MicrosemiLiberoSoCToolchain(GenericToolchain):
    attr_translate = {}

    def __init__(self):
        super().__init__()
        self.additional_io_constraints     = []
        self.additional_fp_constraints     = []
        self.additional_timing_constraints = []

    def build(self, platform, *args, **kwargs):
        """Sets family-specific overrides at the start of the build process."""
        device = platform.device.lower()
        if device.startswith("mpf"):
            self.special_overrides = common.microsemi_mpf_special_overrides
        elif device.startswith("m2s") or device.startswith("m2gl"):
            self.special_overrides = common.microsemi_m2s_special_overrides
        else:
            raise ValueError(f"Unsupported device family for device: {platform.device}")
        return super().build(platform, *args, **kwargs)

    @classmethod
    def tcl_name(cls, name):
        return "{" + name + "}"

    ## IO Constraint Dispatcher
    
    def build_io_constraints(self):
        """Dispatcher method for IO constraints."""
        device = self.platform.device.lower()
        pdc = ""
        for sig, pins, others, resname in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    if device.startswith("mpf"):
                        pdc += self._format_io_pdc_mpf(sig + f"[{i}]", p, others)
                    else:
                        pdc += self._format_io_pdc_m2s(sig + f"[{i}]", p, others)
            else:
                if device.startswith("mpf"):
                    pdc += self._format_io_pdc_mpf(sig, pins[0], others)
                else:
                    pdc += self._format_io_pdc_m2s(sig, pins[0], others)
        
        pdc += "\n".join(self.additional_io_constraints)
        tools.write_to_file(self._build_name + "_io.pdc", pdc)
        return (self._build_name + "_io.pdc", "PDC")

    ## Family-Specific IO Constraint Helpers
    
    def _format_io_pdc_mpf(self, signame, pin, others):
        """Formats a PDC line for PolarFire devices."""
        r = f"set_io -port_name {self.tcl_name(signame)} "
        for c in ([Pins(pin)] + others):
            if isinstance(c, Pins):
                r += f"-pin_name {c.identifiers[0]} "
            elif isinstance(c, IOStandard):
                r += f"-io_std {c.name} "
            elif isinstance(c, Misc):
                r += f"-RES_PULL {c.misc} "
        r += "-fixed true\n"
        return r

    def _format_io_pdc_m2s(self, signame, pin, others):
        """Formats a PDC line for SmartFusion2/IGLOO2 devices."""
        r = f"set_io {self.tcl_name(signame)} "
        for c in ([Pins(pin)] + others):
            if isinstance(c, Pins):
                r += f"-pinname {c.identifiers[0]} "
            elif isinstance(c, IOStandard):
                r += f"-iostd {c.name} "
            elif isinstance(c, Misc):
                r += f"-RES_PULL {c.misc} "
        r += "-fixed true\n"
        return r

    def build_placement_constraints(self):
        pdc = "\n".join(self.additional_fp_constraints)
        tools.write_to_file(self._build_name + "_fp.pdc", pdc)
        return (self._build_name + "_fp.pdc", "PDC")

    ## Project Build Dispatcher
    
    def build_project(self):
        """Calls the correct project builder based on device name."""
        device = self.platform.device.lower()
        if device.startswith("mpf"):
            return self.build_project_mpf()
        elif device.startswith("m2s") or device.startswith("m2gl"):
            return self.build_project_m2s()
        else:
            raise ValueError(f"Unsupported device family for device: {self.platform.device}")

    ## Family-Specific Project Builders
    
    def build_project_mpf(self):
        """Generates the TCL script for PolarFire devices."""
        tcl = []
        #die, package, speed = self.platform.device.split("-")
        
        # Handle different device string formats
        device_parts = self.platform.device.split("-")
        if len(device_parts) == 3:
            die, package, speed = device_parts
        elif len(device_parts) == 2:
            die, package = device_parts
            speed = "STD" # Use a default speed grade of STD
        else:
            raise ValueError(f"Unexpected device string format: {self.platform.device}")

        # ### CORRECTED SECTION START ###
        # --- Smarter speed grade formatting ---
        if speed.upper() == "STD":
            formatted_speed = speed # Use "STD" without a prefix
        elif not speed.startswith("-"):
            formatted_speed = "-" + speed
        else:
            formatted_speed = speed
        # ### CORRECTED SECTION END ###


        tcl.append(" ".join([
            "new_project",
            "-location {./impl}",
            f"-name {self.tcl_name(self._build_name)}",
            "-project_description {}",
            "-block_mode 0",
            "-standalone_peripheral_initialization 0",
            "-instantiate_in_smartdesign 1",
            "-ondemand_build_dh 0",
            "-use_enhanced_constraint_flow 1",
            "-hdl {VERILOG}",
            "-family {PolarFire}",
            f"-die {self.tcl_name(die)}",
            f"-package {self.tcl_name(package)}",
            f"-speed {self.tcl_name(formatted_speed)}", # Use the new formatted variable
            "-die_voltage {1.0}",
            "-part_range {IND}",
            "-adv_options {VCCI_1.2_VOLTR:IND}",
            "-adv_options {VCCI_1.5_VOLTR:IND}",
            "-adv_options {VCCI_1.8_VOLTR:IND}",
            "-adv_options {VCCI_2.5_VOLTR:IND}",
            "-adv_options {VCCI_3.3_VOLTR:IND}"
        ]))
        
        # Add sources and constraints
        for filename, language, library, *copy in self.platform.sources:
            filename_tcl = "{" + filename + "}"
            tcl.append("import_files -hdl_source " + filename_tcl)
            
        # Building the design Hierarchy    
        tcl.append("build_design_hierarchy")
        
        # Set top level
        #tcl.append("set_root -module {}".format(self.tcl_name(self._build_name + "::work")))
        tcl.append(f"set_root -module {self.tcl_name(self._build_name + '::work')}")
        
                
        # Copy init files FIXME: support for include path on LiberoSoC?
        # Commenting out copy init file as this breaks the LiberoSoC flow.
        #for file in os.listdir(self._build_dir):
        #    if file.endswith(".init"):
        #        tcl.append("file copy -- {} impl/synthesis".format(file))
        
        
        # Import io constraints
        #tcl.append("import_files -io_pdc {}".format(self.tcl_name(self._build_name + "_io.pdc")))
        
        tcl.append(f"import_files -io_pdc {self.tcl_name(self._build_name + '_io.pdc')}")
        
        # Import floorplanner constraints
        #tcl.append("import_files -fp_pdc {}".format(self.tcl_name(self._build_name + "_fp.pdc")))
        
        tcl.append(f"import_files -fp_pdc {self.tcl_name(self._build_name + '_fp.pdc')}")
        
        # Import timing constraints
        #tcl.append("import_files -convert_EDN_to_HDL 0 -sdc {}".format(self.tcl_name(self._build_name + ".sdc")))
        
        tcl.append(f"import_files -convert_EDN_to_HDL 0 -sdc {self.tcl_name(self._build_name + '.sdc')}")
        
        
        # Associate constraints with tools
        tcl.append(" ".join(["organize_tool_files",
            "-tool {SYNTHESIZE}",
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))
        tcl.append(" ".join(["organize_tool_files",
            "-tool {PLACEROUTE}",
            "-file impl/constraint/io/{}_io.pdc".format(self._build_name),
            "-file impl/constraint/fp/{}_fp.pdc".format(self._build_name),
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))
        tcl.append(" ".join(["organize_tool_files",
            "-tool {VERIFYTIMING}",
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))



        # Build flow
        tcl.append("run_tool -name {CONSTRAINT_MANAGEMENT}")
        tcl.append("run_tool -name {SYNTHESIZE}")
        tcl.append("run_tool -name {PLACEROUTE}")
        tcl.append("run_tool -name {GENERATEPROGRAMMINGDATA}")
        tcl.append("run_tool -name {GENERATEPROGRAMMINGFILE}")
        
        # Export programming file using dynamic build name and disabled auto-programming.
        tcl.append(f"""
        export_prog_job \\
            -job_file_name {{{self._build_name}}} \\
            -export_dir {{./impl/designer/{self._build_name}/export}} \\
            -bitstream_file_type {{TRUSTED_FACILITY}} \\
            -bitstream_file_components {{FABRIC SNVM}} \\
            -program_design 0 \\
            -design_bitstream_format {{PPD}}
        """)
        
        
        tools.write_to_file(self._build_name + ".tcl", "\n".join(tcl))
        return self._build_name + ".tcl"

    def build_project_m2s(self):
        """Generates the TCL script for SmartFusion2 & IGLOO2 devices."""
        tcl = []
        device = self.platform.device.lower()
        family_name = "SmartFusion2" if device.startswith("m2s") else "IGLOO2"
        #die, package, speed = self.platform.device.split("-")
        
        #die, package, speed = self.platform.device.split("-")
        
        # Handle different device string formats
        device_parts = self.platform.device.split("-")
        if len(device_parts) == 3:
            die, package, speed = device_parts
        elif len(device_parts) == 2:
            die, package = device_parts
            speed = "STD" # Use a default speed grade of STD
        else:
            raise ValueError(f"Unexpected device string format: {self.platform.device}")

        # ### CORRECTED SECTION START ###
        # --- Smarter speed grade formatting ---
        if speed.upper() == "STD":
            formatted_speed = speed # Use "STD" without a prefix
        elif not speed.startswith("-"):
            formatted_speed = "-" + speed
        else:
            formatted_speed = speed
              
        
        
        tcl.append(" ".join([
            "new_project",
            "-location {./impl}",
            f"-name {self.tcl_name(self._build_name)}",
            "-project_description {}",
            "-block_mode 0",
            "-standalone_peripheral_initialization 0",
            "-instantiate_in_smartdesign 1",
            "-ondemand_build_dh 0",
            "-use_enhanced_constraint_flow 1",
            "-hdl {VERILOG}",
            f"-family {{{family_name}}}",
            f"-die {self.tcl_name(die)}",
            f"-package {self.tcl_name(package)}",
            f"-speed {self.tcl_name(formatted_speed)}", # Use the new formatted variable
            "-die_voltage {1.2}",
            "-part_range {IND}",
            "-adv_options {IO_DEFT_STD:LVCMOS 3.3V}",
            "-adv_options {RESTRICTPROBEPINS:1}",
            "-adv_options {PLL_SUPPLY:PLL_SUPPLY_33}",
        ]))
        
        # Add sources and constraints
        for filename, language, library, *copy in self.platform.sources:
            tcl.append(f"import_files -hdl_source {self.tcl_name(filename)}")
        tcl.append("build_design_hierarchy")
        tcl.append(f"set_root -module {self.tcl_name(self._build_name + '::work')}")
        tcl.append(f"import_files -io_pdc {self.tcl_name(self._build_name + '_io.pdc')}")
        tcl.append(f"import_files -fp_pdc {self.tcl_name(self._build_name + '_fp.pdc')}")
        tcl.append(f"import_files -convert_EDN_to_HDL 0 -sdc {self.tcl_name(self._build_name + '.sdc')}")
        
        
        # Associate constraints with tools
        tcl.append(" ".join(["organize_tool_files",
            "-tool {SYNTHESIZE}",
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))
        tcl.append(" ".join(["organize_tool_files",
            "-tool {PLACEROUTE}",
            "-file impl/constraint/io/{}_io.pdc".format(self._build_name),
            "-file impl/constraint/fp/{}_fp.pdc".format(self._build_name),
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))
        tcl.append(" ".join(["organize_tool_files",
            "-tool {VERIFYTIMING}",
            "-file impl/constraint/{}.sdc".format(self._build_name),
            "-module {}".format(self._build_name),
            "-input_type {constraint}"
        ]))


        # Build flow
        tcl.append("run_tool -name {CONSTRAINT_MANAGEMENT}")
        tcl.append("run_tool -name {SYNTHESIZE}")
        tcl.append("run_tool -name {PLACEROUTE}")
        tcl.append("run_tool -name {GENERATEPROGRAMMINGDATA}")
        tcl.append("run_tool -name {GENERATEPROGRAMMINGFILE}")
        
        # Export programming file using dynamic build name and disabled auto-programming.
        
        tcl.append(" ".join([
            "export_prog_job",
            "-job_file_name {{{}}}".format(self._build_name),
            "-export_dir {{./impl/designer/{}/export}}".format(self._build_name),
            "-bitstream_file_type {TRUSTED_FACILITY}",
            "-bitstream_file_components {FABRIC}",
            "-sanitize_envm  0",
            "-design_bitstream_format {PPD}"
        ]))
        
              
        tools.write_to_file(self._build_name + ".tcl", "\n".join(tcl))
        return self._build_name + ".tcl"

    ## Common Methods
    
    def build_timing_constraints(self, vns):
        sdc = []
        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            clk_sig = self._vns.get_name(clk)
            if name is None:
                name = clk_sig
            sdc.append(f"create_clock -name {name} -period {str(period)} [get_nets {clk_sig}]")
        for from_, to in sorted(self.false_paths, key=lambda x: (x[0].duid, x[1].duid)):
            sdc.append(f"set_clock_groups -group [get_clocks -include_generated_clocks -of [get_nets {from_}]] -group [get_clocks -include_generated_clocks -of [get_nets {to}]] -asynchronous")
        sdc += self.additional_timing_constraints
        tools.write_to_file(self._build_name + ".sdc", "\n".join(sdc))
        return (self._build_name + ".sdc", "SDC")

    def build_script(self):
        if sys.platform in ("win32", "cygwin"):
            script_ext = ".bat"
            script_contents = "@echo off\nREM Autogenerated by LiteX\n\n"
        else:
            script_ext = ".sh"
            script_contents = "# Autogenerated by LiteX\n"
        script_contents += f"libero script:{self._build_name}.tcl\n"
        script_file = "build_" + self._build_name + script_ext
        tools.write_to_file(script_file, script_contents, force_unix=False)
        return script_file

    def run_script(self, script):
        if os.path.exists("impl"):
            shutil.rmtree("impl")
        if sys.platform in ["win32", "cygwin"]:
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]
        if which("libero") is None:
            msg = "Unable to find Libero SoC toolchain.\n"
            raise OSError(msg)
        if subprocess.call(shell + [script]) != 0:
            raise OSError("Subprocess failed")

    def add_false_path_constraint(self, platform, from_, to):
        if (to, from_) not in self.false_paths:
            self.false_paths.add((from_, to))