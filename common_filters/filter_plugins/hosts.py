
import jinja2

@jinja2.pass_context
def addresslist(context, nametable, reverse=True):
    """

    :param context: Jinja2 context.
    :param nametable: A dict with hostnames and addresses
    :param reverse: Are the hostnames in reverse order
    :returns: A list of address/hostname entries
    """
    result = []

    for host, address in nametable.items():
        if reversed:
            h = host.split('.')
            host = '.'.join(reversed(h))
        result.append({'address': address, 'hostname': host})

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'hosts__addresslist': addresslist
        }
