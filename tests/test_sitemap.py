from datetime import date
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_sitemap", ROOT / "scripts/check_sitemap.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class SitemapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("index.html", "hero-slides.json", "sitemap.xml", "robots.txt"):
            shutil.copy(ROOT / name, self.root / name)
        for name in ("assets", "seo"):
            shutil.copytree(ROOT / name, self.root / name)
        self.today = date(2026, 10, 21)

    def check(self, base=None):
        return checker.validate(self.root, today=self.today, base=base)

    def edit(self, path, old, new):
        file = self.root / path
        file.write_text(file.read_text().replace(old, new))

    def review(self, **values):
        file = self.root / checker.REVIEW
        data = json.loads(file.read_text())
        data.update(values)
        file.write_text(json.dumps(data, ensure_ascii=False))

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True,
                                       stderr=subprocess.DEVNULL).strip()

    def baseline(self):
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-qm", "baseline")
        return self.git("rev-parse", "HEAD")

    def test_current_review_passes(self):
        self.assertEqual(self.check(), "2026-10-03")

    def test_old_sitemap_date_fails(self):
        self.edit("sitemap.xml", "2026-10-03", "2026-08-20T17:18:37+09:00")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.check()

    def test_content_changes_need_review(self):
        mutations = {
            "text": lambda: self.edit("index.html", "豆缶プロジェクト", "新しいプロジェクト"),
            "link": lambda: self.edit("index.html", "https://mamecan.jp/", "https://example.com/"),
            "json": lambda: self.edit("hero-slides.json", "{", "{ "),
            "image replacement": lambda: (self.root / "assets/decaf.jpg").write_bytes(b"new"),
            "image addition": lambda: (self.root / "assets/new.jpg").write_bytes(b"new"),
            "image deletion": lambda: (self.root / "assets/decaf.jpg").unlink(),
        }
        originals = {name: (self.root / name).read_bytes() for name in
                     ("index.html", "hero-slides.json", "assets/decaf.jpg")}
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                for path, contents in originals.items():
                    (self.root / path).write_bytes(contents)
                (self.root / "assets/new.jpg").unlink(missing_ok=True)
                self.check()
                mutate()
                with self.assertRaisesRegex(ValueError, "content changed"):
                    self.check()

    def test_development_only_changes_do_not_advance_date(self):
        (self.root / "vercel.json").write_text('{"example": true}')
        (self.root / "notes.md").write_text("Development notes")
        self.assertEqual(self.check(), "2026-10-03")

    def test_invalid_or_future_review_dates_fail(self):
        for value in ("2026-02-30", "2026-10-22", "2026-10-03T00:00:00+09:00"):
            with self.subTest(value=value):
                self.review(lastmod=value)
                with self.assertRaises(ValueError):
                    self.check()

    def test_bad_namespace_and_duplicate_url_fail(self):
        path = self.root / "sitemap.xml"
        original = path.read_text()
        path.write_text(original.replace("http://www.sitemaps.org/schemas/sitemap/0.9", "wrong"))
        with self.assertRaises(ValueError):
            self.check()
        path.write_text(original.replace("</urlset>", "<url/></urlset>"))
        with self.assertRaises(ValueError):
            self.check()

    def test_canonical_and_robots_mismatches_fail(self):
        self.edit("robots.txt", "https://7story.co.jp/", "https://www.7story.co.jp/")
        with self.assertRaisesRegex(ValueError, "robots.txt"):
            self.check()
        self.edit("robots.txt", "https://www.7story.co.jp/", "https://7story.co.jp/")
        self.edit("index.html", 'rel="canonical" href="https://7story.co.jp/"',
                  'rel="canonical" href="https://www.7story.co.jp/"')
        self.review(content_sha256=checker.content_hash(self.root))
        with self.assertRaisesRegex(ValueError, "HTML canonical"):
            self.check()

    def test_new_page_is_not_silently_omitted(self):
        (self.root / "about.html").write_text("About")
        with self.assertRaisesRegex(ValueError, "New root HTML"):
            self.check()

    def test_hash_only_refresh_without_new_reason_fails(self):
        base = self.baseline()
        self.edit("index.html", "豆缶プロジェクト", "新しいプロジェクト")
        self.review(content_sha256=checker.content_hash(self.root))
        with self.assertRaisesRegex(ValueError, "new review reason"):
            self.check(base)

    def test_cosmetic_review_can_retain_date(self):
        base = self.baseline()
        self.edit("index.html", "--bg:#ffffff", "--bg:#fff")
        self.review(content_sha256=checker.content_hash(self.root),
                    change_type="non-significant", reason="CSS色の短縮表記のみ。本文・リンクに変更なし。")
        self.assertEqual(self.check(base), "2026-10-03")
        self.review(lastmod="2026-10-04")
        self.edit("sitemap.xml", "2026-10-03", "2026-10-04")
        with self.assertRaisesRegex(ValueError, "retain lastmod"):
            self.check(base)

    def test_significant_review_advances_date(self):
        base = self.baseline()
        self.edit("index.html", "豆缶プロジェクト", "新しいプロジェクト")
        self.review(lastmod="2026-10-21", content_sha256=checker.content_hash(self.root),
                    change_type="significant", reason="Topics本文の実質的な変更。")
        self.edit("sitemap.xml", "2026-10-03", "2026-10-21")
        self.assertEqual(self.check(base), "2026-10-21")

    def test_initial_pr_without_review_file_in_base(self):
        (self.root / checker.REVIEW).unlink()
        base = self.baseline()
        shutil.copy(ROOT / checker.REVIEW, self.root / checker.REVIEW)
        self.assertEqual(self.check(base), "2026-10-03")


if __name__ == "__main__":
    unittest.main()
