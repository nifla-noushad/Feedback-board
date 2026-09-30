from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve


def media(request, path):
    """Serve uploaded images from disk (used when Cloudinary isn't configured)."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("feedback.urls")),
]

if not settings.CLOUDINARY_URL:
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", media)]
