import pickle
import shutil
from os import path, getlogin, name, environ, remove, makedirs, listdir

try:
    from os import getuid
except:
    pass
from json import load, dumps


def saveSession(files_array: list):
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)

        if temp_dir:
            file_path = path.join(temp_dir, "session.pkl")
    else:
        file_path = "session.pkl"
    with open(file_path, 'wb') as f:
        pickle.dump((files_array), f)


def loadSession() -> list:
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "session.pkl")
    else:
        file_path = "session.pkl"
    try:
        with open(file_path, 'rb') as f:
            files_array = pickle.load(f)
    except FileNotFoundError:
        with open(file_path, 'wb') as f:
            pickle.dump([], f)
        files_array = []
    return files_array


def saveRecent(recent_files: list):
    recent_files = list(set(recent_files))
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "recent.pkl")
    else:
        file_path = "recent.pkl"
    with open(file_path, 'wb') as f:
        pickle.dump((recent_files), f)


def removeRecentFile():
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "recent.pkl")
    else:
        file_path = "recent.pkl"
    remove(file_path)


def clearCache():
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path_recent = path.join(temp_dir, "recent.pkl")
            file_path_session = path.join(temp_dir, "session.pkl")
    else:
        file_path_recent = "recent.pkl"
        file_path_session = "session.pkl"
    remove(file_path_recent)
    remove(file_path_session)


def loadRecent() -> list:
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, "recent.pkl")
    else:
        file_path = "recent.pkl"
    try:
        with open(file_path, 'rb') as f:
            files_array = pickle.load(f)
            files_array = list(set(files_array))
            return files_array
    except FileNotFoundError:
        with open(file_path, 'wb') as f:
            pickle.dump([], f)
        return []


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


def load_settings(scriptPath):
    configPath = scriptPath + r"/config/settings.json"
    return load(open(configPath, "r"))


def update_settings(scriptPath, data):
    with open(scriptPath + r"/config/settings.json", 'r+') as f:
        f.seek(0)
        f.write(dumps(data))
        f.truncate()


def backup(file):
    backup_folder = 'backups'
    backup_name = path.basename(file.split('.')[0]) + '_backup.txt'
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, backup_folder)
    else:
        file_path = backup_folder
    if not path.exists(file_path):
        makedirs(file_path)
    shutil.copyfile(file, path.join(file_path, backup_name))
    with open(path.join(file_path, backup_name), "a") as f:
        f.write("\n" + file)


def clear_backup():
    backup_folder = 'backups'
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, backup_folder)
    else:
        file_path = backup_folder
    if path.exists(file_path):
        for name_file in listdir(file_path):
            remove(path.join(file_path, name_file))


def check_backups():
    files = list()
    backup_folder = 'backups'
    if name == 'nt':
        temp_dir = environ.get('TEMP', None)
        if temp_dir:
            file_path = path.join(temp_dir, backup_folder)
    else:
        file_path = backup_folder
    if path.exists(file_path):
        for name_file in listdir(file_path):
            files.append(path.join(file_path, name_file))
        return files
    return []


def restore_backup():
    files = check_backups()
    for file in files:
        with open(file, "r") as f:
            text = f.readlines()
        with open(text[-1], "w") as f:
            f.write("".join(text[0:-1]))
    clear_backup()
