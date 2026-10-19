"""Application configuration.

All runtime configuration is read from environment variables (optionally a
project-local ``.env`` file).  Configuration is validated at import/startup
time so that a misconfigured process fails fast instead of at first use.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]

VALID_PAYMENT_MODES = ("success", "fail_twice", "always_fail")
VALID_RESTAURANT_MODES = ("success", "always_fail")
VALID_DELIVERY_MODES = ("success", "always_fail")
VALID_NOTIFICATION_MODES = ("success", "always_fail")
VALID_CRASH_MODES = ("none", "before_commit", "after_commit_before_ack")
VALID_DISPATCHER_CRASH_MODES = ("none", "after_publish_before_sent")


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=str(WORKSPACE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- core -------------------------------------------------------------
    project_name: str = "QuickBite"
    environment: str = Field(default="development")
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- database ---------------------------------------------------------
    database_url: str = (
        "postgresql+asyncpg://quickbite:quickbite@127.0.0.1:55432/quickbite"
    )
    # Readiness probe timeout (seconds)
    db_probe_timeout_seconds: float = 2.0

    # --- broker -----------------------------------------------------------
    amqp_url: str = "amqp://guest:guest@127.0.0.1:5672/"
    amqp_probe_timeout_seconds: float = 2.0

    # --- auth -------------------------------------------------------------
    jwt_secret: str = "quickbite-development-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "quickbite"
    jwt_access_token_expire_minutes: int = 120

    # --- http -------------------------------------------------------------
    cors_origins: str = (
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:5000,http://127.0.0.1:5000"
    )

    # --- pagination -------------------------------------------------------
    default_page_size: int = 20
    max_page_size: int = 100

    # --- simulation delays (development/demo) ----------------------------
    sim_payment_delay_ms: int = 2500
    sim_restaurant_delay_ms: int = 3500
    sim_delivery_delay_ms: int = 2500
    sim_notification_delay_ms: int = 500

    # --- deterministic demo failure controls -----------------------------
    demo_payment_mode: str = "success"
    demo_payment_fail_count: int = 2
    demo_restaurant_mode: str = "success"
    demo_delivery_mode: str = "success"
    demo_notification_mode: str = "success"
    # Crash the payment worker at a checkpoint, limited to a single order id
    # so that recovery demos are reproducible.
    demo_crash_mode: str = "none"
    demo_crash_order_id: str | None = None
    # Crash the outbox dispatcher after publish but before marking sent.
    dispatcher_crash_mode: str = "none"
    dispatcher_crash_order_id: str | None = None

    # --- bounded retries --------------------------------------------------
    retry_max_attempts: int = 3
    # Comma separated, index 0 -> retry #1 delay, etc.
    retry_delays_seconds: str = "2,10,30"
    outbox_poll_interval_ms: int = 250
    outbox_batch_size: int = 25
    outbox_lease_seconds: int = 30
    scheduler_poll_interval_ms: int = 250
    worker_prefetch_count: int = 8

    # --- validation limits ------------------------------------------------
    max_distinct_order_items: int = 20
    min_item_quantity: int = 1
    max_item_quantity: int = 20
    min_delivery_address_length: int = 10
    max_delivery_address_length: int = 300

    # ------------------------------------------------------------------ #
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def retry_delays(self) -> list[float]:
        delays = [float(x) for x in self.retry_delays_seconds.split(",") if x.strip()]
        if len(delays) != self.retry_max_attempts:
            raise ValueError(
                "retry_delays_seconds must contain exactly retry_max_attempts values"
            )
        return delays

    @field_validator("demo_payment_mode")
    @classmethod
    def _payment_mode(cls, v: str) -> str:
        if v not in VALID_PAYMENT_MODES:
            raise ValueError(f"demo_payment_mode must be one of {VALID_PAYMENT_MODES}")
        return v

    @field_validator("demo_restaurant_mode")
    @classmethod
    def _restaurant_mode(cls, v: str) -> str:
        if v not in VALID_RESTAURANT_MODES:
            raise ValueError(
                f"demo_restaurant_mode must be one of {VALID_RESTAURANT_MODES}"
            )
        return v

    @field_validator("demo_delivery_mode")
    @classmethod
    def _delivery_mode(cls, v: str) -> str:
        if v not in VALID_DELIVERY_MODES:
            raise ValueError(f"demo_delivery_mode must be one of {VALID_DELIVERY_MODES}")
        return v

    @field_validator("demo_notification_mode")
    @classmethod
    def _notification_mode(cls, v: str) -> str:
        if v not in VALID_NOTIFICATION_MODES:
            raise ValueError(
                f"demo_notification_mode must be one of {VALID_NOTIFICATION_MODES}"
            )
        return v

    @field_validator("demo_crash_mode")
    @classmethod
    def _crash_mode(cls, v: str) -> str:
        if v not in VALID_CRASH_MODES:
            raise ValueError(f"demo_crash_mode must be one of {VALID_CRASH_MODES}")
        return v

    @field_validator("dispatcher_crash_mode")
    @classmethod
    def _dispatcher_crash(cls, v: str) -> str:
        if v not in VALID_DISPATCHER_CRASH_MODES:
            raise ValueError(
                f"dispatcher_crash_mode must be one of {VALID_DISPATCHER_CRASH_MODES}"
            )
        return v

    def validate_for_runtime(self) -> None:
        """Fail fast on unsafe production configuration.

        Deterministic failure injection and weak secrets are development/demo
        features only; they are rejected when ``environment`` is production.
        """
        if self.environment.lower() == "production":
            if self.jwt_secret == "quickbite-development-only-secret-change-me":
                raise ValueError("jwt_secret must be set to a real value in production")
            unsafe = {
                "demo_payment_mode": self.demo_payment_mode,
                "demo_restaurant_mode": self.demo_restaurant_mode,
                "demo_delivery_mode": self.demo_delivery_mode,
                "demo_notification_mode": self.demo_notification_mode,
                "demo_crash_mode": self.demo_crash_mode,
                "dispatcher_crash_mode": self.dispatcher_crash_mode,
            }
            bad = [
                k
                for k, v in unsafe.items()
                if (v != "success" and k != "demo_crash_mode" and k != "dispatcher_crash_mode")
                or (k in ("demo_crash_mode", "dispatcher_crash_mode") and v != "none")
            ]
            if bad:
                raise ValueError(
                    "failure injection is not allowed in production: " + ", ".join(bad)
                )
        # retry delays validated eagerly
        _ = self.retry_delays


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    return settings


settings = get_settings()
