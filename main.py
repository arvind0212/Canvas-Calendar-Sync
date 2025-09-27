#!/usr/bin/env python3

import logging
import sys
from datetime import datetime

from config import Config
from sync_engine import SyncEngine

def setup_logging():
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("="*60)
    logger.info(f"Canvas Calendar Sync started at {datetime.now().isoformat()}")
    logger.info("="*60)

    try:
        Config.validate()
        logger.info("Configuration validated successfully")

        sync_engine = SyncEngine()
        result = sync_engine.sync()

        logger.info("="*60)
        logger.info("SYNC SUMMARY:")
        logger.info(f"  Events created: {result['created']}")
        logger.info(f"  Events updated: {result['updated']}")
        logger.info(f"  Errors encountered: {result['errors']}")
        logger.info("="*60)

        if result['errors'] > 0:
            logger.warning(f"Sync completed with {result['errors']} errors. Check logs for details.")
            sys.exit(1)
        else:
            logger.info("Sync completed successfully!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        logger.exception("Full error details:")
        sys.exit(1)

if __name__ == "__main__":
    main()