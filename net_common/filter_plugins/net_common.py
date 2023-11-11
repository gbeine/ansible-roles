
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


@jinja2.pass_context
def netaddress(context, address, netmask):
    """

    :param context: Jinja2 context.
    :param address: The address
    :param netmask: The netmask
    :returns: Calculates the network address based on IP address and netmask
    """
    address_split = address.split('.')
    netmask_split = netmask.split('.')

    netaddress_split = [None] * 4

    for i in range(0,4):
        split = int(address_split[i]) & int(netmask_split[i])
        netaddress_split[i] = str(split)

    result = '.'.join(netaddress_split)

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'net_common__netmask2prefixlength': netmask2prefixlength,
            'net_common__netaddress': netaddress
        }
