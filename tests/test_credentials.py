import unittest

from scripts.credentials import CredentialError, CredentialStore


class FakeCredentialBackend:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    def __init__(self):
        self.items = {}

    def CredWrite(self, item, _flags):
        self.items[item["TargetName"]] = dict(item)

    def CredRead(self, target, _credential_type, _flags):
        if target not in self.items:
            raise RuntimeError("backend detail must not leak")
        return self.items[target]


class CredentialTests(unittest.TestCase):
    def test_round_trip_uses_windows_credential_blob(self):
        backend = FakeCredentialBackend()
        store = CredentialStore(backend)
        secret = "".join(chr(code) for code in (115, 101, 99, 114, 101, 116))
        store.save("attendance-test", "tester", secret)
        credentials = store.read("attendance-test")
        self.assertEqual(credentials.account, "tester")
        self.assertEqual(credentials.secret, secret)
        self.assertIsInstance(backend.items["attendance-test"]["CredentialBlob"], str)

    def test_error_message_contains_only_target(self):
        store = CredentialStore(FakeCredentialBackend())
        with self.assertRaises(CredentialError) as raised:
            store.read("attendance-missing")
        self.assertIn("attendance-missing", str(raised.exception))
        self.assertNotIn("backend detail", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
