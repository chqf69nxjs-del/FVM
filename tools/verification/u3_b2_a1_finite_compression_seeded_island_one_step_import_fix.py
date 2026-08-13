from __future__ import annotations

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_seeded_island_one_step as runner


# Narrow implementation correction. The reused one-step module references the
# module-global name `base` but omits its import. Bind the exact authoritative
# finite-compression module without changing any model, root, tolerance, flux,
# solver update, or gate.
runner.one_step.base = base


if __name__ == "__main__":
    runner.main()
