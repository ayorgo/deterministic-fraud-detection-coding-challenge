import environ

env = environ.Env()

# Application settings
PROXIMITY_METERS = env.int("PROXIMITY_METERS", default=200)
SUSPECTED_TTL_SECONDS = env.int("SUSPECTED_TTL_SECONDS", default=60 * 60 * 24)
ACCEPTED_TTL_SECONDS = env.int("ACCEPTED_TTL_SECONDS", default=60 * 60 * 2)
FRAUD_SCORE_THRESHOLD = env.float("FRAUD_SCORE_THRESHOLD", default=0.25)
DEBUG = env.bool("DEBUG", default=False)

# Cache settings
REDIS_PORT = env.int("REDIS_PORT", default=6379)
REDIS_HOST = env.str("REDIS_HOST", default="localhost")
