"""Small, dependency-free fixtures for package tests."""

from __future__ import annotations

from django.contrib.auth import get_user_model


def make_user(*, username: str = "member", is_staff: bool = False):
    """Create a local test user with the supplied privileges."""
    return get_user_model().objects.create_user(
        username=username,
        password="safe-test-password",
        is_staff=is_staff,
    )
