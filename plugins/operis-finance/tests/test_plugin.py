import importlib.util
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


margin = load("margin", ROOT / "skills/operis-finance-review/scripts/margin_review.py")
configuration = load("configuration", ROOT / "scripts/configure_customer.py")


class MarginTests(unittest.TestCase):
    def setUp(self):
        self.rows = margin.read_rows(ROOT / "tests/fixtures/synthetic-margin.csv")

    def test_weighted_margin_and_variance(self):
        result = margin.review(self.rows, "FY2026-P09", "FY2026-P08")["groups"][0]
        self.assertEqual(result["current"]["revenue"], Decimal("150000"))
        self.assertEqual(result["current"]["gross_profit"], Decimal("51000"))
        self.assertEqual(result["current"]["gross_margin_pct"], Decimal("34"))
        self.assertEqual(margin.display(result["prior"]["gross_margin_pct"]), "43.33")
        self.assertEqual(margin.display(result["changes"]["gross_margin_percentage_points"]), "-9.33")
        self.assertEqual(result["changes"]["gross_profit"], Decimal("-14000"))

    def test_currencies_and_companies_are_separate(self):
        other_currency = {**self.rows[0], "currency": "EUR", "record_id": "eur-1"}
        other_company = {**self.rows[0], "company": "Another Manufacturer"}
        result = margin.review(self.rows + [other_currency, other_company], "FY2026-P09", "FY2026-P08")
        self.assertEqual(len(result["groups"]), 3)

    def test_missing_period_is_not_zero(self):
        result = margin.review(self.rows, "FY2026-P10", "FY2026-P08")["groups"][0]
        self.assertIsNone(result["current"])
        self.assertIsNone(result["changes"])
        self.assertTrue(result["warnings"])

    def test_credit_note_is_signed(self):
        credit = {**self.rows[0], "record_id": "credit", "revenue": Decimal("-10000"), "cogs": Decimal("-6000")}
        result = margin.review(self.rows + [credit], "FY2026-P09", "FY2026-P08")["groups"][0]
        self.assertEqual(result["prior"]["revenue"], Decimal("140000"))
        self.assertEqual(result["prior"]["gross_profit"], Decimal("61000"))

    def test_zero_denominator_is_undefined(self):
        rows = [{**self.rows[0], "revenue": Decimal("0")}, {**self.rows[2], "revenue": Decimal("0")}]
        result = margin.review(rows, "FY2026-P09", "FY2026-P08")["groups"][0]
        self.assertIsNone(result["current"]["gross_margin_pct"])
        self.assertIsNone(result["changes"]["revenue_pct"])
        self.assertIsNone(result["changes"]["gross_margin_percentage_points"])

    def test_duplicate_records_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.csv"
            source = (ROOT / "tests/fixtures/synthetic-margin.csv").read_text()
            path.write_text(source + source.splitlines()[1] + "\n")
            with self.assertRaisesRegex(ValueError, "duplicate source record"):
                margin.read_rows(path)

    def test_bad_or_missing_amounts_rejected(self):
        for value in ["", "NaN", "Infinity", "1,200", "bad", "0.0000001", "1e999999", "9" * 1000]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                margin.amount(value, 2, "revenue")

    def test_comparison_must_exist_and_differ(self):
        for current, prior in [("FY2026-P08", "FY2026-P08"), ("missing", "absent"), ("", "FY2026-P08")]:
            with self.subTest(current=current, prior=prior), self.assertRaises(ValueError):
                margin.review(self.rows, current, prior)


class PackageTests(unittest.TestCase):
    def test_base_has_no_connection_or_customer_data(self):
        manifest = json.loads((ROOT / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "operis-finance")
        self.assertFalse((ROOT / "mcp.json").exists())
        self.assertFalse((ROOT / ".app.json").exists())
        self.assertNotIn("apps", manifest["extensions"]["com.openai"])
        for path in ROOT.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                content = path.read_text().lower()
                self.assertNotIn("bunting" + "gpt.com", content, str(path))
                self.assertNotIn("gp3" + ".app", content, str(path))

    def test_customer_copy_and_registered_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "customer"
            configuration.configure(output, "https://finance.customer-domain.com/mcp", "plugin_asdk_app_test_connection")
            config = json.loads((output / "mcp.json").read_text())
            self.assertEqual(config["mcpServers"]["operis_customer_finance"]["type"], "streamable-http")
            self.assertEqual(config["mcpServers"]["operis_customer_finance"]["url"], "https://finance.customer-domain.com/mcp")
            apps = json.loads((output / ".app.json").read_text())
            self.assertTrue(apps["apps"]["operis_customer_finance"]["required"])
            self.assertFalse((ROOT / "mcp.json").exists())
            self.assertFalse((output / "tests").exists())

    def test_endpoint_validation_excludes_credentials_and_local_hosts(self):
        for endpoint in ["http://finance.customer-domain.com/mcp", "https://user:secret@finance.customer-domain.com/mcp",
                         "https://finance.customer-domain.com/mcp?token=secret", "https://localhost/mcp",
                         "https://127.0.0.1/mcp", "https://10.0.0.1/mcp", "https://example.com/mcp",
                         "https://bad..domain.com/mcp", "https://finance.customer-domain.com:invalid/mcp"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                configuration.validate_endpoint(endpoint)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "already exists"):
                configuration.configure(directory, "https://finance.customer-domain.com/mcp")

    def test_source_is_not_configured_in_place(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            configuration.configure(ROOT / "customer", "https://finance.customer-domain.com/mcp")

    def test_repo_marketplace_resolves_package(self):
        repository = ROOT.parents[1]
        marketplace = json.loads((repository / ".agents/plugins/marketplace.json").read_text())
        entry = next(item for item in marketplace["plugins"] if item["name"] == "operis-finance")
        self.assertEqual((repository / entry["source"]["path"]).resolve(), ROOT)


if __name__ == "__main__":
    unittest.main()
