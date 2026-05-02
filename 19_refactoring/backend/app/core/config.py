ALLOWED_ORIGIN = "http://localhost:3000"
PING_INTERVAL = 10
PONG_TIMEOUT = 5

SECRET_KEY = "dev-secret-key-do-not-use-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

USERS: dict[str, str] = {
    "alice": "password1",
    "bob": "password2",
}
