
import jinja2

@jinja2.pass_context
def endpoints_from_zones(context, zones):
    """

    :param context: Jinja2 context.
    :param zones: The list of zones
    :returns: The list of endpoints
    """
    result = []
    for zone in zones:
        if 'endpoints' not in zone:
            continue
        for endpoint in zone['endpoints']:
            if 'parent' not in zone:
                result.append( { 'name': endpoint, 'host': endpoint } )
            else:
                result.append({'name': endpoint, 'host': endpoint, 'log_duration': 0 })

    return result


class FilterModule(object):
    """Pragmatic dict filters."""

    def filters(self):
        return {
            'monitoring_icinga_config__endpoints_from_zones': endpoints_from_zones
        }
