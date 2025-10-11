import os
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

class Config:
    CANVAS_CONFIGS = {
        'kth': {
            'name': 'KTH',
            'base_url': 'https://canvas.kth.se',
            'access_token': os.getenv('KTH_CANVAS_TOKEN')
        },
        'ki': {
            'name': 'KI',
            'base_url': 'https://ki.instructure.com',
            'access_token': os.getenv('KI_CANVAS_TOKEN')
        }
    }

    GOOGLE_CALENDAR_ID = 'arvindguruprasad33@gmail.com'
    SYNC_WEEKS_AHEAD = 12

    GOOGLE_SERVICE_ACCOUNT_FILE = 'service-account.json'
    GOOGLE_CREDENTIALS_FILE = 'credentials.json'
    GOOGLE_TOKEN_FILE = 'token.json'

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'sync.log')

    @classmethod
    def validate(cls) -> bool:
        missing_tokens = []

        for university, config in cls.CANVAS_CONFIGS.items():
            if not config['access_token']:
                missing_tokens.append(f"{university.upper()}_CANVAS_TOKEN")

        if missing_tokens:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_tokens)}")

        return True

    @classmethod
    def get_canvas_config(cls, university: str) -> Dict[str, Any]:
        if university not in cls.CANVAS_CONFIGS:
            raise ValueError(f"Unknown university: {university}")

        return cls.CANVAS_CONFIGS[university]