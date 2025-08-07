import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

# Load environment variables - try local .env first, then parent directory
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
local_env = os.path.join(current_dir, '.env')
parent_env = os.path.join(os.path.dirname(current_dir), '.env')

# Load local .env first (higher priority)
load_dotenv(local_env)
# Load parent .env as fallback
load_dotenv(parent_env)

@dataclass
class Config:
    """Configuration settings for the product batch processor."""
    
    # Google Cloud Settings
    PROJECT_ID: str = os.getenv("PROJECT_ID", "")
    LOCATION: str = os.getenv("LOCATION", "asia-northeast3")
    GCS_BUCKET: str = os.getenv("GCS_BUCKET", "")
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "firestore")
    FIRESTORE_COLLECTION: str = os.getenv("FIRESTORE_COLLECTION", "products")
    
    # Crawling Settings
    USER_AGENT: str = "ProductBatchProcessor/1.0"
    REQUEST_TIMEOUT: int = 30
    REQUEST_DELAY: float = 1.0
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 2.0
    
    # Firecrawl Settings
    FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")
    FIRECRAWL_TIMEOUT: int = 60
    FIRECRAWL_WAIT_FOR: int = 5000  # milliseconds to wait for dynamic content
    FIRECRAWL_BLOCK_ADS: bool = True
    FIRECRAWL_MOBILE: bool = False
    FIRECRAWL_SCREENSHOT: bool = False
    FIRECRAWL_INCLUDE_TAGS: List[str] = None
    FIRECRAWL_EXCLUDE_TAGS: List[str] = None
    FIRECRAWL_ACTIONS_ENABLED: bool = True
    
    # Image Processing Settings
    MAX_IMAGE_SIZE: int = 5 * 1024 * 1024  # 5MB
    SUPPORTED_FORMATS: List[str] = None
    CONVERT_TO_JPG: bool = True
    JPG_QUALITY: int = 90
    MAX_IMAGE_WIDTH: int = 1920
    MAX_IMAGE_HEIGHT: int = 1920
    
    # Batch Processing Settings
    MAX_WORKERS: int = 5
    BATCH_SIZE: int = 100
    ENABLE_ASYNC: bool = True
    
    # File System Settings
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    TEMP_DIR: str = os.path.join(DATA_DIR, "temp")
    HTML_DIR: str = os.path.join(DATA_DIR, "html")
    JSON_DIR: str = os.path.join(DATA_DIR, "json")
    IMAGES_DIR: str = os.path.join(DATA_DIR, "images")
    LOGS_DIR: str = os.path.join(DATA_DIR, "logs")
    
    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "json"  # json or text
    LOG_ROTATION: str = "midnight"
    LOG_RETENTION: int = 30  # days
    LOG_MAX_SIZE: str = "100MB"
    
    # Embedding Settings (기존 시스템과 동일)
    TEXT_EMBEDDING_MODEL: str = "gemini-embedding-001"
    TEXT_EMBEDDING_DIMENSION: int = 1536  # 기존 시스템과 동일
    IMAGE_EMBEDDING_MODEL: str = "multimodalembedding"
    IMAGE_EMBEDDING_DIMENSION: int = 1408  # 기존 시스템과 동일
    
    # AI Processing Settings
    EXTRACTION_MODEL: str = "gemini-2.5-flash"
    MAX_EXTRACTION_TOKENS: int = 8192
    EXTRACTION_TEMPERATURE: float = 0.1
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        if self.SUPPORTED_FORMATS is None:
            self.SUPPORTED_FORMATS = ["jpg", "jpeg", "png", "webp", "gif"]
        
        # Set default Firecrawl tags if not specified
        if self.FIRECRAWL_INCLUDE_TAGS is None:
            self.FIRECRAWL_INCLUDE_TAGS = ["main", "article", "section", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "img", "meta"]
        
        if self.FIRECRAWL_EXCLUDE_TAGS is None:
            self.FIRECRAWL_EXCLUDE_TAGS = ["script", "style", "nav", "footer", "aside", "advertisement", "banner"]
        
        # Validate required settings
        if not self.PROJECT_ID:
            raise ValueError("PROJECT_ID must be set in environment variables")
        
        if not self.GCS_BUCKET:
            raise ValueError("GCS_BUCKET must be set in environment variables")
        
        # Create directories if they don't exist
        for directory in [self.DATA_DIR, self.TEMP_DIR, self.HTML_DIR, 
                         self.JSON_DIR, self.IMAGES_DIR, self.LOGS_DIR]:
            os.makedirs(directory, exist_ok=True)
    
    def get_file_path(self, file_type: str, product_id: str, extension: str = None) -> str:
        """Generate file path based on type and product ID."""
        type_dirs = {
            "html": self.HTML_DIR,
            "json": self.JSON_DIR,
            "image": self.IMAGES_DIR,
            "temp": self.TEMP_DIR
        }
        
        if file_type not in type_dirs:
            raise ValueError(f"Unknown file type: {file_type}")
        
        base_dir = type_dirs[file_type]
        
        if extension:
            filename = f"{product_id}.{extension}"
        else:
            filename = product_id
        
        return os.path.join(base_dir, filename)
    
    def get_gcs_path(self, file_type: str, filename: str) -> str:
        """Generate GCS path for file."""
        return f"{file_type}s/{filename}"

# Global configuration instance
config = Config()