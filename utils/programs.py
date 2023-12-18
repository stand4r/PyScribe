from subprocess import Popen, PIPE
import pickle
from os import path

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

def saveSession(files_array: list):
    with open('session.pkl', 'wb') as f:
        pickle.dump((files_array), f)

def loadSession() -> list:
    try:
        with open('session.pkl', 'rb') as f:
            files_array = pickle.load(f)
    except FileNotFoundError:
        with open('session.pkl', 'wb') as f:
            pickle.dump([], f)
        files_array = []
    return files_array

def exist_config(file_path):
    return path.exists(file_path)

def create_config(file_path):
    open(file_path, "w").write("{\n}")