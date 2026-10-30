
import jinja2

@jinja2.pass_context
def fill_up_to(context, thevalue, maxlength, fill_with = ' '):
    """

    :param context: Jinja2 context.
    :param thevalue: The value, converted to a string
    :param maxlength: The length the result is filled up to
    :param fill_with: The string used for filling, it is cut off when it does not fit completely
    :returns: The value filled up to exactly maxlength characters, longer values are returned unchanged
    """
    if len(fill_with) == 0:
        raise ValueError('fill_with must not be empty')

    result = str(thevalue)
    while len(result) < maxlength:
        result = result + fill_with[:maxlength - len(result)]

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'whitespaces_fill_up_to': fill_up_to,
        }
