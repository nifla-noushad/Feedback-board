# Feedback Board

A small feedback website built with Django. Visitors can send feedback with an optional image, while an admin can log in to review, search, edit, and delete submitted feedback.

## Features

### For Visitors

- Simple homepage and feedback form
- Name, message, and optional image
- Image upload with instant preview
- Drag and drop image upload
- Remove image before submitting
- Image validation:
  - JPG, PNG, or WEBP only
  - Maximum size of 2 MB
  - File is verified as a real image
- Inline form validation and useful error messages
- Character counter
- Loading spinner
- Network/server error messages
- My Feedback page
- Visitors can edit or delete their own feedback

### For Admins

- Admin login and logout
- Staff-only admin access
- Dashboard for viewing submitted feedback
- Image thumbnails and full-size image viewer
- Search by name or message
- Filter by status
- Filter feedback with or without images
- Sort by newest or oldest
- Pagination
- Edit feedback
- Delete feedback with confirmation
- Replace or remove feedback images
- Feedback status management
- Mark feedback as reviewed
- Mark feedback as resolved
- Reopen feedback
- CSV export of filtered feedback

### Other Features

- Responsive design for mobile and desktop
- Keyboard focus styles
- Reduced-motion support
- Honeypot field for simple spam protection
- JSON API for creating and listing feedback
- Old image files are deleted when feedback is deleted or replaced



## Tech Stack

- Python 3.12
- Django 5
- HTML
- CSS
- JavaScript
- Pillow
- SQLite

## Project Structure

```text
feedback-board/

├── config/
│   └── Django settings, root URLs, WSGI/ASGI

├── feedback/
│   ├── models.py
│   ├── forms.py
│   ├── validators.py
│   ├── views.py
│   ├── urls.py
│   ├── tests.py
│   ├── migrations/
│   └── templates/feedback/

├── static/
│   ├── css/
│   └── js/

├── media/


├── requirements.txt
├── .gitignore
├── README.md
└── manage.py