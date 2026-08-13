from __future__ import annotations

import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_guard_front_one_step as runner


# Narrow implementation correction: the original runner uses the module-global
# name `base` but omitted the corresponding import. Bind that exact module
# without changing any physics, tolerances, root construction, or solver gates.
runner.base = base


if __name__ == "__main__":
    runner.main()
