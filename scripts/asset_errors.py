"""Capability errors shared by CLI and native tool adapters."""


class DependencyMissing(ValueError):
    pass


class ApprovalRequired(ValueError):
    pass


class AssetConflict(ValueError):
    pass
