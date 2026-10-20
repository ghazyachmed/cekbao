import unittest
from checker import analyze, domain_from_url

class BaselineTests(unittest.TestCase):
    def test_spoof_domain(self):
        self.assertEqual(domain_from_url('https://university.example.edu.evil.test/p'), 'university.example.edu.evil.test')
    def test_http_not_accepted(self):
        self.assertEqual(domain_from_url('http://university.example.edu/pay'), '')
    def test_domain_mismatch_flags(self):
        result=analyze({'institution':'DEMO-INTL','request_url':'https://evil.test','payee':'X','channel':'bank_transfer'})
        self.assertIn('REQUEST_DOMAIN_MISMATCH',result['risk_flags'])
    def test_payee_mismatch(self):
        result=analyze({'institution':'DEMO-INTL','request_url':'https://university.example.edu','payee':'X','channel':'official_portal'})
        self.assertIn('PAYEE_MISMATCH',result['risk_flags'])
    def test_missing_slip_in_synthetic_ledger(self):
        result=analyze({'institution':'DEMO-ID','request_url':'https://campus.example.ac.id','payee':'Example Campus Billing Account','channel':'bank_va','slip_id':'S','amount':'3','synthetic_university_ledger':{}})
        self.assertIn('SLIP_NOT_FOUND_IN_SYNTHETIC_LEDGER',result['risk_flags'])
    def test_ledger_disagreement(self):
        result=analyze({'institution':'DEMO-ID','request_url':'https://campus.example.ac.id','payee':'Example Campus Billing Account','channel':'bank_va','slip_id':'S','amount':'3','synthetic_university_ledger':{'S':'4'}})
        self.assertIn('LEDGER_AMOUNT_MISMATCH',result['risk_flags'])
    def test_unknown_fails_closed(self):
        self.assertEqual(analyze({'institution':'NEW'})['status'],'NOT_VERIFIABLE')
    def test_policy_match_not_settlement(self):
        result=analyze({'institution':'DEMO-INTL','request_url':'https://university.example.edu/portal','payee':'Example University Official Tuition Account','channel':'official_portal'})
        self.assertEqual(result['status'],'MATCHES_SYNTHETIC_POLICY_ONLY')
        self.assertFalse(result['verified_bank_settlement'])
    def test_urgency_flag(self):
        result=analyze({'institution':'DEMO-INTL','request_url':'https://university.example.edu/portal','payee':'Example University Official Tuition Account','channel':'official_portal','urgent_pressure':True})
        self.assertIn('URGENCY_PRESSURE',result['risk_flags'])
    def test_no_spoof_subdomain(self):
        result=analyze({'institution':'DEMO-INTL','request_url':'https://university.example.edu.attacker.com','payee':'Example University Official Tuition Account','channel':'official_portal'})
        self.assertNotEqual(result['status'],'MATCHES_SYNTHETIC_POLICY_ONLY')

if __name__ == '__main__':
    unittest.main(verbosity=2)
