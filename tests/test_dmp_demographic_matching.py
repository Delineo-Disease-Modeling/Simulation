"""DMP demographic matching: the request schema must reconcile with the DB's.

The engine emits demographics as Sex "M"/"F" and key "Vaccination Status"; the
legacy age/sex state machines in the DB use Sex "Male"/"Female" and key
"Vaccination". Without reconciliation the legacy constraint silently degrades to a
wildcard (different key) or never matches (different value), so age/sex
stratification never engages AND a vaccinated agent can leak into an unvaccinated
machine. These tests pin the canonicalization fix.

The pure-function tests always run. The full-routing tests use the real
state-machine DB via the in-process DMP and are skipped when it isn't available.
"""
import contextlib
import io
import unittest

from dmp.app.state_machine.state_machine_matching import (
    _canonicalize_demographics,
    _demographics_compatible,
)

# Engine request demographics (as emitted by infectionmgr._demographics_for).
REQ_70_M_UNVACC = {"Age": "70", "Sex": "M", "Vaccination Status": "Unvaccinated", "Variant": "Delta"}
REQ_30_M_UNVACC = {"Age": "30", "Sex": "M", "Vaccination Status": "Unvaccinated", "Variant": "Delta"}
REQ_70_M_VACC = {"Age": "70", "Sex": "M", "Vaccination Status": "Vaccinated", "Variant": "Delta"}

# DB machines.
M39_65P_MALE_UNVACC = {"Sex": "Male", "Age": "65+", "Vaccination": "Unvaccinated"}  # legacy keys
M59_GENERIC_UNVACC = {"Vaccination Status": "Unvaccinated"}
M54_GENERIC_VACC = {"Vaccination Status": "Vaccinated"}


class CanonicalizeTest(unittest.TestCase):
    def test_legacy_key_and_sex_value_canonicalize(self):
        self.assertEqual(
            _canonicalize_demographics(M39_65P_MALE_UNVACC),
            {"Sex": "Male", "Age": "65+", "Vaccination Status": "Unvaccinated"},
        )

    def test_request_sex_abbreviation_canonicalizes(self):
        self.assertEqual(_canonicalize_demographics({"Sex": "M"})["Sex"], "Male")
        self.assertEqual(_canonicalize_demographics({"Sex": "F"})["Sex"], "Female")


class DemographicsCompatibleTest(unittest.TestCase):
    def test_elderly_unvacc_male_matches_legacy_age_sex_machine(self):
        # Red before the fix: "M" != "Male" and "Vaccination Status" != "Vaccination".
        self.assertTrue(_demographics_compatible(REQ_70_M_UNVACC, M39_65P_MALE_UNVACC))

    def test_young_does_not_match_elderly_machine(self):
        self.assertFalse(_demographics_compatible(REQ_30_M_UNVACC, M39_65P_MALE_UNVACC))

    def test_vaccinated_does_not_leak_into_unvaccinated_age_machine(self):
        # The legacy machine's vaccination constraint must be ENFORCED, not dropped
        # as a different-key wildcard (which is what the old matcher did).
        self.assertFalse(_demographics_compatible(REQ_70_M_VACC, M39_65P_MALE_UNVACC))

    def test_generic_vaccination_machines_still_match(self):
        self.assertTrue(_demographics_compatible(REQ_30_M_UNVACC, M59_GENERIC_UNVACC))
        self.assertTrue(_demographics_compatible(REQ_70_M_VACC, M54_GENERIC_VACC))
        self.assertFalse(_demographics_compatible(REQ_70_M_VACC, M59_GENERIC_UNVACC))


def _dmp_available() -> bool:
    try:
        from simulator.dmp_inprocess import InProcessDMP

        InProcessDMP()
        return True
    except Exception:
        return False


DMP_AVAILABLE = _dmp_available()


@unittest.skipUnless(DMP_AVAILABLE, "in-process DMP DB/package not available")
class DemographicRoutingTest(unittest.TestCase):
    """Full routing through the real DB + specificity sort (the in-process path)."""

    def _match(self, request):
        from simulator.dmp_inprocess import InProcessDMP

        dmp = InProcessDMP()
        with contextlib.redirect_stdout(io.StringIO()):  # matcher prints diagnostics
            return dmp._dmp.find_matching_state_machine(
                "COVID-19", request, "variant.Delta.general"
            )

    def test_elderly_unvacc_routes_to_age_sex_machine(self):
        m = self._match(REQ_70_M_UNVACC)
        self.assertEqual(m["demographics"].get("Age"), "65+")
        self.assertEqual(
            _canonicalize_demographics(m["demographics"]).get("Sex"), "Male"
        )

    def test_young_unvacc_routes_to_generic(self):
        # No age constraint on the matched machine -> the generic unvacc machine.
        m = self._match(REQ_30_M_UNVACC)
        self.assertIsNone(m["demographics"].get("Age"))

    def test_vaccinated_elderly_does_not_route_to_unvacc_age_machine(self):
        # No vaccinated 65+ machine exists, so it must fall to the generic vacc
        # machine, NOT the unvaccinated age machine.
        m = self._match(REQ_70_M_VACC)
        self.assertIsNone(m["demographics"].get("Age"))
        canon = _canonicalize_demographics(m["demographics"])
        self.assertEqual(canon.get("Vaccination Status"), "Vaccinated")


if __name__ == "__main__":
    unittest.main()
