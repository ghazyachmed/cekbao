"""Message catalog: English plural forms for counted summaries."""
from policyguard.web.i18n import tn


def test_counted_messages_use_the_singular_form_for_one():
    assert tn("compare.n_conflict", 1) == "1 detail conflicts with the policy"
    assert tn("compare.n_conflict", 3) == "3 details conflict with the policy"
    assert tn("compare.n_agree", 1) == "1 agrees"
    assert tn("compare.n_agree", 4) == "4 agree"


def test_counted_message_without_a_singular_form_falls_back_to_the_base_key():
    assert tn("compare.n_missing", 1) == "1 not stated in the instruction"
