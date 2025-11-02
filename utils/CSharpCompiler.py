import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class CSharpCompiler:
    """C# compilation and project build manager"""
    
    def __init__(self):
        self.compiler_path = self.detect_compiler()
        self.dotnet_path = self.detect_dotnet()
        
    def detect_compiler(self) -> Optional[str]:
        """Detect C# compiler (csc)"""
        # Try to find csc in common locations
        possible_paths = [
            r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
            r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe",
            "/usr/bin/csc",
            "/usr/bin/mcs"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
                
        try:
            result = subprocess.run(["which", "csc"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        return None
    
    def detect_dotnet(self) -> Optional[str]:
        """Detect .NET CLI"""
        try:
            result = subprocess.run(["dotnet", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                return "dotnet"
        except:
            pass
            
        return None
    
    def compile_single_file(self, file_path: str, output_path: str = None, 
                          references: List[str] = None) -> Tuple[bool, str, str]:
        """Compile single C# file"""
        if not self.compiler_path:
            return False, "", "C# compiler not found. Install .NET Framework or Mono."
            
        file_path = Path(file_path)
        if not file_path.exists():
            return False, "", f"File not found: {file_path}"
            
        if not output_path:
            output_path = file_path.with_suffix('.exe')
            
        # Default references for basic C# programs
        if references is None:
            references = [
                "System.dll",
                "System.Core.dll",
                "System.Data.dll",
                "System.Xml.dll"
            ]
            
        cmd = [self.compiler_path]
        
        # Add references
        for ref in references:
            cmd.extend(["/reference:", ref])
            
        # Add output
        cmd.extend(["/out:", str(output_path)])
        
        # Add target (console application)
        cmd.append("/target:exe")
        
        # Add file to compile
        cmd.append(str(file_path))
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=file_path.parent)
            
            if result.returncode == 0:
                return True, str(output_path), result.stdout
            else:
                return False, "", result.stderr
                
        except Exception as e:
            return False, "", f"Compilation error: {str(e)}"
    
    def compile_with_dotnet(self, file_path: str, output_dir: str = None) -> Tuple[bool, str, str]:
        """Compile using .NET CLI"""
        if not self.dotnet_path:
            return False, "", ".NET CLI not found. Install .NET SDK."
            
        file_path = Path(file_path)
        project_dir = file_path.parent
        
        # Create temporary console project if no .csproj exists
        csproj_path = project_dir / f"{file_path.stem}.csproj"
        if not csproj_path.exists():
            self.create_console_project(csproj_path, file_path.name)
            
        try:
            # Build project
            cmd = [self.dotnet_path, "build", str(csproj_path)]
            if output_dir:
                cmd.extend(["--output", output_dir])
                
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_dir)
            
            if result.returncode == 0:
                # Find output executable
                output_exe = self.find_output_executable(project_dir, file_path.stem)
                return True, output_exe, result.stdout
            else:
                return False, "", result.stderr
                
        except Exception as e:
            return False, "", f".NET build error: {str(e)}"
    
    def create_console_project(self, csproj_path: Path, main_file: str):
        """Create a simple console project file"""
        project_content = f"""<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net6.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <StartupObject>Program</StartupObject>
  </PropertyGroup>

</Project>"""
        
        csproj_path.write_text(project_content)
        
        # Also create Program.cs if it doesn't exist
        program_cs = csproj_path.parent / "Program.cs"
        if not program_cs.exists() and main_file != "Program.cs":
            # Rename the main file to Program.cs or create a stub
            main_file_path = csproj_path.parent / main_file
            if main_file_path.exists():
                # Copy content to Program.cs
                program_cs.write_text(main_file_path.read_text())
    
    def find_output_executable(self, project_dir: Path, project_name: str) -> str:
        """Find the output executable path"""
        # Look in bin directories
        possible_locations = [
            project_dir / "bin" / "Debug" / "net6.0" / f"{project_name}.exe",
            project_dir / "bin" / "Release" / "net6.0" / f"{project_name}.exe",
            project_dir / "bin" / "Debug" / "net7.0" / f"{project_name}.exe",
            project_dir / "bin" / "Release" / "net7.0" / f"{project_name}.exe",
            project_dir / "bin" / "Debug" / "net8.0" / f"{project_name}.exe",
            project_dir / "bin" / "Release" / "net8.0" / f"{project_name}.exe",
        ]
        
        for location in possible_locations:
            if location.exists():
                return str(location)
                
        return ""
    
    def run_csharp_program(self, exe_path: str, args: str = "", 
                          working_dir: str = None) -> Tuple[bool, str, str]:
        """Run compiled C# program"""
        if not os.path.exists(exe_path):
            return False, "", f"Executable not found: {exe_path}"
            
        try:
            cmd = [exe_path]
            if args:
                cmd.extend(args.split())
                
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=working_dir or Path(exe_path).parent
            )
            
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                return False, result.stdout, result.stderr
                
        except Exception as e:
            return False, "", f"Execution error: {str(e)}"
    
    def build_solution(self, solution_path: str, configuration: str = "Debug") -> Tuple[bool, str, str]:
        """Build .NET solution"""
        if not self.dotnet_path:
            return False, "", ".NET CLI not found"
            
        solution_path = Path(solution_path)
        if not solution_path.exists():
            return False, "", f"Solution file not found: {solution_path}"
            
        try:
            cmd = [self.dotnet_path, "build", str(solution_path), "--configuration", configuration]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=solution_path.parent)
            
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                return False, result.stdout, result.stderr
                
        except Exception as e:
            return False, "", f"Build error: {str(e)}"


class CSharpProjectManager:
    """Manager for C# projects and solutions"""
    
    def __init__(self):
        self.compiler = CSharpCompiler()
    
    def detect_project_type(self, directory: str) -> str:
        """Detect project type in directory"""
        dir_path = Path(directory)
        
        # Check for .sln files
        sln_files = list(dir_path.glob("*.sln"))
        if sln_files:
            return "solution"
            
        # Check for .csproj files
        csproj_files = list(dir_path.glob("*.csproj"))
        if csproj_files:
            return "project"
            
        # Check for .cs files
        cs_files = list(dir_path.glob("*.cs"))
        if cs_files:
            return "source"
            
        return "unknown"
    
    def create_new_project(self, project_name: str, directory: str, 
                         project_type: str = "console") -> Tuple[bool, str]:
        """Create new C# project"""
        if not self.compiler.dotnet_path:
            return False, ".NET CLI not found"
            
        try:
            project_dir = Path(directory) / project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            
            cmd = [self.compiler.dotnet_path, "new", project_type, 
                  "--name", project_name, "--output", str(project_dir)]
                  
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, f"Project created successfully in {project_dir}"
            else:
                return False, result.stderr
                
        except Exception as e:
            return False, f"Error creating project: {str(e)}"