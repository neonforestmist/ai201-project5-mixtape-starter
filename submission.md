# Project 5 Submission: Mixtape Bug Hunt

## AI Usage

I used Codex during Milestone 1 to navigate the starter repo, summarize the responsibilities of the main files, trace route-to-service call chains, and compare the project brief with the local code. I verified the setup steps by running the app locally, sending a request to the Flask server, and running the baseline test suite myself instead of relying only on the AI summary.

During Milestone 2, I used Codex to help build controlled reproduction steps for the chosen bugs. I verified the behavior by running the code against the seeded database and controlled service inputs before making any application code changes.

During Milestone 3, I used Codex to help trace each reproduced symptom from route to service code, identify the exact failing condition, and run focused regression checks after each fix. I verified each proposed fix by reading the changed code and running the relevant tests.

## Milestone 1: Codebase Map

### Setup Notes

- Created a local virtual environment in `.venv`.
- Installed dependencies from `requirements.txt`.
- Seeded the database with `python seed_data.py`, which created 5 users, 13 songs, 3 playlists, and 10 tags.
- Created the required working branch: `bugfix/mixtape`.
- Started the app with `FLASK_APP=app:create_app flask run` through the virtual environment.
- Confirmed the app responds at `http://127.0.0.1:5000` by requesting `GET /songs/search?q=Anthem`.
- Ran the baseline tests with `python -m pytest tests/`. The starter currently has 3 failing tests that match the known open bug areas: playlist retrieval and Sunday streak handling.

### Main Files And Roles

- `app.py`: Defines the Flask application factory, configures SQLAlchemy, registers the route blueprints, and creates database tables inside the app context.
- `models.py`: Defines the database schema and model serialization helpers. The central models are `User`, `Song`, `ListeningEvent`, `Rating`, `Playlist`, `Notification`, and `Tag`. It also defines association tables for friendships, song tags, and ordered playlist entries.
- `seed_data.py`: Recreates and populates the SQLite database with realistic users, friendships, songs, tags, playlists, listening events, streak values, and sample notifications.
- `routes/songs.py`: Handles song search, song detail lookup, rating a song, and recording a listen. It delegates search to `search_service`, ratings to `notification_service`, and listens to `streak_service`.
- `routes/playlists.py`: Handles playlist creation, playlist detail lookup, playlist song retrieval, and adding a song to a playlist. It delegates playlist reads/creates to `playlist_service` and playlist-add side effects to `notification_service`.
- `routes/users.py`: Handles user detail, streak, notifications, and marking notifications as read. It delegates streak and notification logic to the service layer.
- `routes/feed.py`: Handles the friends listening now feed and the broader activity feed through `feed_service`.
- `services/streak_service.py`: Records listening events and updates each user's listening streak based on the date of the last listen.
- `services/feed_service.py`: Builds friend activity results, including a "listening now" view and a general activity feed.
- `services/search_service.py`: Searches songs by title or artist and serializes song results with tags.
- `services/notification_service.py`: Creates notifications, adds songs to playlists, saves ratings, retrieves notifications, and marks notifications read.
- `services/playlist_service.py`: Creates playlists and retrieves playlist metadata or ordered playlist songs.
- `tests/`: Contains targeted tests for streak logic, search behavior, and playlist retrieval. These tests document several intended behaviors and expose existing starter bugs.

### Data Model Notes

- `User` stores identity, streak state, last listen time, and relationships to shared songs, ratings, listening events, notifications, playlists, and friends.
- `Song` stores track metadata, the user who shared it, and tag relationships.
- `ListeningEvent` records that a user listened to a song at a specific time.
- `Rating` stores a user's 1-to-5 score for a song, with a uniqueness rule so one user can only have one rating per song.
- `Playlist` stores playlist metadata. Playlist membership and order live in the `playlist_entries` association table.
- `Notification` stores user-facing notification messages and read state.
- `Tag` and `song_tags` connect songs to zero or more descriptive tags.

### Example Data Flow: Rating A Song

