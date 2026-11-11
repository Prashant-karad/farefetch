"""License guard core tests. Run: python -m unittest discover -s tests -v (from platform/)."""

import unittest
from datetime import datetime, timedelta, timezone

from app.services.license_core import Item, all_violations, check, deterministic_fix, longest_common_run, words

SOURCE = ("Before the kharif season, a simple soil check saves money on fertilizer. Farmers in our Pune district "
          "field visits who tested nitrogen, phosphorus and potassium before sowing applied fertilizer in measured "
          "doses instead of guessing.")


def item(**kw) -> Item:
    base = dict(resource_id="res_a", path="/blog/a", title="Soil health checks", text=SOURCE,
                license_id="lic_read_24h", license_type="read", max_quote_words=8, attribution_required=True,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1), grant_id="grt_1")
    base.update(kw)
    return Item(**base)


class LicenseCoreTest(unittest.TestCase):
    def test_longest_run(self):
        self.assertEqual(longest_common_run(words("a b c d x"), words("z a b c d"))[0], 4)

    def test_clean_paraphrase_passes(self):
        answer = "Testing soil weeks before sowing helps farmers dose fertilizer precisely [res_a]."
        self.assertEqual(all_violations(check(answer, [item()])), [])

    def test_verbatim_copy_and_missing_citation(self):
        answer = ("Farmers in our Pune district field visits who tested nitrogen, phosphorus and potassium "
                  "before sowing did well.")
        types = {v["type"] for v in all_violations(check(answer, [item()]))}
        self.assertEqual(types, {"verbatim_copy", "missing_attribution"})

    def test_quote_license_allows_longer_quotes(self):
        answer = ('As [res_a] puts it: "Farmers in our Pune district field visits who tested nitrogen, '
                  'phosphorus and potassium".')
        self.assertEqual(all_violations(check(answer, [item(license_type="quote", max_quote_words=50)])), [])

    def test_expired_license(self):
        answer = "Soil testing before sowing pays off [res_a]."
        expired = item(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        self.assertEqual([v["type"] for v in all_violations(check(answer, [expired]))], ["license_expired"])

    def test_deterministic_fix_removes_violations(self):
        answer = ("Soil testing matters. Farmers in our Pune district field visits who tested nitrogen, "
                  "phosphorus and potassium before sowing did well.")
        results = check(answer, [item()])
        fixed = deterministic_fix(answer, [item()], results)
        self.assertEqual(all_violations(check(fixed, [item()])), [])


if __name__ == "__main__":
    unittest.main()
