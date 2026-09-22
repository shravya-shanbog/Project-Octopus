from hashlib import sha256


# --------------------------------------------------
# DEMO USER STORE
# --------------------------------------------------

USERS = {
    "admin@projectoctopus.com": {
        "password_hash": sha256(
            "Octopus@123".encode()
        ).hexdigest(),
        "name": "Octopus Administrator",
        "role": "admin"
    }
}


# --------------------------------------------------
# PASSWORD VERIFICATION
# --------------------------------------------------

def verify_password(password: str, stored_hash: str) -> bool:

    password_hash = sha256(
        password.encode()
    ).hexdigest()

    return password_hash == stored_hash


# --------------------------------------------------
# AUTHENTICATE USER
# --------------------------------------------------

def authenticate_user(email: str, password: str):

    email = email.strip().lower()

    user = USERS.get(email)

    if not user:
        return None

    if not verify_password(
        password,
        user["password_hash"]
    ):
        return None

    return {
        "email": email,
        "name": user["name"],
        "role": user["role"]
    }