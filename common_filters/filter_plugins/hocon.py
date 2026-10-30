import jinja2
import re

_BARE_KEY_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def _quote(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _render_key(key):
    key = str(key)
    return key if _BARE_KEY_RE.match(key) else _quote(key)


def _render_scalar(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    return _quote(str(value))


def _render_entries(value, indent, step):
    pad = ' ' * indent

    return '\n'.join(
        '{0}{1} = {2}'.format(pad, _render_key(k), _render(v, indent, step))
        for k, v in value.items()
    )


def _render(value, indent, step):
    pad, pad_in = ' ' * indent, ' ' * (indent + step)

    if isinstance(value, dict):
        if not value:
            return '{}'
        body = _render_entries(value, indent + step, step)
        return '{\n' + body + '\n' + pad + '}'

    if isinstance(value, (list, tuple)):
        if not value:
            return '[]'
        body = '\n'.join(
            '{0}{1}'.format(pad_in, _render(v, indent + step, step))
            for v in value
        )
        return '[\n' + body + '\n' + pad + ']'

    return _render_scalar(value)


@jinja2.pass_context
def to_hocon(context, value, root=False, step=2):
    """

    :param context: Jinja2 context.
    :param value: The data structure (dict/list/scalar) to render.
    :param root: If True and value is a dict, render it without the outer
                 braces and with the top level keys not indented
                 (idiomatic for standalone .conf files).
    :param step: Indentation width in spaces.
    :returns: The value rendered as a HOCON string.
    """
    if root and isinstance(value, dict):
        return _render_entries(value, 0, step)

    return _render(value, 0, step)


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'to_hocon': to_hocon
        }
