"""
tests/test_feed.py — Mixtape

Tests for friends listening now behavior.
"""

import pytest
from datetime import datetime, timezone
from app import create_app, db
from models import ListeningEvent, Song, User, friendships
import services.feed_service as feed_service


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def feed_users_and_songs(app):
    with app.app_context():
        viewer = User(username="viewer", email="viewer@example.com")
        yesterday_friend = User(username="yesterday", email="yesterday@example.com")
        today_friend = User(username="today", email="today@example.com")
        db.session.add_all([viewer, yesterday_friend, today_friend])
        db.session.flush()

        db.session.execute(friendships.insert().values(user_id=viewer.id, friend_id=yesterday_friend.id))
        db.session.execute(friendships.insert().values(user_id=yesterday_friend.id, friend_id=viewer.id))
        db.session.execute(friendships.insert().values(user_id=viewer.id, friend_id=today_friend.id))
        db.session.execute(friendships.insert().values(user_id=today_friend.id, friend_id=viewer.id))

        yesterday_song = Song(
            title="Yesterday Song",
            artist="Test Artist",
            shared_by=yesterday_friend.id,
        )
        today_song = Song(
            title="Today Song",
            artist="Test Artist",
            shared_by=today_friend.id,
        )
        db.session.add_all([yesterday_song, today_song])
        db.session.commit()

        yield {
            "viewer": viewer,
            "yesterday_friend": yesterday_friend,
            "today_friend": today_friend,
            "yesterday_song": yesterday_song,
            "today_song": today_song,
        }


def test_listening_now_only_shows_friends_who_listened_today(
    app, feed_users_and_songs, monkeypatch
):
    """A listen from yesterday evening should not appear the next morning."""
    frozen_now = datetime(2024, 6, 16, 9, 0, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now if tz is not None else frozen_now.replace(tzinfo=None)

    monkeypatch.setattr(feed_service, "datetime", FrozenDateTime)

    with app.app_context():
        db.session.add_all([
            ListeningEvent(
                user_id=feed_users_and_songs["yesterday_friend"].id,
                song_id=feed_users_and_songs["yesterday_song"].id,
                listened_at=datetime(2024, 6, 15, 23, 0, 0, tzinfo=timezone.utc),
            ),
            ListeningEvent(
                user_id=feed_users_and_songs["today_friend"].id,
                song_id=feed_users_and_songs["today_song"].id,
                listened_at=datetime(2024, 6, 16, 8, 30, 0, tzinfo=timezone.utc),
            ),
        ])
        db.session.commit()

        feed = feed_service.get_friends_listening_now(feed_users_and_songs["viewer"].id)

        usernames = [item["friend"]["username"] for item in feed]
        assert usernames == ["today"]
