import os
import subprocess
import sys
import platform
import shutil
from pathlib import Path
import posixpath # Use posixpath for consistent forward slashes in Tcl paths

from litex.build.generic_programmer import GenericProgrammer

def find_fpexpress():
    """
    Finds the FPExpress executable.

    Checks the system's PATH for the executable.

    Returns:
        str: The full path to the fpexpress executable.

    Raises:
        FileNotFoundError: If the executable cannot be found in the PATH.
    """
    # The command might be case-sensitive on some systems.
    # On Windows, it's typically FPExpress.exe, on Linux, fpexpress.
    fpexpress_cmd = "FPExpress" if platform.system() == "Windows" else "fpexpress"
    
    path = shutil.which(fpexpress_cmd)
    if path is None:
        # Try the other case as a fallback
        fpexpress_cmd = "fpexpress" if platform.system() == "Windows" else "FPExpress"
        path = shutil.which(fpexpress_cmd)

    if path is None:
        raise FileNotFoundError(
            f"'{fpexpress_cmd}' not found in the system PATH. "
            "Please ensure Microchip Libero/FlashPro Express is installed and its 'bin' directory is in your PATH."
        )
    return path

class FlashProExpressProgrammer(GenericProgrammer):
    """
    LiteX programmer for Microchip PolarFire devices using FlashPro Express.

    This class provides an interface compatible with the LiteX builder,
    allowing programming via the `builder.load()` method.
    """
    def __init__(self, device=None):
        self.device = device
        self.fpexpress_executable = find_fpexpress()
        
    def program_device(self, build_dir, project_name, device_string):
        """
        Generates and executes a Tcl script to program the device using a job file.
        """
        tcl = []
        
        # Construct paths using the provided build_dir.
        # Use posixpath to ensure forward slashes, as expected by Tcl.
        job_file_path = posixpath.join(build_dir, 'impl', 'designer', project_name, 'export', f'{project_name}.job')
        programmer_proj_path = posixpath.join(build_dir, 'impl', 'programmer')
        
        # Ensure the target directory for the job project exists.
        # FPExpress requires the location to be created beforehand.
        os.makedirs(programmer_proj_path, exist_ok=True)
        
        # The die name is required for the set_programming_action command
        die, _, _ = device_string.split("-")

        # Create Tcl script content
        tcl.append(f"# Generated for project: {project_name}")
        tcl.append(" ".join([
            "create_job_project",
            f"-job_project_location {{{programmer_proj_path}}}",
            f"-job_file {{{job_file_path}}}",
            "-overwrite 1"
        ]))
        tcl.append(" ".join([ "set_programming_action", f"-name {{{die}}}", "-action {PROGRAM}" ]))
        tcl.append(" ".join([ "run_selected_actions", "-prog_spi_flash 0", "-disable_prog_design 0" ]))
        tcl.append("save_project")
        tcl.append("puts \"\\nSUCCESS: Device programming script finished.\"")
        
        tcl_script_content = "\n".join(tcl)
        
        # Write Tcl script to a temporary file
        tcl_file = Path(build_dir) / "program_device.tcl"
        try:
            with open(tcl_file, "w") as f:
                f.write(tcl_script_content)
            print(f"Successfully created Tcl script at: {tcl_file}")
        except IOError as e:
            raise IOError(f"Failed to create Tcl script: {e}")

        # Execute the Tcl script using FPExpress
        print("\nExecuting FPExpress...")
        command = [self.fpexpress_executable, f"SCRIPT:{tcl_file.as_posix()}"]
        
        try:
            # Removed capture_output=True to allow FPExpress output to stream directly to the console.
            # The output will now be printed in real-time.
            result = subprocess.run(
                command, check=True, capture_output=False, text=True
            )
            print("--- FPExpress Output ---")
            print(result.stdout)
            print("------------------------")
            print("Device programming completed successfully!")
        except subprocess.CalledProcessError as e:
            print("Error: FPExpress execution failed.", file=sys.stderr)
            print(f"Return Code: {e.returncode}", file=sys.stderr)
            print("\n--- STDOUT ---", file=sys.stderr)
            print(e.stdout, file=sys.stderr)
            print("\n--- STDERR ---", file=sys.stderr)
            print(e.stderr, file=sys.stderr)
            raise
        finally:
            # Clean up the temporary Tcl script
            if tcl_file.exists():
                os.remove(tcl_file)
                print(f"Cleaned up temporary script: {tcl_file}")

    def load_bitstream(self, bitstream_filename, **kwargs):
        """
        Loads the bitstream by calling the program_device function.

        The LiteX builder calls this method and provides the path to the
        final bitstream/job file. We use its directory as the build directory.

        Args:
            bitstream_filename (str): Path to the generated bitstream file (.job).
            **kwargs: Additional programmer arguments. Expects 'device' for override.
        """
        bitstream_path = Path(bitstream_filename)
        
        # Robustly find the build directory. It's the directory that contains the 'impl' folder.
        build_dir_path = bitstream_path
        # This loop will go up the directory tree until it finds the parent of 'impl'.
        while build_dir_path.name != 'impl' and build_dir_path != build_dir_path.parent:
            build_dir_path = build_dir_path.parent
        
        if build_dir_path.name != 'impl':
            raise NotADirectoryError(f"Could not find 'impl' directory in the path of {bitstream_filename}")

        # The build_dir is the parent of the 'impl' directory.
        build_dir = str(build_dir_path.parent)
        project_name = bitstream_path.stem

        # Prioritize device from command-line/kwargs, fall back to device from platform.
        device = kwargs.get("device", self.device)
        if not device:
            raise ValueError("No device specified. "
                "Provide it with --device or set the 'device' attribute in the platform file.")

        print(f"--- Using FlashProExpress Programmer for device: {device} ---")
        self.program_device(build_dir=build_dir, project_name=project_name, device_string=device)

