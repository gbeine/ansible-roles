
import jinja2


@jinja2.pass_context
def print_openhab_item(context, item):
    """

    :param context: Jinja2 context.
    :param item: An openHAB item definition
    :returns: The formatted string
    """
    result = "{} {}".format(item['type'], item['name'])

    if 'label' in item:
        result = result + " \"" + item['label'] + "\""
    if 'icon' in item:
        result = result + " <" + item['icon'] + ">"
    if 'groups' in item:
        result = result + " (" + ','.join(item['groups']) + ")"
    if 'tags' in item:
        result = result + " [" + ','.join(item['tags']) + "]"
    if 'bindings' in item:
        result = result + " {" + parameters(item['bindings']) + "}"

    return result


@jinja2.pass_context
def print_openhab_sitemap(context, sitemap, name):
    """

    :param context: Jinja2 context.
    :param sitemap: An openHAB sitemap definition
    :returns: The formatted string
    """
    result = "sitemap {}".format(name)

    if 'label' in sitemap:
        result = result + " label=\"" + sitemap['label'] + "\""

    if 'elements' in sitemap:
        result = result + " {\n"
        result = result + elements(sitemap['elements'])
        result = result + "}"

    return result


@jinja2.pass_context
def print_openhab_thing(context, item):
    """

    :param context: Jinja2 context.
    :param item: The thing or bridge
    :returns: The formatted string
    """
    if 'is_bridge' in item and item['is_bridge']:
        result = bridge(item)
    else:
        result = thing(item)

    return result


def bridge(item):
    result = "Bridge {}".format(thing_definition(item))

    return result


def thing(item):
    result = "Thing {}".format(thing_definition(item))

    return result


def thing_definition(item):
    result = "{}:{}:{}".format(item['binding'], item['type'], item['thing'])

    if 'label' in item:
        result = "{} \"{} \"".format(result, item['label'])
    if 'bridge' in item:
        result = "{} ({})".format(result, item['bridge'])
    if 'location' in item:
        result = "{} @ \"{} \"".format(result, item['location'])

    if 'parameters' in item:
        result = "{} [ {} ]".format(result, parameters(item['parameters']))

    if 'channels' in item:
        result = result + " {\n  Channels:\n"
        result = result + channels(item['channels'])
        result = result + "}"

    return result


def parameters(parameters):
    result = ""
    for p, v in parameters.items():
        if isinstance(v, bool):
            r = "{}={}".format(p, str(v).lower())
        elif isinstance(v, int):
            r = "{}={}".format(p, v)
        else:
            r = "{}=\"{}\"".format(p, v)
        result = "{}, {}".format(result, r) if len(result) > 0 else "{}".format(r)

    return result


def channels(channels):
    result = ""
    for c in channels:
        r = "    Type {} : {}".format(c['type'], c['name'])
        if 'parameters' in c:
            r = "{} [ {} ]".format(r, parameters(c['parameters']))
        result = result + r + "\n"

    return result


def elements(elements):
    result = ""
    for e in elements:
        r = "    {} item={}".format(e['type'], e['item'])
        result = result + r + "\n"

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'smarthome_openhab_item': print_openhab_item,
            'smarthome_openhab_sitemap': print_openhab_sitemap,
            'smarthome_openhab_thing': print_openhab_thing
        }
