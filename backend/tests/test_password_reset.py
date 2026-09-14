"""Tests for the password reset flow: password_reset/store.py,
password_reset/mailer.py, and the forgot/reset routes in routes/auth.py.

MongoDB is replaced by a small in-memory collection that supports exactly the
operations those modules use, so the tests exercise the real query logic
(single use, expiry, retiring older tokens) without a database.
"""

import smtplib
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from bson import ObjectId
from fastapi import BackgroundTasks, HTTPException

import config
import password_reset.mailer as mailer
import password_reset.store as store
import routes.auth as auth_routes
from auth.security import hash_password, verify_password
from models import ForgotPasswordRequest, ResetPasswordRequest


def _matches(document, query):
    for key, condition in query.items():
        value = document.get(key)
        if isinstance(condition, dict) and "$gt" in condition:
            if value is None or not value > condition["$gt"]:
                return False
        elif value != condition:
            return False
    return True


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query):
        return next((d for d in self.documents if _matches(d, query)), None)

    def insert_one(self, document):
        document.setdefault("_id", ObjectId())
        self.documents.append(document)
        return mock.Mock(inserted_id=document["_id"])

    def update_many(self, query, update):
        matched = [d for d in self.documents if _matches(d, query)]
        for document in matched:
            document.update(update["$set"])
        return mock.Mock(matched_count=len(matched))

    def update_one(self, query, update):
        document = self.find_one(query)
        if document is not None:
            document.update(update["$set"])
        return mock.Mock(matched_count=1 if document is not None else 0)

    def find_one_and_update(self, query, update):
        document = self.find_one(query)
        if document is None:
            return None
        before = dict(document)
        document.update(update["$set"])
        return before


class TokenStoreTests(unittest.TestCase):

    def setUp(self):
        self.tokens = FakeCollection()
        patcher = mock.patch.object(store, "password_reset_tokens_collection", self.tokens)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_a_hash_of_the_token_is_stored(self):
        token = store.create_reset_token("user-1", lifetime_minutes=30)

        stored = self.tokens.documents[0]
        self.assertEqual(stored["token_hash"], store.hash_token(token))
        self.assertNotIn(token, str(stored))
        self.assertGreaterEqual(len(token), 40)

    def test_token_can_be_used_once(self):
        token = store.create_reset_token("user-1", lifetime_minutes=30)

        self.assertEqual(store.consume_reset_token(token)["user_id"], "user-1")
        self.assertIsNone(store.consume_reset_token(token))

    def test_expired_token_is_rejected(self):
        issued = datetime.now(timezone.utc) - timedelta(minutes=31)
        token = store.create_reset_token("user-1", lifetime_minutes=30, now=issued)

        self.assertIsNone(store.consume_reset_token(token))

    def test_new_token_retires_the_previous_one(self):
        first = store.create_reset_token("user-1", lifetime_minutes=30)
        second = store.create_reset_token("user-1", lifetime_minutes=30)

        self.assertIsNone(store.consume_reset_token(first))
        self.assertIsNotNone(store.consume_reset_token(second))

    def test_unknown_or_malformed_token_is_rejected(self):
        store.create_reset_token("user-1", lifetime_minutes=30)

        for token in ("not-a-real-token", "", None, 12345):
            self.assertIsNone(store.consume_reset_token(token))


class ForgotPasswordRouteTests(unittest.TestCase):

    def setUp(self):
        self.user_id = ObjectId()
        self.users = FakeCollection([{
            "_id": self.user_id,
            "name": "Sam",
            "email": "sam@example.com",
            "password_hash": hash_password("old-password"),
        }])
        self.tokens = FakeCollection()

        for target, attribute, value in (
            (auth_routes, "users_collection", self.users),
            (store, "password_reset_tokens_collection", self.tokens),
        ):
            patcher = mock.patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _request(self, email):
        tasks = BackgroundTasks()
        response = auth_routes.forgot_password(ForgotPasswordRequest(email=email), tasks)
        return response, tasks

    def test_response_is_identical_for_known_and_unknown_email(self):
        known, _ = self._request("sam@example.com")
        unknown, _ = self._request("nobody@example.com")

        self.assertEqual(known, unknown)
        self.assertEqual(
            known["message"],
            "If an account exists with this email address, password reset "
            "instructions have been sent.",
        )

    def test_unknown_email_creates_no_token_and_sends_nothing(self):
        _, tasks = self._request("nobody@example.com")

        self.assertEqual(self.tokens.documents, [])
        self.assertEqual(len(tasks.tasks), 0)

    def test_known_email_creates_a_token_and_queues_the_email(self):
        _, tasks = self._request("sam@example.com")

        self.assertEqual(len(self.tokens.documents), 1)
        self.assertEqual(self.tokens.documents[0]["user_id"], str(self.user_id))
        self.assertEqual(len(tasks.tasks), 1)
        self.assertIs(tasks.tasks[0].func, mailer.send_reset_email)
        self.assertEqual(tasks.tasks[0].args[0], "sam@example.com")


