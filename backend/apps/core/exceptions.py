"""Shared domain exceptions."""
from django.core.exceptions import ValidationError


class MaxDebateIterationsExceededError(Exception):
    """Raised when 3-agent debate exceeds MAX_DEBATE_ITERATIONS."""


class CardMutationValidationError(ValidationError):
    """User card edit violates capacity or availability rules."""


class InventoryLockConflictError(Exception):
    """Concurrent booking could not acquire row lock."""


class FloorPriceBreachAttemptError(Exception):
    """Negotiated price below walk-away floor."""


class TemplateValidationException(ValidationError):
    """Proposal template missing placeholders or unsafe markup."""


class PricingBoundsViolationError(Exception):
    """XGBoost returned invalid bounds; triggers fallback engine."""


class MapVectorizationFallbackHandler(Exception):
    """Map confidence below threshold; enable manual polygon editor."""
