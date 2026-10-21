import pytest

from app import create_app
from app.config import TestConfig


@pytest.fixture()
def app():
    return create_app(TestConfig)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """Registered + logged-in client (personal SaaS account)."""
    client.post(
        "/auth/register",
        data={"email": "user@example.com", "password": "passw0rd1", "password2": "passw0rd1"},
    )
    return client
