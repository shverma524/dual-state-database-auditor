from .hashing import sha256_hex

def parent_hash(left_hex: str, right_hex: str) -> str:
    return sha256_hex(bytes.fromhex(left_hex) + bytes.fromhex(right_hex))

def build_tree(leaves: list[str]) -> tuple[str, list[list[dict]]]:
    """
    Returns root and one proof per leaf. Each proof item includes sibling hash
    and sibling side ('left' or 'right'), so verification is order-correct.
    Odd nodes are duplicated at each level.
    """
    if not leaves:
        raise ValueError("Cannot build a Merkle tree with zero leaves")

    level = list(leaves)
    proofs = [[] for _ in leaves]
    positions = list(range(len(leaves)))

    while len(level) > 1:
        original_len = len(level)
        if original_len % 2:
            level = level + [level[-1]]

        for leaf_i, pos in enumerate(positions):
            sibling_pos = pos - 1 if pos % 2 else pos + 1
            sibling_hash = level[sibling_pos]
            proofs[leaf_i].append({
                "sibling": sibling_hash,
                "side": "left" if pos % 2 else "right",
            })
            positions[leaf_i] = pos // 2

        level = [
            parent_hash(level[i], level[i + 1])
            for i in range(0, len(level), 2)
        ]

    return level[0], proofs

def verify_proof(leaf_hash: str, proof: list[dict], expected_root: str) -> bool:
    """Verify a Merkle proof; reject malformed input without raising errors."""
    def valid_hash(value):
        if not isinstance(value, str) or len(value) != 64:
            return False
        try:
            bytes.fromhex(value)
            return True
        except ValueError:
            return False

    if not valid_hash(leaf_hash) or not valid_hash(expected_root):
        return False
    if not isinstance(proof, list):
        return False

    node = leaf_hash
    try:
        for step in proof:
            if not isinstance(step, dict):
                return False

            sibling = step.get("sibling")
            side = step.get("side")

            if not valid_hash(sibling):
                return False

            if side == "left":
                node = parent_hash(sibling, node)
            elif side == "right":
                node = parent_hash(node, sibling)
            else:
                return False

        return node == expected_root
    except (TypeError, ValueError, KeyError):
        return False
