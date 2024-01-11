from subprocess import Popen, PIPE
import pickle
from os import path, getuid, getlogin, name
from json import load, dumps


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
    if name == 'nt':
        username = getlogin()
    else:
        import pwd
        username = pwd.getpwuid(getuid())[0]
    return username

def get_scriptdir():
    return path.dirname(path.realpath(__file__))


def loadConfigFromJson(file_path, need_dict):
    if not path.exists(file_path): 
        return None
    try:
        with open(file_path, "r") as file_json:
            return load(file_json)[need_dict]
    except:
        return None

def dumpJsonFile(file_path, json_data):
    try:
        with open(file_path, 'r+') as f:
            f.seek(0)
            f.write(dumps(json_data))
            f.truncate()
    except:
        return None

def loadJsonFile(file_path):
    if not path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as file_json:
            return load(file_json)
    except:
        return None

def load_settings(scriptpath):
    configpath = scriptpath+r"/config/settings.json"
    try:
        return load(open(configpath, "r"))
    except:
        with open(configpath, "w") as file_json:
            file_json.write("{}")
        return load(open(configpath, "r"))

