
import re
import jinja2
import json

@jinja2.pass_context
def dict2string(context, thedict, innerjoin = '=', outerjoin = ' '):
    """

    :param context: Jinja2 context.
    :param thedict: The dict
    :param theprefix: The prefix to prepend on each key
    :returns: The join result as string
    """
    result = ''
    for key, value in thedict.items():
        if len(result) > 0:
            result = result + outerjoin
        result = result + key + innerjoin + str(value)

    return result

@jinja2.pass_context
def dict2json(context, thedict, remove_empty = True):
    """

    :param context: Jinja2 context.
    :param thedict: The dict
    :param remove_empty: Remove empty value while transforming into JSON
    :returns: The join result as string
    """
    def remove(d):
        r = {}
        for a, b in d.items():
            if b:
                if isinstance(b, dict):
                    r[a] = remove(b)
                elif isinstance(b, list):
                    r[a] = list(filter(None, b))
                else:
                    r[a] = b
        return r

    result = remove(thedict) if remove_empty else thedict

    return json.dumps(result)

@jinja2.pass_context
def join_with_prefix(context, thedict, theprefix, innerjoin = '=', outerjoin = ' '):
    """

    :param context: Jinja2 context.
    :param thedict: The dict
    :param theprefix: The prefix to prepend on each key
    :returns: The join result as string
    """
    result = ''
    for key, value in thedict.items():
        if len(result) > 0:
            result = result + outerjoin
        result = result + theprefix + key + innerjoin + str(value)

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


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'dict2string': dict2string,
            'dict2json': dict2json,
            'join_with_prefix': join_with_prefix,
            'value_or_ternary': value_or_ternary,
            'value_or_default': value_or_default,
        }
