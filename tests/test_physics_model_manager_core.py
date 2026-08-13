from liquid_gas_transient.physics_model_manager import FINITE_COMPRESSION_MODEL_REQUIRED, NO_ADMISSIBLE_ISLAND, PhysicsBoundaryModelManager


def test_increment_9m_a0_sequence() -> None:
    manager = PhysicsBoundaryModelManager()
    manager.activate_finite_compression(trigger_classification=FINITE_COMPRESSION_MODEL_REQUIRED)
    manager.close_zero_transfer(trigger_classification=NO_ADMISSIBLE_ISLAND)
    assert len(manager.transition_history) == 2
