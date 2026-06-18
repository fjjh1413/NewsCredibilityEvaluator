import unittest
from unittest.mock import patch

from app.services.web.web_content_fetcher import (
    SSRFBlockedError,
    WebContentFetchError,
    WebContentFetcher,
)


SAMPLE_HTML = """
<!DOCTYPE html>
<html><head>
<meta property="og:title" content="Sample News Title">
<meta property="article:published_time" content="2026-06-18T09:30:00+08:00">
<title>Fallback Title</title>
</head><body>
<nav>navigation menu to strip</nav>
<aside>sidebar noise</aside>
<article>
<p>This is the first paragraph with enough length to be retained by the extractor.</p>
<p>Second paragraph here also long enough for the extractor to keep it.</p>
</article>
</body></html>
"""


class _FakeResponse:
    def __init__(self, body, content_type="text/html; charset=utf-8"):
        self._body = body.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def read(self, _n=-1):
        data = self._body
        self._body = b""
        return data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FetchArticleTestCase(unittest.TestCase):
    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher.urllib.request.urlopen")
    def test_fetch_article_returns_structured_fields(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(SAMPLE_HTML)

        article = WebContentFetcher().fetch_article("https://example.com/news/1")

        self.assertEqual(article["title"], "Sample News Title")
        self.assertIn("first paragraph", article["content"])
        self.assertIn("Second paragraph", article["content"])
        self.assertNotIn("navigation menu", article["content"])
        self.assertEqual(article["source_name"], "example.com")
        self.assertEqual(article["source_url"], "https://example.com/news/1")
        self.assertEqual(article["publish_time"], "2026-06-18T09:30:00+08:00")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher.urllib.request.urlopen")
    def test_fetch_article_reads_json_ld_publish_time(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head>
            <title>JSON-LD News</title>
            <script type="application/ld+json">
              {"@type":"NewsArticle","datePublished":"2026-06-17T18:20:00+08:00"}
            </script>
            </head><body><article>
            <p>This paragraph is long enough to be retained as article content.</p>
            </article></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/2")

        self.assertEqual(article["publish_time"], "2026-06-17T18:20:00+08:00")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher.urllib.request.urlopen")
    def test_fetch_article_ignores_pathologically_nested_json_ld(
        self, mock_urlopen, _mock_private
    ):
        nested_json = "[" * 1100 + "{}" + "]" * 1100
        mock_urlopen.return_value = _FakeResponse(
            "<html><head><title>Deep JSON-LD</title>"
            f'<script type="application/ld+json">{nested_json}</script>'
            "</head><body><article>"
            "<p>This paragraph is long enough to be retained as article content.</p>"
            "</article></body></html>"
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/deep")

        self.assertIsNone(article["publish_time"])

    def test_fetch_article_blocks_private_ip(self):
        with self.assertRaises(SSRFBlockedError):
            WebContentFetcher().fetch_article("http://127.0.0.1/admin")

    def test_fetch_article_rejects_non_http_scheme(self):
        with self.assertRaises(WebContentFetchError):
            WebContentFetcher().fetch_article("ftp://example.com/file")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher.urllib.request.urlopen")
    def test_fetch_article_allow_private_hosts_bypasses_guard(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(SAMPLE_HTML)

        article = WebContentFetcher(allow_private_hosts=True).fetch_article("http://10.0.0.1/x")

        self.assertEqual(article["title"], "Sample News Title")
        self.assertEqual(article["source_name"], "10.0.0.1")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher.urllib.request.urlopen")
    def test_fetch_article_returns_empty_content_when_no_body(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(
            "<html><head><title>Only Title</title></head><body></body></html>"
        )

        article = WebContentFetcher().fetch_article("https://example.com/empty")

        self.assertEqual(article["title"], "Only Title")
        self.assertEqual(article["content"], "")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher.urllib.request.urlopen")
    def test_fetch_article_raises_when_fetch_fails(self, mock_urlopen, _mock_private):
        mock_urlopen.side_effect = WebContentFetchError("超时")

        with self.assertRaises(WebContentFetchError):
            WebContentFetcher().fetch_article("https://example.com/x")


if __name__ == "__main__":
    unittest.main()
