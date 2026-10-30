
import ipaddress
import jinja2

@jinja2.pass_context
def network_cidr(context, address, prefix):
    """

    :param context: Jinja2 context.
    :param address: An IPv4 or IPv6 address within the network
    :param prefix: The prefix length or the IPv4 netmask
    :returns: The network in normalized CIDR notation, e.g. fd00::99:0/112
    """
    result = str(ipaddress.ip_network("{0}/{1}".format(address, prefix), strict=False))

    return result


@jinja2.pass_context
def address_normalize(context, address):
    """

    :param context: Jinja2 context.
    :param address: An IPv4 or IPv6 address
    :returns: The address in normalized notation, e.g. fd00::99:1 for fd00:0:0:0::99:1
    """
    result = str(ipaddress.ip_address(address))

    return result


class FilterModule(object):
    """Pragmatic IPv4 and IPv6 address filters."""

    def filters(self):
        return {
            'ip_network_cidr': network_cidr,
            'ip_address_normalize': address_normalize
        }
