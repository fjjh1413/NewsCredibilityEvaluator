import unittest
import urllib.error
from unittest.mock import patch

from app.services.web.web_content_fetcher import (
    AntiBotBlockedError,
    DynamicRenderRequiredError,
    LoginRequiredError,
    SSRFBlockedError,
    WebContentFetchError,
    WebContentFetcher,
    _is_private_host,
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
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
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
        self.assertEqual(article["page_type"], "static_article")
        self.assertIn("semantic_article_container", article["recognition_signals"])
        self.assertGreaterEqual(article["recognition_confidence"], 0.85)

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
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
        self.assertEqual(article["publish_time_precision"], "datetime")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_reads_structured_script_when_dom_is_empty(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head>
            <title>Client Rendered Shell</title>
            <script id="__NEXT_DATA__" type="application/json">
              {
                "props": {
                  "pageProps": {
                    "article": {
                      "headline": "Structured News Title",
                      "articleBody": "Structured article body with enough detail to be used when the rendered DOM has no paragraphs."
                    }
                  }
                }
              }
            </script>
            </head><body><div id="__next"></div></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/rendered")

        self.assertEqual(article["title"], "Structured News Title")
        self.assertIn("Structured article body", article["content"])
        self.assertEqual(article["extraction_method"], "structured_data")
        self.assertIn("dom_content_empty", article["warnings"])
        self.assertEqual(article["page_type"], "structured_article")
        self.assertEqual(article["recommended_extraction_method"], "structured_data")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_prefers_headline_datetime_over_date_only_meta(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head>
            <meta name="publishdate" content="2026-06-19">
            <title>Railway News</title>
            </head><body>
            <div class="headline">
              <h1>Railway News</h1>
              <div><span>2026</span> <span>06</span> / <span>19</span> 14:30:54 Source: Example News</div>
            </div>
            <article>
              <p>This paragraph is long enough to be retained as article content.</p>
            </article>
            </body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/3")

        self.assertEqual(article["publish_time"], "2026-06-19T14:30:54")
        self.assertEqual(article["publish_time_precision"], "datetime")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_returns_date_precision_when_only_date_is_available(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head>
            <meta name="publishdate" content="2026/06/19">
            <title>Date-only News</title>
            </head><body><article>
              <p>This paragraph is long enough to be retained as article content.</p>
            </article></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/4")

        self.assertEqual(article["publish_time"], "2026-06-19")
        self.assertEqual(article["publish_time_precision"], "date")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_ignores_body_dates_without_publish_metadata(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head><title>Event News</title></head><body>
            <h1>Event News</h1>
            <article>
              <p>The event starts on 2026-06-21 09:00 and ends later that day.</p>
            </article></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/5")

        self.assertIsNone(article["publish_time"])
        self.assertIsNone(article["publish_time_precision"])

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_ignores_generic_time_element_in_article_body(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head><title>Event News</title></head><body>
            <article>
              <h1>Event News</h1>
              <p>The event starts at <time datetime="2026-06-21T09:00:00">9 AM</time>
              and this paragraph is long enough to be retained as article content.</p>
            </article></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/body-time")

        self.assertIsNone(article["publish_time"])
        self.assertIsNone(article["publish_time_precision"])

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_reads_generic_time_element_in_semantic_header(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head><title>Header Time News</title></head><body>
            <article>
              <header><h1>Header Time News</h1>
              <time datetime="2026-06-19T14:30:54+08:00">Published</time></header>
              <p>This paragraph is long enough to be retained as article content.</p>
            </article></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/header-time")

        self.assertEqual(article["publish_time"], "2026-06-19T14:30:54+08:00")
        self.assertEqual(article["publish_time_precision"], "datetime")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_ignores_json_ld_date_modified(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head><title>Modified News</title>
            <script type="application/ld+json">
              {"@type":"NewsArticle","dateModified":"2026-06-19T14:30:54+08:00"}
            </script>
            </head><body><article>
              <p>This paragraph is long enough to be retained as article content.</p>
            </article></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/6")

        self.assertIsNone(article["publish_time"])
        self.assertIsNone(article["publish_time_precision"])

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_normalizes_timezone_without_colon(
        self, mock_urlopen, _mock_private
    ):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head>
            <meta property="article:published_time" content="2026-06-19 14:30:54+0800">
            <title>Timezone News</title>
            </head><body><article>
              <p>This paragraph is long enough to be retained as article content.</p>
            </article></body></html>
            """
        )

        article = WebContentFetcher().fetch_article("https://example.com/news/7")

        self.assertEqual(article["publish_time"], "2026-06-19T14:30:54+08:00")
        self.assertEqual(article["publish_time_precision"], "datetime")

    def test_regex_fallback_uses_the_same_candidate_priority(self):
        html = """
        <html><head><meta content="2026-06-19" name="publishdate"></head><body>
        <h1>Fallback News</h1>
        <div><span>2026</span> <span>06</span> / <span>19</span> 14:30:54</div>
        <article><p>Article body with enough text for extraction.</p></article>
        </body></html>
        """

        result = WebContentFetcher()._extract_publish_time_regex(html)

        self.assertIsNotNone(result)
        self.assertEqual(result.value, "2026-06-19T14:30:54")
        self.assertEqual(result.precision, "datetime")

    def test_regex_fallback_reads_time_element_in_semantic_header(self):
        html = """
        <html><body><article><header>
        <h1>Fallback Header News</h1>
        <time datetime="2026-06-19T14:30:54+08:00">Published</time>
        </header><p>Article body with enough text for extraction.</p></article>
        </body></html>
        """

        result = WebContentFetcher()._extract_publish_time_regex(html)

        self.assertIsNotNone(result)
        self.assertEqual(result.value, "2026-06-19T14:30:54+08:00")
        self.assertEqual(result.precision, "datetime")

    def test_regex_fallback_does_not_scan_article_body_dates(self):
        html = """
        <html><body><article><h1>Fallback Event News</h1>
        <p>The event starts on 2026-06-21 09:00 and this is article body text.</p>
        </article></body></html>
        """

        result = WebContentFetcher()._extract_publish_time_regex(html)

        self.assertIsNone(result)

    def test_publish_time_normalizer_rejects_invalid_calendar_date(self):
        result = WebContentFetcher()._normalize_publish_time_candidate(
            "2026-02-30T14:30:54"
        )

        self.assertIsNone(result)

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
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

    @patch(
        "app.services.web.web_content_fetcher.socket.getaddrinfo",
        return_value=[
            (None, None, None, None, ("93.184.216.34", 0)),
            (None, None, None, None, ("10.0.0.5", 0)),
        ],
    )
    def test_private_host_blocks_any_reserved_dns_record(self, _mock_getaddrinfo):
        self.assertTrue(_is_private_host("example.com"))

    @patch("app.services.web.web_content_fetcher._is_private_host")
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_blocks_redirect_to_private_ip(self, mock_open, mock_private):
        mock_private.side_effect = [False, True]
        mock_open.side_effect = urllib.error.HTTPError(
            "https://example.com/news",
            302,
            "Found",
            {"Location": "http://127.0.0.1/admin"},
            None,
        )

        with self.assertRaises(SSRFBlockedError):
            WebContentFetcher().fetch_article("https://example.com/news")

    def test_fetch_article_rejects_non_http_scheme(self):
        with self.assertRaises(WebContentFetchError):
            WebContentFetcher().fetch_article("ftp://example.com/file")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_detects_login_wall(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head><title>Please sign in</title></head><body>
              <main>
                <h1>Please sign in to continue</h1>
                <form action="/login"><input type="password" name="password"></form>
              </main>
            </body></html>
            """
        )

        with self.assertRaises(LoginRequiredError) as raised:
            WebContentFetcher().fetch_article("https://example.com/news/private")

        self.assertEqual(raised.exception.login_url, "https://example.com/login")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_detects_antibot_wall(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head><title>Access denied</title></head><body>
              <main>
                <h1>Access denied</h1>
                <p>Please verify you are human before continuing.</p>
                <div class="cf-turnstile"></div>
              </main>
            </body></html>
            """
        )

        with self.assertRaises(AntiBotBlockedError) as raised:
            WebContentFetcher().fetch_article("https://example.com/protected")

        self.assertEqual(raised.exception.status, "blocked_by_anti_bot")
        self.assertEqual(raised.exception.recovery_action, "manual_input")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_detects_client_rendered_shell(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(
            """
            <html><head><title>Rendered News</title></head><body>
              <noscript>You need to enable JavaScript to run this app.</noscript>
              <div id="root"></div>
              <script src="/static/runtime.js"></script>
              <script src="/static/news.js"></script>
            </body></html>
            """
        )

        with self.assertRaises(DynamicRenderRequiredError) as raised:
            WebContentFetcher().fetch_article("https://example.com/render-only")

        self.assertEqual(raised.exception.status, "dynamic_render_required")
        self.assertEqual(raised.exception.recovery_action, "manual_input")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_allow_private_hosts_bypasses_guard(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(SAMPLE_HTML)

        article = WebContentFetcher(allow_private_hosts=True).fetch_article("http://10.0.0.1/x")

        self.assertEqual(article["title"], "Sample News Title")
        self.assertEqual(article["source_name"], "10.0.0.1")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_returns_empty_content_when_no_body(self, mock_urlopen, _mock_private):
        mock_urlopen.return_value = _FakeResponse(
            "<html><head><title>Only Title</title></head><body></body></html>"
        )

        article = WebContentFetcher().fetch_article("https://example.com/empty")

        self.assertEqual(article["title"], "Only Title")
        self.assertEqual(article["content"], "")

    @patch("app.services.web.web_content_fetcher._is_private_host", return_value=False)
    @patch("app.services.web.web_content_fetcher._open_without_redirects")
    def test_fetch_article_raises_when_fetch_fails(self, mock_urlopen, _mock_private):
        mock_urlopen.side_effect = WebContentFetchError("超时")

        with self.assertRaises(WebContentFetchError):
            WebContentFetcher().fetch_article("https://example.com/x")


if __name__ == "__main__":
    unittest.main()
