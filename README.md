# PSITE Prep — shareable resident study platform

A responsive, multi-user web application and installable Progressive Web App for desktop, iPhone, iPad, and Android.

## Included
- Individual accounts with hashed passwords and private progress
- Optional program invite code for controlled registration
- 1–100 question sessions
- Domain and subsection filtering
- Immediate grading and complete rationales
- Session history, timing, knowledge-gap analytics, bookmarks, and CSV progress export
- Spaced-repetition flashcards with domain and subsection filtering
- De-identified cohort analytics
- Mobile home-screen installation
- Docker deployment with a persistent database volume
- CSRF protection, secure-cookie option, SQLite WAL mode, health endpoint, and duplicate-answer protection

## Fastest shared deployment
1. Install Docker on a server with HTTPS in front of it.
2. Copy this project to the server.
3. Edit `docker-compose.yml` and replace `SECRET_KEY` and `INVITE_CODE`.
4. Run:

```bash
docker compose up -d --build
```

The app listens on port `8000`. Put it behind an HTTPS reverse proxy and share the resulting URL and invite code with residents.

## Local test
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
SECRET_KEY='local-development-secret' INVITE_CODE='residents2026' python app.py
```

Open `http://localhost:5000`.

## Mobile installation
- iPhone/iPad: open the deployed site in Safari → Share → Add to Home Screen.
- Android: open in Chrome → Install app.

The installed mobile app and website use the same account and synchronized server-side progress.

## Backups
Back up the persistent `psite_data` Docker volume or the file configured by `DATABASE_PATH`. The database contains accounts, progress, sessions, bookmarks, and flashcard scheduling.

## Security and content
Use HTTPS, a unique long `SECRET_KEY`, and a private invite code. The educational content should receive faculty review, and you should confirm that you have permission to distribute all source questions to other users.
