
import jinja2

@jinja2.pass_context
def bool(context, thevar):
    """

    :param context: Jinja2 context.
    :param thevar: the variable to test
    :returns: true if var is bool
    """
    result = False
    result = result or str(thevar).lower == 'true'
    result = result or str(thevar).lower == 'false'

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'bool': bool,
        }
