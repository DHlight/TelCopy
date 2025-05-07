import logging
import time
from sqlalchemy.orm import Session

logger = logging.getLogger("db_utils")

def commit_with_retry(db: Session, retries: int = 5, base_delay: float = 0.1):
    """
    Commit the database session with retries on "database is locked" errors using exponential backoff.
    """
    for attempt in range(retries):
        try:
            db.commit()
            return
        except Exception as e:
            if "database is locked" in str(e).lower():
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Database is locked, retrying commit in {delay:.2f} seconds (attempt {attempt + 1}/{retries})")
                time.sleep(delay)
            else:
                raise
    # Final attempt without catching exception
    db.commit()
