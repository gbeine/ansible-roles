
import jinja2

@jinja2.pass_context
def short(context, fqdn):
    """

    :param context: Jinja2 context.
    :param fqdn: The full qualified domain name
    :returns: The hostname
    """
    result = fqdn.split('.')

    return result[0]


@jinja2.pass_context
def reverse(context, fqdn):
    """

    :param context: Jinja2 context.
    :param fqdn: The full qualified domain name
    :returns: The FQDN in reverse order
    """
    splitted = fqdn.split('.')

    return '.'.join(reversed(splitted))


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'hostname_short': short,
            'hostname_reverse': reverse
        }
