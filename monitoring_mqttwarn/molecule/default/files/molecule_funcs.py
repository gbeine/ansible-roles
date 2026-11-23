# Functions of the molecule tests, defaults.functions loads them


def molecule_format(data, srv=None):
    return 'molecule-formatted ' + str(data.get('payload', ''))
