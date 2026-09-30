import csv
import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import AdminFeedbackForm, FeedbackForm
from .models import Feedback

logger = logging.getLogger(__name__)

SESSION_KEY = "my_feedback"  # ids of feedback submitted from this browser session
PAGE_SIZE = 10

staff_required = login_required(login_url="admin_login")


# --- helpers ----------------------------------------------------------------
def _is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _remember(request, obj):
    ids = request.session.get(SESSION_KEY, [])
    ids.append(obj.pk)
    request.session[SESSION_KEY] = ids[-50:]


def _owned_ids(request):
    return request.session.get(SESSION_KEY, [])


def _get_owned_or_404(request, pk):
    if pk not in _owned_ids(request):
        raise Http404("Feedback not found.")
    return get_object_or_404(Feedback, pk=pk)


def _forget(request, pk):
    request.session[SESSION_KEY] = [i for i in _owned_ids(request) if i != pk]


def _safe_next(request, default):
    """Return to the page the person came from (keeps filters), never to another site."""
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return reverse(default)


def _delete_feedback(obj):
    """Delete the record first, then its image file, so a file problem can never block the delete."""
    image_name = obj.image.name if obj.image else ""
    storage = obj.image.storage
    obj.delete()
    if image_name:
        try:
            storage.delete(image_name)
        except Exception:  # the record is already gone; a leftover file is harmless
            logger.warning("Could not remove image file %s", image_name, exc_info=True)


def _delete_and_report(request, obj, success_message):
    """Delete and show a message. Returns True if the feedback is gone."""
    try:
        _delete_feedback(obj)
    except IntegrityError:
        # Usually a leftover table from an old migration still points at this row.
        logger.exception("Could not delete feedback %s (database constraint)", obj.pk)
        messages.error(
            request,
            "Couldn't delete that feedback because of old database data. "
            "Stop the server, run: python manage.py migrate, then try again.",
        )
        return False
    except Exception:
        logger.exception("Could not delete feedback %s", obj.pk)
        messages.error(request, "Couldn't delete that feedback. Please try again.")
        return False
    messages.success(request, success_message)
    return True


def _filtered_queryset(request):
    """Apply the search / filter / sort query parameters."""
    qs = Feedback.objects.all()
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(message__icontains=q))
    if status in Feedback.Status.values:
        qs = qs.filter(status=status)
    if request.GET.get("image") == "1":
        qs = qs.exclude(image="")
    return qs.order_by("created_at" if request.GET.get("sort") == "old" else "-created_at")


def _edit_feedback(request, obj, form_class, success_url, back_url, is_admin):
    current_image_url = obj.image.url if obj.image else ""
    old_name = obj.image.name if obj.image else ""
    storage = obj.image.storage

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            saved = form.save()
            new_name = saved.image.name if saved.image else ""
            if old_name and old_name != new_name:
                storage.delete(old_name)  # image was replaced or removed
            messages.success(request, "Changes saved.")
            return redirect(success_url)
    else:
        form = form_class(instance=obj)

    return render(
        request,
        "feedback/edit.html",
        {
            "form": form,
            "obj": obj,
            "current_image_url": current_image_url,
            "back_url": back_url,
            "is_admin": is_admin,
        },
    )


def _serialize(f, request):
    url = f.image.url if f.image else None
    if url and url.startswith("/"):
        url = request.build_absolute_uri(url)
    return {
        "id": f.pk,
        "name": f.name,
        "message": f.message,
        "status": f.status,
        "image_url": url,
        "created_at": f.created_at.isoformat(),
    }


