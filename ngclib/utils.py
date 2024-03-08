"""
The utilities file for ngclib supports the foundation of how ngclearn does its dynamic loading of attributes and
modules. When the file is imported it will automatically search for a file (default `json_files/modules.json`,
or passed as --modules="json_files/modules.json") to load all the modules for dynamic loading. Without this file when
the controller tries to load a component or command class it will be unable to find it. Please see the `modules.schema`
file in the `json_schemes` folder for more details on how to create the modules.json file.
"""
import sys, uuid, os, json
from importlib import import_module

## Globally tracking all the modules, and attributes have been dynamically loaded
_Loaded_Attributes = {}
_Loaded_Modules = {}


def check_attributes(obj, required, fatal=False):
    """
    This function will verify that a provided object has the requested attributes.

    :param obj: Object that should have the attributes
    :param required: A list of required attributes by string name
    :param fatal: If true an Attribute error will be thrown (default False)
    :return: Boolean only returns if not fatal, if the object has the required attributes
    """
    if required is None:
        return True
    for atr in required:
        if not hasattr(obj, atr):
            if not fatal:
                return False
            if hasattr(obj, "name"):
                raise AttributeError(str(obj.name) + " is missing the required attribute of " + atr)
            else:
                raise AttributeError("Checked object is missing the required attribute of " + atr)
    return True


def load_module(module_path, match_case=False, absolute_path=False):
    """
    Trys to load a module from the provided path.
    :param module_path: Module path, supports compound modules such as `ngclib.commands`
    :param match_case: If true the module must case match exactly (default false)
    :param absolute_path: If true tries to import exactly what is passed to module path (default false)
    :return: the module that has been loaded
    """
    #Return if we have already loaded this module
    if module_path in _Loaded_Modules.keys():
        return _Loaded_Modules[module_path]
    #Unkown module
    module_name = None
    if absolute_path:
        module_name = module_path
    else:
        #Extract the final module from the module_path
        final_mod = module_path.split('.')[-1]
        final_mod = final_mod if match_case else final_mod.lower()

        #Try to match the final module to any currently loaded module
        for module in sys.modules:
            last_mod = module.split('.')[-1]
            last_mod = last_mod if match_case else last_mod.lower()
            if final_mod == last_mod:
                print("Loading module from " + module)
                module_name = module
                break

        #Will only be None if no imported modules match the import name
        if module_name is None:
            raise RuntimeError("Failed to find dynamic import for \"" + module_path + "\"")

    mod = import_module(module_name)
    _Loaded_Modules[module_path] = mod
    return mod

def load_from_path(path, match_case=False, absolute_path=False):
    """
    Loads an attribute/module from a specified path. If not using the absolute path the module name and attribute
    names will be assumed to be the same.

    :param path: path to attribute/module to load, will try to find the attribute/module if not already loaded
    :param match_case: If true the module must case match exactly (default false)
    :param absolute_path: If true tries to import exactly what is passed to module path (default false)
    :return: The attribute at the path
    """
    if absolute_path is True:
        module_name = '.'.join(path.split('.')[:-1])
        class_name = path.split('.')[-1]
        match_case = True
    else:
        module_name = path
        class_name = path

    return load_attribute(module_path=module_name, attribute_name=class_name,
                          match_case=match_case, absolute_path=absolute_path)


def load_attribute(attribute_name, module_path=None, match_case=False, absolute_path=False):
    """
    Loads a specific attribute from a specified module

    :param attribute_name: name of the attribute to load
    :param module_path: module to load the attribute from, will use the attribute name if None (default None)
    :param match_case: If true the module must case match exactly (default false)
    :param absolute_path: If true tries to import exactly what is passed to module path (default false)
    :return: the loaded attribute
    """
    if attribute_name in _Loaded_Attributes.keys():
        return _Loaded_Attributes[attribute_name]

    if attribute_name is None:
        raise RuntimeError()

    mod = load_module(attribute_name if module_path is None else module_path, match_case=match_case, absolute_path=absolute_path)

    attribute_name = attribute_name if match_case else attribute_name[0].upper() + attribute_name[1:]

    try:
        attr = getattr(mod, attribute_name)
    except AttributeError:
        raise RuntimeError("Could not find an attribute with name \"" + attribute_name + "\" in module " + mod.__name__) \
            from None

    _Loaded_Attributes[attribute_name] = attr
    return attr

def make_unique_path(directory, root_name=None):
    """
    This block of code will make a uniquely named directory inside the specified output folder.
    If the root name already exists it will append a UID to the root name to not overwrite data
    :param directory: The root directory to save models to
    :param root_name: (Default None) The root name for the model to be saved to, if none it will just use the UID
    :return: path to created directory
    """
    uid = uuid.uuid4()
    if root_name is None:
        root_name = str(uid)
        print("generated path will be named \"" + str(root_name) + "\"")

    elif os.path.isdir(directory + "/" + root_name):
        root_name += "_" + str(uid)
        print("root path already exists, generated path will be named \"" + str(root_name) + "\"")

    path = directory + "/" + str(root_name)
    os.mkdir(path)
    return path

def check_serializable(dict):
    """
    Verifies that all the values of a dictionary are serializable
    :param dict: dictionary to check
    :return: list of all the keys that are not serializable
    """
    bad_keys = []
    for key in dict.keys():
        try:
            json.dumps(dict[key])
        except:
            bad_keys.append(key)
    return bad_keys
