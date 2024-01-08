from subprocess import Popen, PIPE
import pickle
from os import path, getuid, getlogin
from json import load


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

def loadConfigFromJson(file_path, need_dict):
    if !path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as file_json:
            return load(file_json)[need_dict]
    except:
        return None

def loadJsonFile(file_path):
    if !path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as file_json:
            return load(file_path)
    except:
        return None

def dumpConfigToJson(file_path, data):
    if !path.exists(file_path):
        return 0
    try:
        with open(file_path, 'r+') as f:
            f.seek(0)
            f.write(json.dumps(json_data))
            f.truncate()
        return 1
    except:
        return 0