1. A client sends `POST /songs/<song_id>/rate` with `user_id` and `score`.
2. `routes/songs.py` reads the JSON body, validates that both fields are present, converts `score` to an integer, and calls `notification_service.rate_song(user_id, song_id, score)`.
3. `rate_song` validates that the score is between 1 and 5.
4. `rate_song` loads the target `Song` and the rating `User`; if either is missing, it raises `ValueError`.
5. `rate_song` checks whether the same user has already rated the same song.
6. If a rating exists, the service updates its score. If not, it creates a new `Rating` row.
7. The service commits the database transaction and returns the `Rating`.
8. The route serializes the rating with `to_dict()` and returns JSON with status `201`.

### Example Data Flow: Viewing Playlist Songs

1. A client sends `GET /playlists/<playlist_id>/songs`.
2. `routes/playlists.py` calls `playlist_service.get_playlist_songs(playlist_id)`.
3. `get_playlist_songs` checks that the playlist exists.
4. It queries `Song` rows through `playlist_entries`, filters by the playlist id, and orders by `playlist_entries.position`.
5. The service serializes the ordered songs with `Song.to_dict()`.
6. The route returns `{"songs": songs, "count": len(songs)}` as JSON.

### Orientation Takeaways

- The routes mostly validate input and translate service results into JSON responses.
- The service layer owns the actual behavior for the five open issues, so bugs should be traced from endpoint to route to service function.
- `models.py` is important context because several features depend on association tables instead of direct model relationships.
- The seed data intentionally creates conditions that make the reported issues reproducible.
- The tests are useful as focused regression checks, but the project brief still needs to be used for full reproduction and root cause analysis wording.

## Milestone 2: Bug Reproduction Notes

I chose Issues #1, #4, and #5 for the first fix pass. I reproduced each one before changing application code.

### Issue #1: My Listening Streak Keeps Resetting

**How I reproduced it:** I isolated `update_listening_streak` with a controlled user and two consecutive UTC dates: Saturday, June 15, 2024 and Sunday, June 16, 2024. After the Saturday listen, the user's streak was `1`. After the Sunday listen, the expected streak was `2`, but the observed streak stayed at `1`.

**Inputs and condition that triggered it:** A user with no previous listening history, followed by listens on consecutive Saturday and Sunday dates.

**Observed result:** Saturday listen -> streak `1`; Sunday listen -> expected `2`, observed `1`.

### Issue #4: Rating A Shared Song Does Not Create A Notification

**How I reproduced it:** I used the seeded database users `aaliya` and `kenji`, created a controlled song shared by `aaliya`, then called `POST /songs/<song_id>/rate` as `kenji` with a score of `5`. The endpoint returned HTTP `201`, and the rating was saved.

**Inputs and condition that triggered it:** A song where `shared_by` is Aaliya's user id, rated by a different user, Kenji.

**Observed result:** Aaliya had `0` notifications before the rating and still had `0` notifications afterward. There were also `0` notifications with type `song_rated`, even though the rating row existed with score `5`.

### Issue #5: The Last Song In A Playlist Never Shows Up

**How I reproduced it:** I used the seeded `Friday Energy` playlist and compared the raw `playlist_entries` rows with the songs returned by `get_playlist_songs`.

**Inputs and condition that triggered it:** A playlist with ordered `playlist_entries`.

**Observed result:** The raw table had `7` playlist entries, but the service returned `6` songs. The raw newest song was `Harlem Renaissance`, but the returned list ended at `Crown Heights Anthem`.

**Follow-up reproduction:** I inserted one additional playlist entry to simulate a new song being added. The raw table then had `8` playlist entries, but the service returned `7` songs. The previous missing song, `Harlem Renaissance`, appeared, and the newly added last song, `Midnight Drive`, became hidden.

### Milestone 2 Checkpoint

- I can trigger all three chosen bugs deliberately.
- I know the inputs and data conditions that reproduce each chosen bug.
- I have not changed application code yet.

## Milestone 3: Root Cause Analysis Entries

