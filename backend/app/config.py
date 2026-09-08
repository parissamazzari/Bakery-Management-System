import os


class Settings:
    # Database
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "bakery")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "bakery_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "bakery_pass")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    PRODUCT_CACHE_TTL_SECONDS: int = int(os.getenv("PRODUCT_CACHE_TTL_SECONDS", "30"))

    # RabbitMQ
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "bakery")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "bakery_pass")
    ORDER_QUEUE_NAME: str = os.getenv("ORDER_QUEUE_NAME", "order_processing")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
