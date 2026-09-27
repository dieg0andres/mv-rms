import unittest

from staging.request_policy import unsafe_request_allowed


HOST = 'private.example.invalid:4443'
ORIGIN = f'https://{HOST}'


class StagingOriginPolicyTests(unittest.TestCase):
    def test_exact_private_origin_required_for_unsafe_methods(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            with self.subTest(method=method):
                self.assertTrue(unsafe_request_allowed({
                    'REQUEST_METHOD': method, 'HTTP_ORIGIN': ORIGIN,
                    'HTTP_SEC_FETCH_SITE': 'same-origin',
                }, HOST))
                for invalid in (None, 'null', 'http://' + HOST,
                                ORIGIN + '/', 'https://other.example.invalid:4443',
                                'https://untrusted.example.invalid:4443'):
                    with self.subTest(method=method, invalid=invalid):
                        self.assertFalse(unsafe_request_allowed({
                            'REQUEST_METHOD': method, 'HTTP_ORIGIN': invalid,
                        }, HOST))

    def test_cross_site_rejected_even_with_exact_origin(self):
        self.assertFalse(unsafe_request_allowed({
            'REQUEST_METHOD': 'POST', 'HTTP_ORIGIN': ORIGIN,
            'HTTP_SEC_FETCH_SITE': 'cross-site',
        }, HOST))

    def test_safe_requests_retain_basic_auth_prompt_path(self):
        for method in ('GET', 'HEAD', 'OPTIONS'):
            with self.subTest(method=method):
                self.assertTrue(unsafe_request_allowed({'REQUEST_METHOD': method}, HOST))


if __name__ == '__main__':
    unittest.main()
