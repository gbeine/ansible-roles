
import jinja2

@jinja2.pass_context
def fill_up_to(context, thevalue, maxlength, fill_with = ' '):
    """

    :param context: Jinja2 context.
    :param thedict: The dict
    :param thekey: The key
    :returns: The default value or the value from the dict
    """
    result = str(thevalue)
    if len(result) < maxlength:
        while len(result) < maxlength:
            result = result + fill_with

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'fill_up_to': fill_up_to,
        }
