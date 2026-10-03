"""Request boundary for a browser Basic-auth staging adapter."""


def unsafe_request_allowed(environ, staging_host):
    if environ.get('REQUEST_METHOD', '').upper() in ('GET', 'HEAD', 'OPTIONS'):
        return True
    expected_origin = f'https://{staging_host}'
    return (environ.get('HTTP_ORIGIN') == expected_origin
            and environ.get('HTTP_SEC_FETCH_SITE', '').lower() != 'cross-site')
