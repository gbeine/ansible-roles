import jinja2
import re

@jinja2.pass_context
def rawstring(context, thestring, quote = '"'):
    """

    :param context: Jinja2 context.
    :param thestring: The string
    :returns: The string output
    """
    if re.match('^raw:', thestring):
        result = re.sub('^raw:', '', thestring)
    else:
        result = quote + thestring + quote

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'rawstring': rawstring,
        }
