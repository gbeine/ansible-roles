
import jinja2

@jinja2.pass_context
def bool(context, thevar):
    """

    :param context: Jinja2 context.
    :param thevar: the variable to test
    :returns: true if var is bool
    """
    result = False
    result = result or lower(str(thevar)) == 'true'
    result = result or lower(str(thevar)) == 'false'

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'bool': bool,
        }