### Issue #1: My Listening Streak Keeps Resetting

**How I reproduced it:** I isolated `update_listening_streak` with a controlled user and two consecutive UTC dates: Saturday, June 15, 2024 and Sunday, June 16, 2024. After the Saturday listen, the streak was `1`. After the Sunday listen, the expected streak was `2`, but the observed streak stayed at `1`.

**How I found the root cause:** I traced the report from `POST /songs/<song_id>/listen` in `routes/songs.py` to `record_listening_event` and `update_listening_streak` in `services/streak_service.py`. The key moment was comparing the documented streak rule, "If the user listened yesterday: streak increments by 1," with the actual conditional that only incremented when `days_since_last == 1 and today.weekday() != 6`.

**The root cause:** `datetime.weekday()` returns `6` on Sunday, and the streak code explicitly excluded Sundays from the consecutive-day increment branch. That meant a normal Saturday-to-Sunday listen had `days_since_last == 1`, but still fell into the reset branch and set the streak back to `1`.

**Your fix and side-effect check:** I changed the consecutive-day condition to increment whenever `days_since_last == 1`, regardless of weekday. I checked the related streak behaviors by running `python -m pytest tests/test_streaks.py`, which covers first listen, same-day repeat listens, normal consecutive days, skipped days, and the Saturday-to-Sunday boundary.

### Issue #4: Rating A Shared Song Does Not Create A Notification

**How I reproduced it:** I used the seeded database users `aaliya` and `kenji`, created a controlled song shared by `aaliya`, then called `POST /songs/<song_id>/rate` as `kenji` with a score of `5`. The endpoint returned HTTP `201`, and the rating row was saved, but Aaliya's notification count stayed at `0`.

**How I found the root cause:** I traced `POST /songs/<song_id>/rate` from `routes/songs.py` to `notification_service.rate_song`. Then I compared that function with `notification_service.add_to_playlist`, the working path mentioned in the bug report. `add_to_playlist` saves the interaction and then calls `create_notification` for the original song sharer. `rate_song` saved the `Rating` and returned immediately without any equivalent notification call.

**The root cause:** The rating flow had no notification side effect. It validated the score, loaded the song and rater, created or updated the `Rating`, committed the database transaction, and returned the rating. Because it never called `create_notification`, the song sharer never received a `song_rated` notification even though the rating itself was saved successfully.

**Your fix and side-effect check:** I added a `create_notification` call after a successful rating when the rater is not the same user who shared the song. The notification type is `song_rated`, and the body names the rater, song, and score. I added `tests/test_notifications.py` to verify that rating another user's song creates a notification and rating your own shared song does not notify yourself. I checked the change by running `python -m pytest tests/test_notifications.py`.

### Issue #5: The Last Song In A Playlist Never Shows Up

**How I reproduced it:** I used the seeded `Friday Energy` playlist and compared the raw `playlist_entries` rows with the result from `get_playlist_songs`. The raw table had `7` entries, but the service returned `6` songs. After I inserted one more playlist entry, the raw count became `8`, the service returned `7`, the previously missing song appeared, and the newly added last song became hidden.

**How I found the root cause:** I traced `GET /playlists/<playlist_id>/songs` from `routes/playlists.py` to `playlist_service.get_playlist_songs`. The SQLAlchemy query joined `Song` to `playlist_entries`, filtered by playlist id, and ordered by `playlist_entries.position`, which matched the expected data flow. The specific failure was in the final return statement, where the code serialized `songs[:-1]` instead of `songs`.

**The root cause:** In Python, `songs[:-1]` returns every item except the last one. The playlist query was retrieving the complete ordered list, but the service dropped the newest/final song while building the response. That is why adding a new song made the old missing song appear while hiding the newly added final song.

**Your fix and side-effect check:** I changed the return statement to serialize all queried songs. I checked related playlist behavior by running `python -m pytest tests/test_playlists.py`, which verifies that all songs are returned, that their order is preserved, and that an empty playlist still returns an empty list.
