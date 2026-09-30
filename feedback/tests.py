import io
import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Feedback

TEST_MEDIA = tempfile.mkdtemp(prefix="feedback-test-media-")


def make_image(name="photo.png", fmt="PNG", size=(20, 20)):
    buf = io.BytesIO()
    Image.new("RGB", size, "blue").save(buf, fmt)
    content_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[fmt]
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


def make_big_image():
    """A valid PNG that is larger than 2 MB (random pixels don't compress)."""
    buf = io.BytesIO()
    Image.frombytes("RGB", (1200, 1200), os.urandom(1200 * 1200 * 3)).save(buf, "PNG")
    return SimpleUploadedFile("big.png", buf.getvalue(), content_type="image/png")


VALID = {"name": "Asha", "message": "The dashboard is easy to use, thank you!"}


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class FeedbackBoardTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("admin", password="pass12345", is_staff=True)
        self.regular = User.objects.create_user("regular", password="pass12345")

    def login_admin(self):
        self.client.login(username="admin", password="pass12345")

    # --- public --------------------------------------------------------
    def test_public_pages_load(self):
        for name in ("home", "submit", "admin_login"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_submit_without_image(self):
        res = self.client.post(reverse("submit"), VALID)
        self.assertRedirects(res, reverse("thank_you"))
        self.assertEqual(Feedback.objects.count(), 1)

    def test_submit_with_image_and_admin_sees_it(self):
        res = self.client.post(reverse("submit"), {**VALID, "image": make_image()})
        self.assertRedirects(res, reverse("thank_you"))
        fb = Feedback.objects.get()
        self.assertTrue(fb.image.name.startswith("feedback/"))
        self.assertTrue(os.path.exists(fb.image.path))

        self.client.logout()
        self.login_admin()
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, "Asha")
        self.assertContains(page, fb.image.url)  # image shown on the admin page
        self.assertEqual(self.client.get(fb.image.url).status_code, 200)

    def test_ajax_submit_returns_json(self):
        res = self.client.post(reverse("submit"), VALID, headers={"x-requested-with": "XMLHttpRequest"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

    def test_validation_errors(self):
        res = self.client.post(
            reverse("submit"), {"name": "", "message": ""}, headers={"x-requested-with": "XMLHttpRequest"}
        )
        self.assertEqual(res.status_code, 400)
        errors = res.json()["errors"]
        self.assertIn("name", errors)
        self.assertIn("message", errors)
        self.assertEqual(Feedback.objects.count(), 0)

    def test_rejects_name_with_numbers_or_symbols(self):
        for invalid_name in ("Asha123", "User@Board", "Alex!"):
            res = self.client.post(reverse("submit"), {**VALID, "name": invalid_name})
            self.assertEqual(Feedback.objects.count(), 0)
            self.assertContains(res, "no numbers or symbols")

    def test_rejects_non_image_disguised_as_png(self):
        fake = SimpleUploadedFile("evil.png", b"not really an image", content_type="image/png")
        res = self.client.post(reverse("submit"), {**VALID, "image": fake})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertContains(res, "valid image")

    def test_rejects_wrong_image_type(self):
        gif = io.BytesIO()
        Image.new("RGB", (10, 10)).save(gif, "GIF")
        upload = SimpleUploadedFile("a.gif", gif.getvalue(), content_type="image/gif")
        res = self.client.post(reverse("submit"), {**VALID, "image": upload})
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertContains(res, "Use a JPG, PNG or WEBP image.")

    def test_rejects_oversized_image(self):
        res = self.client.post(reverse("submit"), {**VALID, "image": make_big_image()})
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertContains(res, "too large")

    def test_honeypot_blocks_bots(self):
        self.client.post(reverse("submit"), {**VALID, "website": "http://spam.example"})
        self.assertEqual(Feedback.objects.count(), 0)

    # --- admin access --------------------------------------------------
    def test_dashboard_requires_login(self):
        res = self.client.get(reverse("dashboard"))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("admin_login"), res["Location"])

    def test_regular_user_can_login_with_username_and_password(self):
        res = self.client.post(reverse("admin_login"), {"username": "regular", "password": "pass12345"})
        self.assertRedirects(res, reverse("dashboard"))

    def test_admin_login_and_logout(self):
        res = self.client.post(reverse("admin_login"), {"username": "admin", "password": "pass12345"})
        self.assertRedirects(res, reverse("dashboard"))
        res = self.client.post(reverse("admin_logout"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_wrong_password_shows_error(self):
        res = self.client.post(reverse("admin_login"), {"username": "admin", "password": "nope"})
        self.assertContains(res, "Please enter a correct username and password")

    # --- search / filter -----------------------------------------------
    def test_search_and_filter(self):
        Feedback.objects.create(name="Ravi", message="Love the new design of the site")
        Feedback.objects.create(name="Meera", message="Login page is slow on mobile", status="resolved")
        self.login_admin()
        url = reverse("dashboard")

        res = self.client.get(url, {"q": "login"})
        self.assertContains(res, "Meera")
        self.assertNotContains(res, "Ravi")

        res = self.client.get(url, {"q": "ravi"})  # matches name, case-insensitive
        self.assertContains(res, "Ravi")

        res = self.client.get(url, {"status": "resolved"})
        self.assertContains(res, "Meera")
        self.assertNotContains(res, "Ravi")

        res = self.client.get(url, {"q": "zzzz"})
        self.assertContains(res, "No feedback matches your filters")

    def test_has_image_filter(self):
        self.client.post(reverse("submit"), {**VALID, "image": make_image()})
        Feedback.objects.create(name="NoPic", message="This one has no picture attached")
        self.client.logout()
        self.login_admin()
        res = self.client.get(reverse("dashboard"), {"image": "1"})
        self.assertContains(res, "Asha")
        self.assertNotContains(res, "NoPic")

    # --- admin edit / delete -------------------------------------------
    def test_admin_edit_changes_text_and_status(self):
        fb = Feedback.objects.create(name="Old", message="Old message goes here ok")
        self.login_admin()
        res = self.client.post(
            reverse("edit", args=[fb.pk]),
            {"name": "New name", "message": "Updated message text here", "status": "reviewed"},
        )
        self.assertRedirects(res, reverse("dashboard"))
        fb.refresh_from_db()
        self.assertEqual((fb.name, fb.status), ("New name", "reviewed"))

    def test_admin_edit_replaces_and_removes_image(self):
        self.client.post(reverse("submit"), {**VALID, "image": make_image()})
        fb = Feedback.objects.get()
        old_path = fb.image.path
        self.client.logout()
        self.login_admin()

        data = {"name": "Asha", "message": VALID["message"], "status": "new", "image": make_image("new.png")}
        self.client.post(reverse("edit", args=[fb.pk]), data)
        fb.refresh_from_db()
        self.assertNotEqual(fb.image.path, old_path)
        self.assertFalse(os.path.exists(old_path))  # old file cleaned up

        new_path = fb.image.path
        self.client.post(
            reverse("edit", args=[fb.pk]),
            {"name": "Asha", "message": VALID["message"], "status": "new", "image-clear": "on"},
        )
        fb.refresh_from_db()
        self.assertFalse(fb.image)
        self.assertFalse(os.path.exists(new_path))

    def test_admin_edit_validation_error(self):
        fb = Feedback.objects.create(name="Old", message="Old message goes here ok")
        self.login_admin()
        res = self.client.post(reverse("edit", args=[fb.pk]), {"name": "", "message": "msg", "status": "new"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Enter your name.")

    def test_admin_delete_removes_record_and_file(self):
        self.client.post(reverse("submit"), {**VALID, "image": make_image()})
        fb = Feedback.objects.get()
        path = fb.image.path
        self.client.logout()
        self.login_admin()

        self.assertEqual(self.client.get(reverse("delete", args=[fb.pk])).status_code, 405)  # no delete on GET
        self.assertEqual(Feedback.objects.count(), 1)

        self.client.post(reverse("delete", args=[fb.pk]))
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertFalse(os.path.exists(path))

    def test_anonymous_cannot_edit_or_delete_via_admin_urls(self):
        fb = Feedback.objects.create(name="Keep", message="Do not remove this feedback")
        self.client.post(reverse("delete", args=[fb.pk]))
        self.client.post(reverse("edit", args=[fb.pk]), {"name": "Hack", "message": "Hacked message text"})
        fb.refresh_from_db()
        self.assertEqual(fb.name, "Keep")

    # --- user edit / delete of their own feedback ----------------------
    def test_user_can_edit_and_delete_own_feedback(self):
        self.client.post(reverse("submit"), VALID)
        fb = Feedback.objects.get()

        self.assertContains(self.client.get(reverse("thank_you")), reverse("my_edit", args=[fb.pk]))
        self.assertContains(self.client.get(reverse("my_feedback")), "Asha")

        res = self.client.post(
            reverse("my_edit", args=[fb.pk]), {"name": "Asha K", "message": "Edited by the author of this"}
        )
        self.assertRedirects(res, reverse("my_feedback"))
        fb.refresh_from_db()
        self.assertEqual(fb.name, "Asha K")

        self.client.post(reverse("my_delete", args=[fb.pk]))
        self.assertEqual(Feedback.objects.count(), 0)

    def test_user_cannot_touch_someone_elses_feedback(self):
        other = Feedback.objects.create(name="Other", message="Somebody else wrote this one")
        self.assertEqual(self.client.get(reverse("my_edit", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("my_delete", args=[other.pk])).status_code, 404)
        self.assertEqual(Feedback.objects.count(), 1)

    # --- export and API ------------------------------------------------
    def test_csv_export_is_admin_only_and_safe(self):
        Feedback.objects.create(name="=cmd()", message="A message that is long enough")
        self.assertEqual(self.client.get(reverse("export_csv")).status_code, 302)
        self.login_admin()
        res = self.client.get(reverse("export_csv"))
        self.assertEqual(res["Content-Type"], "text/csv")
        body = res.content.decode()
        self.assertIn("'=cmd()", body)

    def test_api_create_and_list(self):
        res = self.client.post(reverse("api_feedback"), VALID)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.client.get(reverse("api_feedback")).status_code, 403)
        self.login_admin()
        data = self.client.get(reverse("api_feedback"), {"q": "dashboard"}).json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(self.client.post(reverse("api_feedback"), {"name": "A"}).status_code, 400)

    def test_pagination(self):
        for i in range(12):
            Feedback.objects.create(name=f"User{i}", message="A perfectly fine message here")
        self.login_admin()
        page2 = self.client.get(reverse("dashboard"), {"page": 2})
        self.assertContains(page2, "Page 2 of 2")


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class SyncAndStatusTests(TestCase):
    """A visitor and an admin work on the same feedback, so every change must show up for both."""

    def setUp(self):
        User = get_user_model()
        User.objects.create_user("admin", password="pass12345", is_staff=True)
        self.visitor = Client()
        self.admin = Client()
        self.admin.login(username="admin", password="pass12345")

    def submit_as_visitor(self, name="Asha", message="Great app, easy to use", image=True):
        data = {"name": name, "message": message}
        if image:
            data["image"] = make_image()
        self.visitor.post(reverse("submit"), data)
        return Feedback.objects.latest("pk")

    # --- navbar --------------------------------------------------------
    def test_admin_navbar_has_no_visitor_links(self):
        page = self.admin.get(reverse("dashboard"))
        self.assertNotContains(page, 'href="/submit/"')
        self.assertNotContains(page, 'href="/my-feedback/"')
        self.assertContains(page, "Log out")

    def test_visitor_navbar_has_visitor_links(self):
        page = self.visitor.get(reverse("home"))
        self.assertContains(page, 'href="/submit/"')
        self.assertContains(page, 'href="/my-feedback/"')

    # --- visitor changes show up for the admin -------------------------
    def test_visitor_edit_shows_on_admin_dashboard(self):
        fb = self.submit_as_visitor()
        self.visitor.post(reverse("my_edit", args=[fb.pk]), {"name": "Meera Nair", "message": "Edited by the visitor"})
        page = self.admin.get(reverse("dashboard"))
        self.assertContains(page, "Meera Nair")
        self.assertContains(page, "Edited by the visitor")
        self.assertNotContains(page, "Great app, easy to use")

    def test_visitor_delete_removes_it_from_admin_dashboard(self):
        fb = self.submit_as_visitor()
        path = fb.image.path
        self.assertContains(self.admin.get(reverse("dashboard")), "Asha")
        self.visitor.post(reverse("my_delete", args=[fb.pk]))
        self.assertNotContains(self.admin.get(reverse("dashboard")), "Great app, easy to use")
        self.assertFalse(Feedback.objects.exists())
        self.assertFalse(os.path.exists(path))

    # --- admin changes show up for the visitor -------------------------
    def test_admin_edit_shows_on_visitor_page(self):
        fb = self.submit_as_visitor()
        self.admin.post(
            reverse("edit", args=[fb.pk]),
            {"name": "Asha", "message": "Rewritten by the admin", "status": "reviewed"},
        )
        page = self.visitor.get(reverse("my_feedback"))
        self.assertContains(page, "Rewritten by the admin")
        self.assertContains(page, "badge-reviewed")

    def test_admin_delete_removes_it_for_the_visitor(self):
        fb = self.submit_as_visitor()
        self.admin.post(reverse("delete", args=[fb.pk]))
        self.assertFalse(Feedback.objects.exists())

        page = self.visitor.get(reverse("my_feedback"))
        self.assertNotContains(page, "Great app, easy to use")
        self.assertContains(page, "Nothing here yet")
        self.assertEqual(self.visitor.get(reverse("my_edit", args=[fb.pk])).status_code, 404)
        self.assertEqual(self.visitor.get(reverse("thank_you")).status_code, 200)

    def test_visitor_deleting_something_already_removed_is_handled(self):
        fb = self.submit_as_visitor()
        self.admin.post(reverse("delete", args=[fb.pk]))
        res = self.visitor.post(reverse("my_delete", args=[fb.pk]), follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "already removed")

    def test_admin_deleting_something_already_removed_is_handled(self):
        fb = self.submit_as_visitor()
        self.visitor.post(reverse("my_delete", args=[fb.pk]))
        res = self.admin.post(reverse("delete", args=[fb.pk]), follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "already removed")

    # --- Reviewed / Resolved -------------------------------------------
    def test_admin_can_mark_reviewed_then_resolved_then_reopen(self):
        fb = self.submit_as_visitor()
        url = reverse("set_status", args=[fb.pk])

        page = self.admin.get(reverse("dashboard"))
        self.assertContains(page, "Mark reviewed")
        self.assertContains(page, "Mark resolved")

        self.admin.post(url, {"status": "reviewed"})
        fb.refresh_from_db()
        self.assertEqual(fb.status, "reviewed")
        self.assertContains(self.admin.get(reverse("dashboard")), "badge-reviewed")
        self.assertContains(self.visitor.get(reverse("my_feedback")), "badge-reviewed")

        self.admin.post(url, {"status": "resolved"})
        fb.refresh_from_db()
        self.assertEqual(fb.status, "resolved")
        page = self.admin.get(reverse("dashboard"))
        self.assertContains(page, "badge-resolved")
        self.assertContains(page, "Reopen")
        self.assertNotContains(page, "Mark resolved")

        self.admin.post(url, {"status": "new"})
        fb.refresh_from_db()
        self.assertEqual(fb.status, "new")

    def test_status_counts_and_filter(self):
        a = self.submit_as_visitor(name="Ravi", message="First one", image=False)
        b = self.submit_as_visitor(name="Meera", message="Second one", image=False)
        self.admin.post(reverse("set_status", args=[a.pk]), {"status": "resolved"})
        self.admin.post(reverse("set_status", args=[b.pk]), {"status": "reviewed"})

        page = self.admin.get(reverse("dashboard"))
        stats = page.context["stats"]
        self.assertEqual((stats["total"], stats["new"], stats["reviewed"], stats["resolved"]), (2, 0, 1, 1))

        resolved_only = self.admin.get(reverse("dashboard"), {"status": "resolved"})
        self.assertContains(resolved_only, "Ravi")
        self.assertNotContains(resolved_only, "Meera")

    def test_set_status_rules(self):
        fb = self.submit_as_visitor()
        url = reverse("set_status", args=[fb.pk])
        self.assertEqual(self.admin.get(url).status_code, 405)  # POST only
        self.admin.post(url, {"status": "banana"})  # invalid value is ignored
        fb.refresh_from_db()
        self.assertEqual(fb.status, "new")
        self.assertEqual(self.visitor.post(url, {"status": "resolved"}).status_code, 302)  # not logged in
        fb.refresh_from_db()
        self.assertEqual(fb.status, "new")

    def test_set_status_returns_to_the_same_filtered_page_but_not_other_sites(self):
        fb = self.submit_as_visitor()
        url = reverse("set_status", args=[fb.pk])
        res = self.admin.post(url, {"status": "reviewed", "next": "/dashboard/?status=new"})
        self.assertEqual(res["Location"], "/dashboard/?status=new")
        res = self.admin.post(url, {"status": "resolved", "next": "https://evil.example.com/"})
        self.assertEqual(res["Location"], reverse("dashboard"))

    # --- delete is robust ----------------------------------------------
    def test_delete_still_works_if_the_image_file_cannot_be_removed(self):
        fb = self.submit_as_visitor()
        with mock.patch.object(FileSystemStorage, "delete", side_effect=PermissionError("locked")):
            res = self.admin.post(reverse("delete", args=[fb.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Feedback.objects.exists())

    def test_delete_failure_shows_a_message_instead_of_crashing(self):
        fb = self.submit_as_visitor()
        with mock.patch("feedback.views._delete_feedback", side_effect=RuntimeError("db down")):
            res = self.admin.post(reverse("delete", args=[fb.pk]), follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Please try again")
        self.assertTrue(Feedback.objects.filter(pk=fb.pk).exists())

    def test_delete_returns_to_the_filtered_dashboard(self):
        fb = self.submit_as_visitor()
        res = self.admin.post(reverse("delete", args=[fb.pk]), {"next": "/dashboard/?q=asha&sort=old"})
        self.assertEqual(res["Location"], "/dashboard/?q=asha&sort=old")

    # --- sessions and old data -----------------------------------------
    def test_admin_login_ends_when_browser_closes_but_visitor_session_stays(self):
        admin_browser = Client()
        admin_browser.post(reverse("admin_login"), {"username": "admin", "password": "pass12345"})
        self.assertTrue(admin_browser.session.get_expire_at_browser_close())

        self.submit_as_visitor()
        self.assertFalse(self.visitor.session.get_expire_at_browser_close())

    def test_database_constraint_error_explains_how_to_fix_it(self):
        fb = self.submit_as_visitor()
        with mock.patch("feedback.views._delete_feedback", side_effect=IntegrityError("FOREIGN KEY constraint failed")):
            res = self.admin.post(reverse("delete", args=[fb.pk]), follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "python manage.py migrate")
        self.assertTrue(Feedback.objects.filter(pk=fb.pk).exists())
