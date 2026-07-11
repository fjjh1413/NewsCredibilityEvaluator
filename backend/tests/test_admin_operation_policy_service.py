import unittest

from app.services.admin_operation_policy_service import list_admin_operation_policies


class AdminOperationPolicyServiceTestCase(unittest.TestCase):
    def test_lists_high_risk_policies_with_expected_controls(self) -> None:
        policies = list_admin_operation_policies()

        self.assertGreaterEqual(len(policies), 8)
        operation_keys = {policy["operation_key"] for policy in policies}
        self.assertIn("report.delete", operation_keys)
        self.assertIn("user.update_role", operation_keys)
        self.assertIn("knowledge.rebuild_index", operation_keys)

        report_delete = next(
            policy for policy in policies if policy["operation_key"] == "report.delete"
        )
        self.assertEqual(report_delete["risk_level"], "high")
        self.assertTrue(report_delete["requires_confirmation"])
        self.assertEqual(report_delete["target_type"], "report")
        self.assertIn("request_id", report_delete["audit_fields"])
        self.assertIn("rollback_hint", report_delete)

    def test_filters_by_risk_level(self) -> None:
        policies = list_admin_operation_policies(risk_level="critical")

        self.assertTrue(policies)
        self.assertTrue(all(policy["risk_level"] == "critical" for policy in policies))


if __name__ == "__main__":
    unittest.main()
