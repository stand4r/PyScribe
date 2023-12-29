from subprocess import Popen, PIPE
import pickle
from os import path, getuid, getlogin


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

def get_username():
    if os.name == 'nt':
        username = getlogin()
    else:
        import pwd
        username = pwd.getpwuid(getuid())[0]

    return username