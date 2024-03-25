from ngclib.commands.command import Command
from ngclib.utils import extract_args, check_attributes


class Multiclamp(Command):
    """
    There are times when a model will have many clamp calls as there is a need to clamp many different values in a model
    at the same time. As a solution to this ngclib provides the multiclamp command. This command is used to set a wide
    range of value to all compartments with the same name across all provided compartments.
    """

    def __init__(self, components=None, clamp_name=None, **kwargs):
        """
        Required Calls on Components: ['clamp', 'name']

        :param components: a list of components to call clamp on
        :param clamp_name: a keyword to bind the input for this command do
        """
        super().__init__(components=components, required_calls=['clamp'])
        if clamp_name is None:
            raise RuntimeError("A multiclamp command requires a \'clamp_name\' to bind to for construction")

        self.clamp_name = clamp_name

    def __call__(self, *args, **kwargs):
        try:
            vals = extract_args([self.clamp_name], *args, **kwargs)
        except RuntimeError:
            raise RuntimeError("Multiclamp, " + str(self.clamp_name) + " is missing from keyword arguments or a "
                                                                       "positional arguments can be provided")

        for compartment, value in vals[self.clamp_name].items():
            for component in self.components:
                if check_attributes(component, compartment, fatal=False):
                    self.components[component].clamp(compartment, value)