def _csv_safe(value):
    """Stop spreadsheet apps from running cell contents as formulas."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


class AdminLoginView(LoginView):
    """Admin login. The admin is logged out when the browser closes; visitors keep their session."""

    template_name = "feedback/admin_login.html"
    authentication_form = AuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(0)  # cookie lasts only until the browser is closed
        return response


@require_POST
def admin_logout(request):
    """Log the admin out without wiping the visitor's own "my feedback" history.

    Django's default logout() flushes the whole session. On a browser where
    someone submitted feedback and then logged in as admin, that flush was
    silently erasing the session key we use to remember their own
    submissions (the feedback itself was never deleted, it just became
    unreachable from "My feedback"). We keep that one key and restore it
    after logging out.
    """
    owned = request.session.get(SESSION_KEY)
    auth_logout(request)
    if owned:
        request.session[SESSION_KEY] = owned
    return redirect("home")


# --- public pages -----------------------------------------------------------
def home(request):
    return render(request, "feedback/home.html")


def submit(request):
    if request.method == "POST":
        # Honeypot: real people never fill this hidden field. Pretend success for bots.
        if request.POST.get("website"):
            if _is_ajax(request):
                return JsonResponse({"ok": True, "redirect": reverse("thank_you")})
            return redirect("thank_you")

        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            _remember(request, obj)
            if _is_ajax(request):
                return JsonResponse({"ok": True, "redirect": reverse("thank_you")})
            return redirect("thank_you")
        if _is_ajax(request):
            return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    else:
        form = FeedbackForm()
    return render(request, "feedback/submit.html", {"form": form})


def thank_you(request):
    ids = _owned_ids(request)
    last = Feedback.objects.filter(pk=ids[-1]).first() if ids else None
    return render(request, "feedback/thank_you.html", {"last": last})


def my_feedback(request):
    owned = _owned_ids(request)
    existing = set(Feedback.objects.filter(pk__in=owned).values_list("pk", flat=True))
    if len(existing) != len(set(owned)):  # the admin deleted some of them
        request.session[SESSION_KEY] = [i for i in owned if i in existing]

    qs = Feedback.objects.filter(pk__in=existing)
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(message__icontains=q))
    if status in Feedback.Status.values:
        qs = qs.filter(status=status)
    if request.GET.get("image") == "1":
        qs = qs.exclude(image="")
    qs = qs.order_by("created_at" if request.GET.get("sort") == "old" else "-created_at")

    has_image = request.GET.get("image") == "1"
    sort = request.GET.get("sort", "new")
    filtered = bool(q or status or has_image)

    context = {
        "items": qs,
        "q": q,
        "status": status,
        "sort": sort,
        "has_image": has_image,
        "statuses": Feedback.Status.choices,
        "filtered": filtered,
    }
    return render(request, "feedback/my_feedback.html", context)


def my_edit(request, pk):
    obj = _get_owned_or_404(request, pk)
    return _edit_feedback(request, obj, FeedbackForm, "my_feedback", reverse("my_feedback"), False)


@require_POST
def my_delete(request, pk):
    if pk not in _owned_ids(request):
        raise Http404("Feedback not found.")
    obj = Feedback.objects.filter(pk=pk).first()
    if obj is None:  # the admin already removed it
        _forget(request, pk)
        messages.info(request, "That feedback was already removed.")
    elif _delete_and_report(request, obj, "Your feedback was deleted."):
        _forget(request, pk)
    return redirect("my_feedback")


# --- admin pages ------------------------------------------------------------
@staff_required
def dashboard(request):
    qs = _filtered_queryset(request)
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    stats = Feedback.objects.aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(status="new")),
        reviewed=Count("id", filter=Q(status="reviewed")),
        resolved=Count("id", filter=Q(status="resolved")),
    )
    context = {
        "page": page,
        "q": request.GET.get("q", "").strip(),
        "status": request.GET.get("status", ""),
        "sort": request.GET.get("sort", "new"),
        "has_image": request.GET.get("image") == "1",
        "statuses": Feedback.Status.choices,
        "querystring": params.urlencode(),
        "stats": stats,
    }
    context["filtered"] = bool(context["q"] or context["status"] or context["has_image"])
    return render(request, "feedback/admin_list.html", context)


@staff_required
def edit(request, pk):
    obj = get_object_or_404(Feedback, pk=pk)
    return _edit_feedback(request, obj, AdminFeedbackForm, "dashboard", reverse("dashboard"), True)


@staff_required
@require_POST
def delete(request, pk):
    obj = Feedback.objects.filter(pk=pk).first()
    if obj is None:  # already removed (for example by the person who sent it)
        messages.info(request, "That feedback was already removed.")
    else:
        _delete_and_report(request, obj, "Feedback deleted.")
    return redirect(_safe_next(request, "dashboard"))


@staff_required
@require_POST
def set_status(request, pk):
    """Mark feedback as New, Reviewed or Resolved."""
    obj = Feedback.objects.filter(pk=pk).first()
    new_status = request.POST.get("status", "")
    if obj is None:
        messages.info(request, "That feedback was already removed.")
    elif new_status not in Feedback.Status.values:
        messages.error(request, "Choose a valid status.")
    else:
        obj.status = new_status
        obj.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Marked as {obj.get_status_display().lower()}.")
    return redirect(_safe_next(request, "dashboard"))


@staff_required
def export_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="feedback-{date.today():%Y-%m-%d}.csv"'
    writer = csv.writer(response)
    writer.writerow(["ID", "Name", "Message", "Status", "Image URL", "Created"])
    for f in _filtered_queryset(request):
        item = _serialize(f, request)
        writer.writerow(
            [
                f.pk,
                _csv_safe(f.name),
                _csv_safe(f.message),
                f.status,
                item["image_url"] or "",
                f.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    return response


# --- JSON API ---------------------------------------------------------------
@csrf_exempt
def api_feedback(request):
    """GET: list feedback (admin session required). POST: create feedback (public)."""
    if request.method == "GET":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Admin login required."}, status=403)
        qs = _filtered_queryset(request)
        return JsonResponse({"count": qs.count(), "results": [_serialize(f, request) for f in qs[:100]]})

    if request.method == "POST":
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            return JsonResponse(_serialize(obj, request), status=201)
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    return JsonResponse({"error": "Method not allowed."}, status=405)
