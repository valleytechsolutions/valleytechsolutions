import datetime as dt
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import json
import urllib.error

spec = importlib.util.spec_from_file_location("updater", Path(__file__).parents[1] / "scripts/update_youtube.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)
FEED = f'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"><yt:channelId>{updater.CHANNEL}</yt:channelId><entry><yt:videoId>abcdefghijk</yt:videoId><title>GPIO &amp; &lt;script&gt; [test]</title><published>2026-10-15T12:30:00Z</published></entry></feed>'''.encode()


class FeedTests(unittest.TestCase):
    def test_scoped_replacement_and_escaping(self):
        old = "KEEP\n" + updater.START + "old" + updater.END + "\nALSO KEEP"
        result = updater.replace_block(old, updater.parse_feed(FEED))
        self.assertTrue(result.startswith("KEEP\n" + updater.START))
        self.assertTrue(result.endswith(updater.END + "\nALSO KEEP"))
        self.assertIn("&amp; &lt;script&gt;", result)
        self.assertNotIn("<script>", result)
        self.assertIn("2026-10-15", result)

    def test_transient_404_retries(self):
        calls, waits = [], []
        def opener(*args, **kwargs):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError(updater.FEED, 404, "temporary", {}, None)
            return io.BytesIO(FEED)
        self.assertEqual(len(updater.fetch_feed(opener, waits.append)), 1)
        self.assertEqual(waits, [5, 15])

    def test_retries_are_bounded(self):
        calls = []
        def opener(*args, **kwargs):
            calls.append(1)
            raise TimeoutError()
        with self.assertRaises(RuntimeError):
            updater.fetch_feed(opener, lambda _: None)
        self.assertEqual(len(calls), 4)

    def test_wrong_channel_and_empty_feed_rejected(self):
        with self.assertRaises(ValueError):
            updater.parse_feed(FEED.replace(updater.CHANNEL.encode(), b"other"))
        with self.assertRaises(ValueError):
            updater.parse_feed(FEED[:FEED.index(b"<entry>")] + b"</feed>")

    def test_invalid_markers_fail(self):
        for text in ["missing", updater.START * 2 + updater.END, updater.END + updater.START]:
            with self.assertRaises(ValueError):
                updater.replace_block(text, [])

    def test_stale_cache_fails_after_72_hours(self):
        now = dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc)
        cache = {"checked": (now - dt.timedelta(hours=71)).isoformat(), "entries": [1]}
        self.assertTrue(updater.cache_fresh(cache, now))
        cache["checked"] = (now - dt.timedelta(hours=73)).isoformat()
        self.assertFalse(updater.cache_fresh(cache, now))
        self.assertFalse(updater.cache_fresh({}, now))

    def test_outage_preserves_readme_and_cache_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            original = "Before\n" + updater.START + "\nExisting video\n" + updater.END + "\nAfter"
            cache = json.dumps({"checked": dt.datetime.now(dt.timezone.utc).isoformat(), "entries": [1]})
            (root / "README.md").write_text(original, encoding="utf-8")
            (root / "assets/youtube.json").write_text(cache, encoding="utf-8")
            with patch.object(updater, "ROOT", root), patch.object(updater, "fetch_feed", side_effect=RuntimeError()), patch.object(updater, "summary"):
                updater.main()
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), original)
            self.assertEqual((root / "assets/youtube.json").read_text(encoding="utf-8"), cache)


if __name__ == "__main__":
    unittest.main()
