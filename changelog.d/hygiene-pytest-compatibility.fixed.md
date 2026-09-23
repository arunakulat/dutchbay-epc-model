Explicitly exclude the Hypothesis database from pytest collection and bind the
class-scoped FX calibration fixture to its class, resolving both compatibility
warnings while preserving test collection, qualification controls and fixture values.
