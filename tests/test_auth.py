REGISTER_DATA = {
    "email": "user@example.com",
    "password": "passw0rd1",
    "password2": "passw0rd1",
}


def test_root_redirects_anonymous_to_register(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/register")


def test_register_creates_account_and_session(client):
    response = client.post("/auth/register", data=REGISTER_DATA)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tasks/")
    # now authenticated: root points to the board
    assert client.get("/").headers["Location"].endswith("/tasks/")


def test_register_rejects_duplicate_email(client):
    client.post("/auth/register", data=REGISTER_DATA)
    client.get("/auth/logout")
    response = client.post("/auth/register", data=REGISTER_DATA)
    assert response.status_code == 200
    assert "مسجّل مسبقاً" in response.get_data(as_text=True)


def test_register_rejects_mismatched_passwords(client):
    data = {**REGISTER_DATA, "password2": "different1"}
    response = client.post("/auth/register", data=data)
    assert response.status_code == 200
    assert "غير متطابقتين" in response.get_data(as_text=True)


def test_login_wrong_password_rejects(client):
    client.post("/auth/register", data=REGISTER_DATA)
    client.get("/auth/logout")
    response = client.post(
        "/auth/login", data={"email": REGISTER_DATA["email"], "password": "wrong-pass"}
    )
    assert response.status_code == 200
    assert "غير صحيحة" in response.get_data(as_text=True)


def test_login_success_redirects_to_board(client):
    client.post("/auth/register", data=REGISTER_DATA)
    client.get("/auth/logout")
    response = client.post(
        "/auth/login",
        data={"email": REGISTER_DATA["email"], "password": REGISTER_DATA["password"]},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tasks/")
    followed = client.get(response.headers["Location"])
    assert followed.status_code == 200


def test_board_requires_login(client):
    response = client.get("/tasks/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_logout_ends_session(client):
    client.post("/auth/register", data=REGISTER_DATA)
    response = client.get("/auth/logout")
    assert response.status_code == 302
    # anonymous root goes back to registration
    assert client.get("/").headers["Location"].endswith("/auth/register")
