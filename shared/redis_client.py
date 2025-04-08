import redis
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )
