
import jinja2

@jinja2.pass_context
def hostdict2hostarray(context, thedict):
    """

    :param context: Jinja2 context.
    :param thedict: The dict containing hosts
    :returns: The hostname/address mapping as list
    """
    result = []

    for key, address in thedict.items():
        result.append({ 
            'address': address,
            'hostname': inverthostname(context, key),
        })

    return result


@jinja2.pass_context
def inverthostname(context, hostname):
    """

    :param context: Jinja2 context.
    :param hostname: The hostname to invert
    :returns: The inverted hostname
    """
    parts = hostname.split('.')
    parts.reverse()

    result = ".".join(str(x) for x in parts)

    return result

class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'hostdict2hostarray': hostdict2hostarray,
            'inverthostname': inverthostname,
        }
