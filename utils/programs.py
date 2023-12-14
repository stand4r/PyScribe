from subprocess import Popen, PIPE

def compile_program_c(path: str) -> str:
    exe_path = path.rsplit(".", 1)[0] + ".exe"
    command = ["gcc", path, "-o", exe_path]
            
    compile_process = Popen(command, stderr=PIPE, stdout=PIPE, universal_newlines=True)
    stdout, stderr = compile_process.communicate()
    if compile_process.returncode != 0:
        raise ValueError(f"Compilation completed with error {compile_process.returncode}")      
    else:
        return exe_path
     
def compile_program_cpp(path: str) -> str:
    exe_path = path.rsplit(".", 1)[0] + ".exe"
    command = ["g++", path, "-o", exe_path]
            
    compile_process = Popen(command, stderr=PIPE, stdout=PIPE, universal_newlines=True)
    stdout, stderr = compile_process.communicate()
    if compile_process.returncode != 0:
        raise ValueError(f"Compilation completed with error {compile_process.returncode}")      
    else:
        return exe_path