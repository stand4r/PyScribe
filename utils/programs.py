import pickle
from os import path, getlogin, name
import ast

try:
    from os import getuid
except:
    pass
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


def load_settings(scriptPath):
    configPath = scriptPath + r"/config/settings.json"
    return load(open(configPath, "r"))


def update_settings(scriptPath, data):
    with open(scriptPath + r"/config/settings.json", 'r+') as f:
        f.seek(0)
        f.write(dumps(data))
        f.truncate()

def analyze_code(code):
    # Создаем пустой словарь для автодополнения
    autocomplete_dict = {}

    # Разбираем код в абстрактное синтаксическое дерево (AST)
    tree = ast.parse(code)

    # Обходим AST, чтобы найти все определения и импорты
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Если узел - определение функции, добавляем ее имя в словарь
            autocomplete_dict[node.name] = "function"
        elif isinstance(node, ast.ClassDef):
            # Если узел - определение класса, добавляем его имя в словарь
            autocomplete_dict[node.name] = "class"
        elif isinstance(node, ast.Import):
            # Если узел - импорт, добавляем имена импортированных модулей в словарь
            for alias in node.names:
                autocomplete_dict[alias.name.split(".")[0]] = "module"
        elif isinstance(node, ast.Constant):
            autocomplete_dict[node.name] = "constant"
        
    return autocomplete_dict
