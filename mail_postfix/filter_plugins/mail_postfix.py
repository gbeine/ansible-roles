
import jinja2

@jinja2.pass_context
def domain_name(context, fqdn):
    """

    :param context: Jinja2 context.
    :param fqdn: The full qualified domain name
    :returns: The domain name
    """
    result = fqdn.split('.')

    return '.'.join(result[1:])


@jinja2.pass_context
def merge_by_splittedkey(context, thefirst, thesecond, *thekeys):
    """

    :param context: Jinja2 context.
    :param thefirst: the first array
    :param thesecond: the second array, overriding elements with the same key
    :param thekey: The key
    :returns: The merged array
    """
    result = []
    pos = {}
    for i in range(0, len(thefirst)):
        key = build_identifier(thefirst[i], thekeys)
        pos[key] = i
        result.append(thefirst[i])
    for item in thesecond:
        key = build_identifier(item, thekeys)
        if key in pos:
            result[pos[key]] = item
        else:
            result.append(item)

    return result

def build_identifier(item, thekeys):
    result = ''
    for key in thekeys:
        result = result + item[key]

    return result


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


@jinja2.pass_context
def value_or_default(context, thedict, thekey, thedefault):
    """

    :param context: Jinja2 context.
    :param thedict: The dict
    :param thekey: The key
    :param thedefault: The default value if key does not exist
    :returns: The default value or the value from the dict
    """
    result = thedefault
    if thekey in thedict:
        result = thedict[thekey]
    return result


@jinja2.pass_context
def value_or_ternary(context, thedict, thekey, iftrue, iffalse, thedefault):
    """

    :param context: Jinja2 context.
    :param thedict: The dict
    :param thekey: The key
    :param thedefault: The default value if key does not exist
    :returns: The default value or the value from the dict
    """
    result = thedefault
    if thekey in thedict:
        if thedict[thekey]:
            result = iftrue
        else:
            result = iffalse
    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'mail_postfix__domain_name': domain_name,
            'mail_postfix__fill_up_to': fill_up_to,
            'mail_postfix__merge_by_splittedkey': merge_by_splittedkey,
            'mail_postfix__value_or_default': value_or_default,
            'mail_postfix__value_or_ternary': value_or_ternary
        }
