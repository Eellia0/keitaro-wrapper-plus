import unittest
from fastapi import HTTPException
from app.editor import distribute

class DistributionTests(unittest.TestCase):
    def offer(self, share=0, pinned=False, removed=False):
        return dict(share=share, pinned=pinned, removed=removed)

    def test_rounding_totals_one_hundred(self):
        offers = [self.offer() for _ in range(3)]
        distribute(offers)
        self.assertEqual([offer['share'] for offer in offers], [33, 33, 34])

    def test_pinned_share_is_preserved(self):
        offers = [self.offer(25, True), self.offer(), self.offer()]
        distribute(offers)
        self.assertEqual([offer['share'] for offer in offers], [25, 37, 38])

    def test_removed_offer_has_zero_share(self):
        offers = [self.offer(70, removed=True), self.offer()]
        distribute(offers)
        self.assertEqual([offer['share'] for offer in offers], [0, 100])

    def test_pinned_total_over_one_hundred_is_rejected(self):
        with self.assertRaises(HTTPException):
            distribute([self.offer(60, True), self.offer(50, True)])

    def test_all_pinned_incomplete_total_is_rejected(self):
        with self.assertRaises(HTTPException):
            distribute([self.offer(25, True)])

if __name__ == '__main__':
    unittest.main()
