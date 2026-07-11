import unittest

from app.services.web.page_recognizer import PageRecognizer


class PageRecognizerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.recognizer = PageRecognizer()

    def test_recognizes_static_article_page(self) -> None:
        html = """
        <html><head><title>Static News</title></head><body>
          <article>
            <h1>Static News</h1>
            <p>This is a normal article paragraph with enough readable text for extraction.</p>
            <p>This second paragraph confirms that the page already carries readable HTML.</p>
          </article>
        </body></html>
        """

        result = self.recognizer.recognize(
            html,
            final_url="https://example.com/news/static",
            title="Static News",
            content=(
                "This is a normal article paragraph with enough readable text for extraction. "
                "This second paragraph confirms that the page already carries readable HTML."
            ),
            extraction_method="html",
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.page_type, "static_article")
        self.assertEqual(result.recommended_method, "html")
        self.assertIn("semantic_article_container", result.signals)
        self.assertGreaterEqual(result.confidence, 0.85)

    def test_recognizes_structured_article_before_dynamic_shell(self) -> None:
        html = """
        <html><head>
          <title>Client Shell</title>
          <script id="__NEXT_DATA__" type="application/json">{}</script>
        </head><body><div id="__next"></div></body></html>
        """

        result = self.recognizer.recognize(
            html,
            final_url="https://example.com/news/structured",
            title="Structured News",
            content="Structured article body extracted from script data with enough readable text.",
            extraction_method="structured_data",
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.page_type, "structured_article")
        self.assertEqual(result.recommended_method, "structured_data")
        self.assertIn("structured_article_data", result.signals)

    def test_recognizes_login_wall_and_login_url(self) -> None:
        html = """
        <html><head><title>Please sign in</title></head><body>
          <main>
            <h1>Please sign in to continue</h1>
            <form action="/login"><input type="password" name="password"></form>
          </main>
        </body></html>
        """

        result = self.recognizer.recognize(
            html,
            final_url="https://example.com/news/private",
            title="Please sign in",
            content="",
            extraction_method="html",
        )

        self.assertEqual(result.status, "login_required")
        self.assertEqual(result.page_type, "login_wall")
        self.assertEqual(result.recovery_action, "open_login_then_retry")
        self.assertEqual(result.login_url, "https://example.com/login")

    def test_recognizes_anti_bot_wall(self) -> None:
        html = """
        <html><head><title>Access denied</title></head><body>
          <main>
            <h1>Access denied</h1>
            <p>Please verify you are human before continuing.</p>
            <div class="cf-turnstile"></div>
          </main>
        </body></html>
        """

        result = self.recognizer.recognize(
            html,
            final_url="https://example.com/protected",
            title="Access denied",
            content="Please verify you are human before continuing.",
            extraction_method="html",
        )

        self.assertEqual(result.status, "blocked_by_anti_bot")
        self.assertEqual(result.page_type, "anti_bot_wall")
        self.assertEqual(result.recovery_action, "manual_input")
        self.assertIn("anti_bot_marker", result.signals)

    def test_recognizes_client_rendered_shell(self) -> None:
        html = """
        <html><head><title>Rendered News</title></head><body>
          <noscript>You need to enable JavaScript to run this app.</noscript>
          <div id="root"></div>
          <script src="/static/runtime.js"></script>
          <script src="/static/news.js"></script>
        </body></html>
        """

        result = self.recognizer.recognize(
            html,
            final_url="https://example.com/render-only",
            title="Rendered News",
            content="",
            extraction_method="html",
        )

        self.assertEqual(result.status, "dynamic_render_required")
        self.assertEqual(result.page_type, "client_rendered_shell")
        self.assertEqual(result.recovery_action, "manual_input")
        self.assertIn("client_render_marker", result.signals)


if __name__ == "__main__":
    unittest.main()
