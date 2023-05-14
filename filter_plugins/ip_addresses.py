
import jinja2

@jinja2.pass_context
def netmask2prefixlength(context, netmask):
    """

    :param context: Jinja2 context.
    :param netmask: The netmask
    :returns: The prefix length of the netmask
    """
    # See https://stackoverflow.com/a/38085892
    result = sum(bin(int(x)).count('1') for x in netmask.split('.'))

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'netmask2prefixlength': netmask2prefixlength,
            'netmask2cidr': netmask2prefixlength,
        }
