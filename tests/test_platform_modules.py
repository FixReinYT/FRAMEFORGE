import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lucas_animator"))

from local_accounts import AccountError, LocalAccountStore
from continuity import normalize_tracks, insert_frame, delete_frame
from pro_effects import apply_pro_effect
from entitlements import EntitlementService, BillingUnavailable


class AccountTests(unittest.TestCase):
    def test_register_login_restore_logout_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAccountStore(directory)
            user, recovery = store.create_account("Artist_01", "artist@example.test", "Artist", "long-password-1")
            self.assertEqual(user["username"], "Artist_01")
            self.assertEqual(store.login("ARTIST_01", "long-password-1")["email"], "artist@example.test")
            self.assertEqual(store.restore_session()["display_name"], "Artist")
            store.logout()
            self.assertIsNone(store.restore_session())
            new_recovery = store.reset_password("ARTIST@example.test", recovery, "another-password-2")
            self.assertNotEqual(recovery, new_recovery)
            store.login("artist@example.test", "another-password-2")
            self.assertIsNotNone(store.restore_session())

    def test_duplicate_and_bad_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAccountStore(directory)
            store.create_account("artist", "a@example.test", "Artist", "long-password-1")
            with self.assertRaises(AccountError):
                store.create_account("ARTIST", "b@example.test", "Other", "long-password-2")
            with self.assertRaises(AccountError):
                store.login("artist", "wrong-password")

    def test_profile_requires_matching_session(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAccountStore(directory)
            store.create_account("artist", "a@example.test", "Artist", "long-password-1")
            store.create_account("other", "b@example.test", "Other", "long-password-2")
            with self.assertRaises(AccountError):
                store.update_profile("artist", "Changed")
            store.login("artist", "long-password-1")
            with self.assertRaises(AccountError):
                store.update_profile("other", "Changed")
            self.assertEqual(store.update_profile("ARTIST", "New Name")["display_name"], "New Name")
            store.logout()
            self.assertIsNone(store.restore_session())

    def test_avatar_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalAccountStore(directory)
            store.create_account("artist", "a@example.test", "Artist", "long-password-1")
            store.login("artist", "long-password-1")
            source = Path(directory) / "source.png"
            Image.new("RGB", (20, 30), "red").save(source)
            profile = store.set_avatar("artist", str(source))
            with Image.open(profile["avatar_path"]) as avatar:
                self.assertEqual(avatar.size, (256, 256))


class ContinuityTests(unittest.TestCase):
    def test_tracks_survive_frame_insert_duplicate_and_delete(self):
        tracks = {"Head": {"name": "Head", "color": "#42d6c4", "points": {"0": [10, 20], "2": [30, 40]}}}
        inserted = insert_frame(tracks, 1)
        self.assertEqual(inserted["Head"]["points"], {"0": [10, 20], "3": [30, 40]})
        duplicated = insert_frame(tracks, 1, duplicate_from=0)
        self.assertEqual(duplicated["Head"]["points"]["1"], [10, 20])
        deleted = delete_frame(duplicated, 0)
        self.assertEqual(deleted["Head"]["points"], {"0": [10, 20], "2": [30, 40]})

    def test_track_validation(self):
        clean = normalize_tracks({"Eye": {"color": "#42d6c4", "points": {"0": [3, 4]}}}, 2, 10, 10)
        self.assertEqual(clean["Eye"]["points"]["0"], [3, 4])
        with self.assertRaises(ValueError):
            normalize_tracks({"Eye": {"color": "#42d6c4", "points": {"3": [3, 4]}}}, 2, 10, 10)


class ProEffectTests(unittest.TestCase):
    def test_premium_effects_return_valid_rgba_images(self):
        source = Image.new("RGBA", (24, 24), (120, 80, 40, 180))
        for effect in ("glow", "duotone", "film_grain"):
            result = apply_pro_effect(source, effect, 45)
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.size, source.size)
            if effect == "glow":
                self.assertGreaterEqual(result.getchannel("A").getpixel((0, 0)), 180)
            else:
                self.assertEqual(result.getchannel("A").getpixel((0, 0)), 180)

    def test_unknown_effect_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_pro_effect(Image.new("RGBA", (4, 4)), "made_up")


class BillingTests(unittest.TestCase):
    def test_no_provider_never_grants_or_fakes_pro(self):
        service = EntitlementService()
        self.assertFalse(service.has("pro_filters", {"username": "artist"}))
        with self.assertRaises(BillingUnavailable):
            service.begin_checkout({"username": "artist"})


if __name__ == "__main__":
    unittest.main()
