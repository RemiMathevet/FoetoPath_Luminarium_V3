"""Tests pour rate_limiter.py — backoff exponentiel, cleanup, thread safety."""

import time
import threading

import pytest

from rate_limiter import LoginRateLimiter


class TestDelaySchedule:

    def test_no_delay_under_3_failures(self):
        rl = LoginRateLimiter()
        rl.record_failure("user", "1.2.3.4")
        rl.record_failure("user", "1.2.3.4")
        assert rl.get_delay("user", "1.2.3.4") == 0.0

    def test_delay_at_3_failures(self):
        rl = LoginRateLimiter()
        for _ in range(3):
            rl.record_failure("user", "1.2.3.4")
        delay = rl.get_delay("user", "1.2.3.4")
        assert delay > 0
        assert delay <= 5.0

    def test_delay_at_4_failures(self):
        rl = LoginRateLimiter()
        for _ in range(4):
            rl.record_failure("user", "1.2.3.4")
        delay = rl.get_delay("user", "1.2.3.4")
        assert delay <= 15.0

    def test_delay_at_6_plus_failures(self):
        rl = LoginRateLimiter()
        for _ in range(6):
            rl.record_failure("user", "1.2.3.4")
        delay = rl.get_delay("user", "1.2.3.4")
        assert delay <= 120.0

    def test_delay_decreases_over_time(self):
        rl = LoginRateLimiter()
        for _ in range(3):
            rl.record_failure("user", "1.2.3.4")
        d1 = rl.get_delay("user", "1.2.3.4")
        time.sleep(0.1)
        d2 = rl.get_delay("user", "1.2.3.4")
        assert d2 < d1


class TestSuccessReset:

    def test_success_resets_counter(self):
        rl = LoginRateLimiter()
        for _ in range(5):
            rl.record_failure("user", "1.2.3.4")
        rl.record_success("user", "1.2.3.4")
        assert rl.get_delay("user", "1.2.3.4") == 0.0
        assert rl.get_attempt_count("user", "1.2.3.4") == 0

    def test_success_on_unknown_user(self):
        rl = LoginRateLimiter()
        rl.record_success("nobody", "0.0.0.0")
        assert rl.get_attempt_count("nobody", "0.0.0.0") == 0


class TestKeyIsolation:

    def test_different_users_isolated(self):
        rl = LoginRateLimiter()
        for _ in range(5):
            rl.record_failure("alice", "1.1.1.1")
        assert rl.get_delay("alice", "1.1.1.1") > 0
        assert rl.get_delay("bob", "1.1.1.1") == 0.0

    def test_different_ips_isolated(self):
        rl = LoginRateLimiter()
        for _ in range(5):
            rl.record_failure("user", "10.0.0.1")
        assert rl.get_delay("user", "10.0.0.1") > 0
        assert rl.get_delay("user", "10.0.0.2") == 0.0

    def test_case_insensitive_username(self):
        rl = LoginRateLimiter()
        for _ in range(3):
            rl.record_failure("Alice", "1.1.1.1")
        assert rl.get_delay("alice", "1.1.1.1") > 0


class TestCleanup:

    def test_cleanup_removes_old_entries(self):
        rl = LoginRateLimiter(cleanup_interval=0)
        rl.record_failure("old", "1.1.1.1")
        time.sleep(0.05)
        rl.record_failure("new", "2.2.2.2")
        assert rl.get_attempt_count("old", "1.1.1.1") == 0


class TestAttemptCount:

    def test_count_increments(self):
        rl = LoginRateLimiter()
        assert rl.get_attempt_count("u", "1.1.1.1") == 0
        rl.record_failure("u", "1.1.1.1")
        assert rl.get_attempt_count("u", "1.1.1.1") == 1
        rl.record_failure("u", "1.1.1.1")
        assert rl.get_attempt_count("u", "1.1.1.1") == 2


class TestThreadSafety:

    def test_concurrent_failures(self):
        rl = LoginRateLimiter()
        errors = []

        def hammer():
            try:
                for _ in range(50):
                    rl.record_failure("user", "1.1.1.1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert rl.get_attempt_count("user", "1.1.1.1") == 200