class ResetPasswordRouteTests(unittest.TestCase):

    def setUp(self):
        self.user_id = ObjectId()
        self.users = FakeCollection([{
            "_id": self.user_id,
            "name": "Sam",
            "email": "sam@example.com",
            "password_hash": hash_password("old-password"),
        }])
        self.tokens = FakeCollection()

        for target, attribute, value in (
            (auth_routes, "users_collection", self.users),
            (store, "password_reset_tokens_collection", self.tokens),
        ):
            patcher = mock.patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.token = store.create_reset_token(str(self.user_id), lifetime_minutes=30)

    def _reset(self, token, password):
        return auth_routes.reset_password(
            ResetPasswordRequest(token=token, new_password=password)
        )

    def _stored_hash(self):
        return self.users.documents[0]["password_hash"]

    def test_valid_token_sets_the_new_password(self):
        response = self._reset(self.token, "brand-new-password")

        self.assertIn("reset", response["message"])
        self.assertTrue(verify_password("brand-new-password", self._stored_hash()))
        self.assertFalse(verify_password("old-password", self._stored_hash()))
        self.assertIn("password_changed_at", self.users.documents[0])

    def test_token_cannot_be_reused(self):
        self._reset(self.token, "brand-new-password")

        with self.assertRaises(HTTPException) as raised:
            self._reset(self.token, "another-password")

        self.assertEqual(raised.exception.status_code, 400)
        self.assertTrue(verify_password("brand-new-password", self._stored_hash()))

    def test_invalid_token_is_rejected_and_password_unchanged(self):
        with self.assertRaises(HTTPException) as raised:
            self._reset("forged-token", "brand-new-password")

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("invalid or has expired", raised.exception.detail)
        self.assertTrue(verify_password("old-password", self._stored_hash()))

    def test_short_password_is_rejected_without_using_up_the_token(self):
        with self.assertRaises(HTTPException) as raised:
            self._reset(self.token, "short")

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("at least 8", raised.exception.detail)

        # The link still works with a valid password.
        self._reset(self.token, "brand-new-password")
        self.assertTrue(verify_password("brand-new-password", self._stored_hash()))

    def test_overlong_password_is_rejected_without_using_up_the_token(self):
        with self.assertRaises(HTTPException) as raised:
            self._reset(self.token, "x" * 73)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIsNotNone(store.consume_reset_token(self.token))


class MailerTests(unittest.TestCase):

    def _config(self, **overrides):
        values = {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": 587,
            "SMTP_USERNAME": None,
            "SMTP_PASSWORD": None,
            "SMTP_FROM": "MoveWell AI <no-reply@example.com>",
            "SMTP_SECURITY": "starttls",
            "FRONTEND_URL": "https://app.example.com",
            "PASSWORD_RESET_TOKEN_MINUTES": 30,
            "PASSWORD_RESET_LOG_LINKS": False,
        }
        values.update(overrides)
        patchers = [mock.patch.object(config, key, value) for key, value in values.items()]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_email_contains_the_reset_link(self):
        self._config()

        message = mailer.build_reset_email("sam@example.com", "Sam", "tok/en+1")

        self.assertEqual(message["To"], "sam@example.com")
        self.assertIn(
            "https://app.example.com/reset-password?token=tok%2Fen%2B1",
            message.get_content(),
        )

    def test_configured_smtp_delivers_the_message(self):
        self._config()

        with mock.patch.object(mailer, "_deliver") as deliver:
            mailer.send_reset_email("sam@example.com", "Sam", "token-123")

        deliver.assert_called_once()
        self.assertIn("token-123", deliver.call_args.args[0].get_content())

    def test_smtp_failure_is_logged_not_raised(self):
        self._config()

        with mock.patch.object(mailer, "_deliver", side_effect=smtplib.SMTPException("down")):
            with self.assertLogs("movewell.password_reset", level="ERROR"):
                mailer.send_reset_email("sam@example.com", "Sam", "token-123")

    def test_unconfigured_smtp_sends_nothing_and_does_not_log_the_link(self):
        self._config(SMTP_HOST=None)

        with mock.patch.object(mailer, "_deliver") as deliver:
            with self.assertLogs("movewell.password_reset", level="ERROR") as logs:
                mailer.send_reset_email("sam@example.com", "Sam", "secret-token")

        deliver.assert_not_called()
        self.assertNotIn("secret-token", "".join(logs.output))

    def test_log_links_flag_logs_the_link_when_smtp_is_unconfigured(self):
        self._config(SMTP_HOST=None, PASSWORD_RESET_LOG_LINKS=True)

        with self.assertLogs("movewell.password_reset", level="WARNING") as logs:
            mailer.send_reset_email("sam@example.com", "Sam", "dev-token")

        self.assertIn("reset-password?token=dev-token", "".join(logs.output))


if __name__ == "__main__":
    unittest.main()
