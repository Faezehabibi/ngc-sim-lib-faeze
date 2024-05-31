from ngcsimlib.utils import make_unique_path, check_attributes, check_serializable, load_from_path
from ngcsimlib.logger import warn, info
from ngcsimlib.utils import get_compartment_by_name, \
    get_context, add_context, get_current_path, get_current_context, set_new_context
from ngcsimlib.compilers.command_compiler import dynamic_compile
import json, os


class Context:
    """
    The ngc context is the foundation of all ngclearn models and the central operational construct for simulating
    complex systems. The controller is the object that organizes all the components, commands, and connections that
    characterize a complex system and/or model to be simulated over time (and was referred to as the
    "nodes-and-cables" system in earlier versions of ngc-learn).

    On a software engineering side of things the contexts are how ngcsimlib organizes all components and compartments
    made during the runtime. Every context is named and if a context is constructed in the future with the same name
    the original context will be provided with access to all previously added components and commands. There is one
    additional note about naming, as contexts can be nestest each one keeps a path from the top level context ('/')
    appending its name to end of the path. This is the true value that is used to reproduce a context in teh future.
    So if a context is nested on creation the path will need to be provided to access it again (This can also just be
    done by nesting contexts again)
    """

    def __new__(cls, name, *args, **kwargs):
        """
        When building a context if it exists return the existing context else make a new one

        Args:
             name: the name of the context
        """
        assert len(name) > 0
        con = get_context(str(name))
        if con is None:
            return super().__new__(cls)
        else:
            return con

    def __init__(self, name):
        """
        Builds the initial context object, if `__new__` provides an already initialized context do not continue with
        construction as it is already initialized. This is where the path to a context is assigned so their paths are
        dependent on the current context path upon creation.

        Args:
             name: The name of the new context can not be empty
        """
        if hasattr(self, "_init"):
            return
        self._init = True

        add_context(str(name), self)
        self.components = {}
        self._component_paths = {}
        self.commands = {}
        self.name = name

        # Used for contexts
        self.path = get_current_path() + "/" + str(name)
        self._last_context = ""

        self._json_objects = {"ops": [], "components": {}, "commands": {}}

    def __enter__(self):
        """
        Contexts provide an enter to track the previous context and set themselves as the current one
        """
        self._last_context = get_current_path()
        set_new_context(self.path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Contexts provide an exit to return to the previous context upon exiting
        """
        set_new_context(self._last_context)

    def get_components(self, *component_names):
        """
        Gets all the components by name in a context

        Args:
            component_names: an arbitrary list of component names to get

        Returns:
             either a list of components or a single component depending on the number of components being retrieved
        """
        if len(component_names) == 0:
            return None
        _components = []
        for a in component_names:
            if a in self.components.keys():
                _components.append(self.components[a])
            else:
                warn(f"Could not fine a component with the name \"{a}\" in the context")
        return _components if len(component_names) > 1 else _components[0]

    def register_op(self, op):
        """
        Adds an operation to the local json storage for saving

        Args:
             op: the operation to save
        """
        self._json_objects['ops'].append(op.dump())

    def register_command(self, klass, *args, components=None, command_name=None, **kwargs):
        """
        Adds a command to the local json storage for saving

        Args:
            klass: the class of the command

            args: the positional arguments to the constructor

            components: the components passed into the command (default: None)

            command_name: the command name

            kwargs: the keyword arguments passed into the command
        """
        _components = [components.name for components in components]
        self._json_objects['commands'][command_name] = {"class": klass, "components": _components, "args": args,
                                                        "kwargs": kwargs}

    def register_component(self, component, *args, **kwargs):
        """
        Adds a component to the local json storage for saving, will provide a warning for all values it fails to
        serialize into a json file

        Args:
            component: the component object to save

            args: the positional arguments to build the component

            kwargs: the keyword arguments to build the component
        """
        if component.path in self._component_paths.keys():
            return
        self._component_paths[component.path] = component

        c_path = component.path
        c_class = component.__class__.__name__

        _args = []

        for a in args:
            try:
                json.dumps([a])
                _args.append(a)
            except:
                info("Failed to serialize \"", a, "\" in ", component.path, sep="")

        _kwargs = {key: value for key, value in kwargs.items()}
        bad_keys = check_serializable(_kwargs)
        for key in bad_keys:
            del _kwargs[key]
            info("Failed to serialize \"", key, "\" in ", component.path, sep="")

        obj = {"class": c_class, "args": _args, "kwargs": _kwargs}
        self._json_objects['components'][c_path] = obj

    def add_component(self, component):
        """
        Adds a component to the context if it does not exist already in the context

        Args:
            component: the component being added to the context
        """
        if component.name not in self.components.keys():
            self.components[component.name] = component
        else:
            warn(f"Failed to add {component.name} to current context as it already exists")

    def add_command(self, command, name=None):
        """
        Adds a command to the context, if no name is provided it will use the command's internal name

        Args:
            command:

            name: The name of the command (default: None)
        """
        name = command.name if name is None else name

        self.commands[name] = command
        self.__setattr__(name, command)

    def save_to_json(self, directory, model_name=None, custom_save=True):
        """
        Dumps all the required json files to rebuild the current controller to a specified directory. If there is a
        `save` command present on the controller and custom_save is True, it will run that command as well.

        Args:
            directory: The top level directory to save the model to

            model_name: The name of the model, if None or if there is already a
                model with that name a uid will be used or appended to the name
                respectively. (Default: None)

            custom_save: A boolean that if true will attempt to call the `save`
                command if present on the controller (Default: True)

        Returns:
            a tuple where the first value is the path to the model, and the
                second is the path to the custom save folder if custom_save is
                true and None if false
        """
        path = make_unique_path(directory, model_name)

        with open(path + "/ops.json", 'w') as fp:
            json.dump(self._json_objects['ops'], fp, indent=4)

        with open(path + "/commands.json", 'w') as fp:
            json.dump(self._json_objects['commands'], fp, indent=4)

        with open(path + "/components.json", 'w') as fp:
            hyperparameters = {}

            for c_path, component in self._json_objects['components'].items():
                if component['kwargs'].get('parameter_map', None) is not None:
                    for cKey, pKey in component['kwargs']['parameter_map'].items():
                        pVal = component['kwargs'][cKey]
                        if pKey not in hyperparameters.keys():
                            hyperparameters[pKey] = []
                        hyperparameters[pKey].append((c_path, cKey, pVal))

            hp = {}
            for param in hyperparameters.keys():
                matched = True
                hp[param] = None
                for _, _, pVal in hyperparameters[param]:
                    if hp[param] is None:
                        hp[param] = pVal
                    elif hp[param] != pVal:
                        del hp[param]
                        matched = False
                        break

                for c_path, cKey, _ in hyperparameters[param]:
                    if matched:
                        self._json_objects['components'][c_path]['kwargs'][cKey] = param

                    else:
                        warn("Unable to extract hyperparameter", param,
                             "as it is mismatched between components. Parameter will not be extracted")

            for c_path, component in self._json_objects['components'].items():
                if "parameter_map" in component['kwargs'].keys():
                    del component['kwargs']["parameter_map"]

            obj = {"components": self._json_objects['components']}
            if len(hp.keys()) != 0:
                obj["hyperparameters"] = hp

            json.dump(obj, fp, indent=4)

        if custom_save:
            os.mkdir(path + "/custom")
            if check_attributes(self, ['save']):
                self.save(path + "/custom")
            else:
                warn("Context doesn't have a save command registered. Saving all components")
                for component in self.components.values():
                    if check_attributes(component, ['save']):
                        component.save(path + "/custom")

        return (path, path + "/custom") if custom_save else (path, None)

    def load_from_dir(self, directory, custom_folder="/custom"):
        """
        Builds a controller from a directory. Designed to be used with
        `save_to_json`.

        Args:
            directory: the path to the model

            custom_folder: The name of the custom data folder for building
                components. (Default: `/custom`)
        """
        self.make_components(directory + "/components.json", directory + custom_folder)
        self.make_ops(directory + "/ops.json")
        self.make_commands(directory + "/commands.json")

    def make_components(self, path_to_components_file, custom_file_dir=None):
        """
        Loads a collection of components from a json file. Follow
        `components.schema` for the specific format of the json file.

        Args:
            path_to_components_file: the path to the file, including the name
                and extension

            custom_file_dir: the path to the custom directory for custom load methods,
                this directory is named `custom` if the save_to_json method is
                used. (Default: None)
        """
        with open(path_to_components_file, 'r') as file:
            componentsConfig = json.load(file)

            parameterMap = {}
            components = componentsConfig["components"]
            if "hyperparameters" in componentsConfig.keys():
                for c_path, component in components.items():
                    for pKey, pValue in componentsConfig["hyperparameters"].items():
                        for cKey, cValue in component['kwargs'].items():
                            if pKey == cValue:
                                component['kwargs'][cKey] = pValue
                                parameterMap[cKey] = pKey

            for c_path, component in components.items():
                klass = load_from_path(component["class"])
                _args = component['args']
                _kwargs = component['kwargs']
                obj = klass(*_args, **_kwargs, parameter_map=parameterMap)

                if check_attributes(obj, ["load"]):
                    obj.load(custom_file_dir)

    def make_ops(self, path_to_ops_file):
        """
        Loads a collection of ops from a json file. Follow `ops.schema`
        for the specific format of this json file.

        Args:
            path_to_ops_file: the path of the file, including the name
                and extension
        """
        with open(path_to_ops_file, 'r') as file:
            ops = json.load(file)
            for op in ops:
                self._make_op(op)

    def make_commands(self, path_to_commands_file):
        """
        Goes through the provided command file and builds and adds all commands to the context

        Args:
            path_to_commands_file: a path to the commands file

        """
        with open(path_to_commands_file, 'r') as file:
            commands = json.load(file)
            for c_name, command in commands.items():
                if command['class'] == "dynamic_compiled":
                    self.compile_command_key(
                        *self.get_components(*command['components']), compile_key=command['compile_key'], name=c_name)
                else:
                    klass = load_from_path(command['class'])
                    klass(*command['args'], **command['kwargs'], components=self.get_components(*command['components']),
                          command_name=c_name)

    def _make_op(self, op_spec):
        klass = load_from_path(op_spec["class"])
        _sources = []
        for s in op_spec["sources"]:
            if isinstance(s, dict):
                _sources.append(self._make_op(s))
            else:
                _sources.append(get_compartment_by_name(get_current_context(), s))

        obj = klass(*_sources)

        if op_spec['destination'] is None:
            return obj

        else:
            dest = get_compartment_by_name(get_current_context(), op_spec['destination'])
            dest << obj

    @staticmethod
    def dynamicCommand(fn):
        """
        Provides a decorator that will automatically bind the decorated method to the current context.
        Note this if this is called from a context object it will still use the current context not the object

        Args:
            fn: The wrapped method

        Returns: The method

        """
        if get_current_context() is not None:
            get_current_context().__setattr__(fn.__name__, fn)
        return fn

    def compile_command_key(self, *components, compile_key, name=None):
        """
        Compiles a given set of components with a given compile key.
        It will automatically add it to the context after compiling

        Args:
            *components: positional arguments for all components

            compile_key: a keyword argument for the compile key

            name: the name to register the command under (default: None)

        Returns:
            The compiled command, the argument list needed to run the command
        """
        cmd, args = dynamic_compile(*components, compile_key=compile_key)
        if name is None:
            name = compile_key

        klass = "dynamic_compiled"
        _components = [components.name for components in components]
        self._json_objects['commands'][name] = {"class": klass, "components": _components, "compile_key": compile_key}
        self.__setattr__(name, cmd)
        return cmd, args