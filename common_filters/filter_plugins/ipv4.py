
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
def map2ipv6(context, address, site):
    """

    :param context: Jinja2 context.
    :param address: The IPv4 address
    :param site: The first three groups of the IPv6 address (the /48 of the site), e.g. fde9:f508:05c6
    :returns: Maps an IPv4 address into the site, the second and third octet become the fourth group
              and the last octet the last group, all in hex, e.g. fde9:f508:5c6:a863::1 for 192.168.99.1
    """
    octets = ipaddress.IPv4Address(address).packed
    groups = str(site).strip(':').split(':')
    if len(groups) != 3:
        raise ValueError("site must consist of three groups, e.g. fde9:f508:05c6: {0}".format(site))

    prefix = 0
    for group in groups:
        if not 1 <= len(group) <= 4 or any(c not in '0123456789abcdefABCDEF' for c in group):
            raise ValueError("site must consist of three groups of up to four hex digits: {0}".format(site))
        prefix = (prefix << 16) | int(group, 16)

    value = (prefix << 80) | (octets[1] << 72) | (octets[2] << 64) | octets[3]
    result = str(ipaddress.IPv6Address(value))

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'ipv4_netmask2prefixlength': netmask2prefixlength,
            'ipv4_netaddress': netaddress,
            'ipv4_map2ipv6': map2ipv6
        }
