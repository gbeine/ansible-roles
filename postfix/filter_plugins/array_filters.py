
import jinja2

@jinja2.contextfilter
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


@jinja2.contextfilter
def merge_by_key(context, thefirst, thesecond, thekey):
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
        key = thefirst[i][thekey]
        pos[key] = i
        result.append(thefirst[i])
    for item in thesecond:
        key = item[thekey]
        if key in pos:
            result[pos[key]] = item
        else:
            result.append(item)

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'merge_by_splittedkey': merge_by_splittedkey,
            'merge_by_key': merge_by_key,
        }
