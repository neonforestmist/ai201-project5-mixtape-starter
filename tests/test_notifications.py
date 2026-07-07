"""
tests/test_notifications.py — Mixtape

Tests for notification side effects.
"""

import pytest
from app import create_app, db
from models import Notification, Song, User
from services.notification_service import rate_song


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def users_and_song(app):
    with app.app_context():
        sharer = User(username="sharer", email="sharer@example.com")
        rater = User(username="rater", email="rater@example.com")
        db.session.add_all([sharer, rater])
        db.session.flush()

        song = Song(
            title="Notification Song",
            artist="Test Artist",
            genre="test",
            shared_by=sharer.id,
        )
        db.session.add(song)
        db.session.commit()

        yield {"sharer": sharer, "rater": rater, "song": song}


def test_rate_song_notifies_song_sharer(app, users_and_song):
    """Rating another user's song creates a notification for the sharer."""
    with app.app_context():
        sharer = users_and_song["sharer"]
        rater = users_and_song["rater"]
        song = users_and_song["song"]

        rating = rate_song(rater.id, song.id, 5)

        notification = db.session.query(Notification).filter_by(
            user_id=sharer.id,
            notification_type="song_rated",
        ).one()
        assert rating.score == 5
        assert "rater rated your song 'Notification Song' 5 stars." == notification.body


def test_rate_song_does_not_notify_self_rating(app, users_and_song):
    """Rating your own shared song should not notify yourself."""
    with app.app_context():
        sharer = users_and_song["sharer"]
        song = users_and_song["song"]

        rate_song(sharer.id, song.id, 4)

        notifications = db.session.query(Notification).filter_by(
            user_id=sharer.id,
            notification_type="song_rated",
        ).all()
        assert notifications == []
