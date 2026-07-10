import os
import unittest
from unittest.mock import Mock, patch

import feishu_alerts


class FeishuAlertBridgeTestCase(unittest.TestCase):
    def test_format_feishu_text_summarizes_alertmanager_payload(self) -> None:
        payload = {
            "status": "firing",
            "groupLabels": {"service": "backend"},
            "externalURL": "http://alertmanager:9093",
            "alerts": [
                {
                    "labels": {
                        "alertname": "BackendHighErrorRate",
                        "severity": "page",
                        "service": "backend",
                    },
                    "annotations": {
                        "summary": "Backend 5xx error rate is above 1%",
                        "runbook": "docs/deployment/runbook.md#backendhigherrorrate",
                    },
                }
            ],
        }

        text = feishu_alerts.format_feishu_text(payload)

        self.assertIn("[FIRING] NewsCred 告警", text)
        self.assertIn("BackendHighErrorRate [page]", text)
        self.assertIn("Runbook:", text)
        self.assertIn("Alertmanager: http://alertmanager:9093", text)

    def test_post_to_feishu_rejects_non_feishu_webhook_host(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "host"):
            feishu_alerts.post_to_feishu(
                "https://example.com/open-apis/bot/v2/hook/token",
                "test",
            )

    def test_post_to_feishu_sends_text_message_payload(self) -> None:
        response = Mock()
        response.status = 200
        response.read.return_value = b'{"code":0,"msg":"success"}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            feishu_alerts.post_to_feishu(
                "https://open.feishu.cn/open-apis/bot/v2/hook/token",
                "hello",
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertIn(b'"msg_type": "text"', request.data)
        self.assertIn("hello".encode("utf-8"), request.data)


if __name__ == "__main__":
    os.environ.setdefault(
        "FEISHU_WEBHOOK_URL",
        "https://open.feishu.cn/open-apis/bot/v2/hook/test",
    )
    unittest.main()
