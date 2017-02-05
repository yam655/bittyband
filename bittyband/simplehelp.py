

class SimpleHelp:

    def __init__(self, config = None, player = None):
        self.data = []

    def prepare(self, txt):
        self.data = txt

    def prepare_keys(self, lister):
        lister.add_variant("Q", "^J")

    def get_order(self):
        return self.data

    def return_value(self, line):
        return self.data[line]
