from app.main import UserCreate
from app.models import User


def test_usernames_are_normalized_to_lowercase():
    payload = UserCreate(username="Alice.Example", password="valid-password-2026")
    assert payload.username == "alice.example"


def test_user_model_has_case_insensitive_unique_index():
    assert any(index.name == "uq_users_username_lower" and index.unique for index in User.__table__.indexes)
