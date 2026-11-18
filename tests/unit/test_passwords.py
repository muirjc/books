"""T016: Argon2id password hashing (Constitution Principle IX)."""

from __future__ import annotations

from argon2 import PasswordHasher

from book_tracker.auth.passwords import DUMMY_HASH, hash_password, needs_rehash, verify_password


def test_hash_is_argon2id_and_verifies() -> None:
    hashed = hash_password("correct horse")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "correct horse")
    assert not verify_password(hashed, "wrong horse")


def test_verify_rejects_garbage_hash() -> None:
    assert not verify_password("not-a-hash", "anything")


def test_needs_rehash_for_weaker_parameters() -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("pw")
    assert needs_rehash(weak)
    assert not needs_rehash(hash_password("pw"))


def test_dummy_hash_never_matches_common_passwords() -> None:
    assert DUMMY_HASH.startswith("$argon2id$")
    assert not verify_password(DUMMY_HASH, "password123")
