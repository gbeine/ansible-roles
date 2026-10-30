
import ipaddress
import jinja2

@jinja2.pass_context
def netmask2prefixlength(context, netmask):
    """

    :param context: Jinja2 context.
    :param netmask: The netmask
    :returns: The prefix length of the netmask
    """
    result = ipaddress.IPv4Network("0.0.0.0/{0}".format(netmask)).prefixlen

    return result


@jinja2.pass_context
def netaddress(context, address, netmask):
    """

    :param context: Jinja2 context.
    :param address: The address
    :param netmask: The netmask
    :returns: Calculates the network address based on IP address and netmask
    """
    result = str(ipaddress.IPv4Network("{0}/{1}".format(address, netmask), strict=False).network_address)

    return result


@jinja2.pass_context
def map2ipv6(context, address):
    """

    :param context: Jinja2 context.
    :param address: The address
    :returns: Converts an IPv4 address to an IPv4-mapped IPv6 address in hex notation, e.g. ::ffff:a00:1
    """
    value = int(ipaddress.IPv4Address(address))
    result = "::ffff:{0:x}:{1:x}".format(value >> 16, value & 0xffff)

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'ipv4_netmask2prefixlength': netmask2prefixlength,
            'ipv4_netaddress': netaddress,
            'ipv4_map2ipv6': map2ipv6
        }
