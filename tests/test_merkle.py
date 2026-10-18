import unittest
from app.merkle import build_tree, verify_proof


class TestMerkleTree(unittest.TestCase):
    def test_single_leaf(self):
        leaves = ["a" * 64]
        root, proofs = build_tree(leaves)
        self.assertEqual(root, leaves[0])
        self.assertEqual(len(proofs), 1)
        self.assertTrue(verify_proof(leaves[0], proofs[0], root))

    def test_even_and_odd_leaf_counts(self):
        for count in range(2, 10):
            with self.subTest(count=count):
                leaves = [f"{i:064x}" for i in range(count)]
                root, proofs = build_tree(leaves)
                self.assertEqual(len(proofs), count)
                for leaf, proof in zip(leaves, proofs):
                    self.assertTrue(verify_proof(leaf, proof, root))

    def test_tampered_leaf_fails(self):
        leaves = [f"{i:064x}" for i in range(5)]
        root, proofs = build_tree(leaves)
        self.assertFalse(verify_proof("f" * 64, proofs[2], root))

    def test_tampered_sibling_fails(self):
        leaves = [f"{i:064x}" for i in range(5)]
        root, proofs = build_tree(leaves)
        altered = [dict(step) for step in proofs[2]]
        altered[0]["sibling"] = "f" * 64
        self.assertFalse(verify_proof(leaves[2], altered, root))

    def test_invalid_side_fails(self):
        leaves = [f"{i:064x}" for i in range(3)]
        root, proofs = build_tree(leaves)
        altered = [dict(step) for step in proofs[0]]
        altered[0]["side"] = "middle"
        self.assertFalse(verify_proof(leaves[0], altered, root))

    def test_empty_tree_is_rejected(self):
        with self.assertRaises(ValueError):
            build_tree([])


if __name__ == "__main__":
    unittest.main()
