# Feedback Board

A small feedback website built with Django. Visitors send feedback with an optional image; an admin logs in to review, search, edit and delete it.

## Features

**For visitors**
- Simple homepage and a feedback form (name, message, optional image)
- Image upload with instant preview, drag and drop, and a remove button
- Image validation in the browser and on the server: JPG, PNG or WEBP only, 2 MB maximum, and the file must be a real image (a renamed `.exe` is rejected)
- Inline validation with specific error messages, a character counter, a loading spinner and network/server error banners
- After submitting, visitors can edit or delete their own feedback from the "My feedback" page (tied to their browser session)

**For admins**
- Admin login page (staff accounts only) and logout
- Dashboard listing all feedback with image thumbnails and a full-size image viewer
- Search by name or message, filter by status and "has image", sort by newest or oldest, pagination
- Edit any entry (text, status, replace or remove the image) and delete with a confirmation dialog
- Status workflow: one-click "Mark reviewed", "Mark resolved" and "Reopen" buttons, clickable status counts that filter the list, and the status badge is visible to the visitor on "My feedback"
- Export the current filtered list to CSV

**Other**
- Responsive layout for mobile and desktop, keyboard focus styles, reduced-motion support
- JSON API: `POST /api/feedback/` (create) and `GET /api/feedback/` (list, admin session required)
- Old image files are deleted when feedback is deleted or its image is replaced


## How it works

- **Visitors don't need an account.** When you submit feedback, its ID is
  saved into your browser's session (a cookie), which is how "My feedback"
  knows what's yours without any login. Clearing cookies or switching
  browsers loses access to that list — the feedback itself is never
  deleted, just no longer linked to your session.
- **Images are stored on disk, not in the database.** The database only
  keeps a file path string; the actual image bytes live under `media/`,
  organised by upload date.
- **Search, filters, CSV export and the API share one filtering function.**
  So a status or search filter behaves identically everywhere, from one
  place in the code.

## Tech stack

Python 3.12, Django 5, HTML, CSS, vanilla JavaScript, Pillow, SQLite.

## Project structure

```
feedback-board/
├── config/                  Django settings, root URLs, WSGI/ASGI
├── feedback/                The app
│   ├── models.py            Feedback model
│   ├── forms.py             Form validation and admin login form
│   ├── validators.py        Image type and size checks
│   ├── views.py             Pages, admin dashboard, CSV export, JSON API
│   ├── urls.py
│   ├── tests.py
│   ├── migrations/
│   └── templates/feedback/  HTML templates
├── static/css, static/js    Styles and scripts
├── requirements.txt  .env.example  .gitignore

```

## Run locally

```bash
git clone <your-repo-url> feedback-board
cd feedback-board

python -m venv venv
source venv/bin/activate #linux       # Windows: venv\Scripts\activate
pip install -r requirements.txt

            

python manage.py migrate
python manage.py createsuperuser  # this is your admin login
python manage.py runserver
```

Open http://127.0.0.1:8000/

| Page | URL |
|---|---|
| Home | `/` |
| Give feedback | `/submit/` |
| My feedback (visitor) | `/my-feedback/` |
| Admin login | `/admin-login/` |
| Admin dashboard | `/dashboard/` |
| Django's built-in admin | `/django-admin/` |

Try it: submit feedback with an image, log in at `/admin-login/`, and open the dashboard. The entry and its thumbnail appear there, and you can search, filter, edit and delete it.


## Ideas for later

Email notification to admins, star ratings or categories, a dark mode toggle, rate limiting with `django-ratelimit`, and an image lightbox with keyboard navigation.