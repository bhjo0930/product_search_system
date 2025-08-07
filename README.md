# Product Search System

A Google Cloud-based product embedding and similarity search system that uses Google's Gemini embedding models for intelligent product discovery.

## 🎯 Overview

This system implements multi-modal product search using embeddings from both text descriptions and product images. It supports two storage backends:

- **Google Firestore**: Vector search with automatic collection creation
- **Vertex AI Matching Engine**: Dedicated vector database with separate text/image indexes
- **Web Application**: Flask-based interface for product management and search

## 🏗️ Architecture

### Core Components

```
product_search_system/
├── embedding_firestore.py    # Firestore-based embedding system
├── embedding_vertex.py       # Vertex AI Matching Engine system
├── web_app/                  # Flask web application
├── product_batch_processor/  # Batch processing tools with Firecrawl integration
└── docs/                     # Documentation
```

### Data Flow

1. **Product Import** → CSV/Web interface → Text & image extraction
2. **Embedding Generation** → Gemini models → Vector representations
3. **Storage** → Firestore/Vertex AI → Indexed for search
4. **Search** → Query embedding → Similarity matching → Ranked results

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Google Cloud Project with APIs enabled:
  - Vertex AI API
  - Firestore API
  - Cloud Storage API
- Google Cloud credentials configured

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository>
   cd product_search_system
   ```

2. **Install dependencies**:
   ```bash
   pip install pandas google-cloud-aiplatform google-cloud-firestore python-dotenv vertexai flask
   ```

3. **Configure environment**:
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

### Environment Configuration

Create `.env` file with required variables:

```bash
# Google Cloud Configuration (Required)
PROJECT_ID="your-google-cloud-project-id"
LOCATION="asia-northeast3"
GCS_BUCKET="your-gcs-bucket-name"

# Flask Security (Required for web app)
SECRET_KEY="your-secure-random-secret-key"

# Google Custom Search (Optional - for web search features)
GOOGLE_API_KEY="your-google-api-key"
CUSTOM_SEARCH_ENGINE_ID="your-search-engine-id"

# Firecrawl API (Optional - for enhanced web scraping)
FIRECRAWL_API_KEY="your-firecrawl-api-key"

# Storage Configuration (Optional - defaults provided)
FIRESTORE_DATABASE="firestore"
FIRESTORE_COLLECTION="products"
LOG_LEVEL="INFO"
```

## 📋 Usage

### Basic Embedding Operations

**Firestore approach** (Recommended for development):
```bash
python embedding_firestore.py
```

**Vertex AI approach** (For production scale):
```bash
python embedding_vertex.py
```

### Web Application

```bash
cd web_app
python app.py
```

Access at `http://localhost:5000`

### Batch Processing

```bash
cd product_batch_processor
python main.py
```

## 🔧 Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PROJECT_ID` | Google Cloud Project ID | `"my-project-123"` |
| `GCS_BUCKET` | Cloud Storage bucket for images | `"my-bucket-images"` |
| `SECRET_KEY` | Flask session security key | `"random-secure-key-here"` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCATION` | `"asia-northeast3"` | Google Cloud region |
| `FIRESTORE_DATABASE` | `"firestore"` | Firestore database name |
| `FIRESTORE_COLLECTION` | `"products"` | Collection for product data |
| `LOG_LEVEL` | `"INFO"` | Logging verbosity |
| `GOOGLE_API_KEY` | `""` | For Google Custom Search |
| `CUSTOM_SEARCH_ENGINE_ID` | `""` | Search engine configuration |
| `FIRECRAWL_API_KEY` | `""` | Web scraping enhancement |

### Usage in Code

The system uses these environment variables across different modules:

```python
# Core Google Cloud settings (used in all modules)
PROJECT_ID = os.getenv("PROJECT_ID")  # Required
LOCATION = os.getenv("LOCATION", "asia-northeast3")  # Has default
GCS_BUCKET = os.getenv("GCS_BUCKET")  # Required for image storage

# Flask security (web_app/app.py)
app.secret_key = os.getenv('SECRET_KEY', 'dev-key-change-in-production')

# Optional features
google_api_key = os.getenv('GOOGLE_API_KEY')  # Web search features
firecrawl_key = os.getenv("FIRECRAWL_API_KEY")  # Enhanced scraping
```

## 🏢 Project Structure

```
product_search_system/
├── README.md                 # This file
├── CLAUDE.md                 # AI assistant guidance
├── .env.template            # Environment template
├── .gitignore              # Git ignore patterns
│
├── docs/                   # Documentation
│   ├── SETUP.md           # Detailed setup guide
│   ├── API.md             # API documentation
│   └── DEPLOYMENT.md      # Deployment guide
│
├── web_app/               # Flask web application
│   ├── app.py            # Main Flask application
│   ├── templates/        # HTML templates
│   └── static/          # CSS, JS, images
│
├── product_batch_processor/  # Batch processing tools
│   ├── config/              # Configuration
│   ├── modules/             # Processing modules
│   └── docs/               # Processor documentation
│
├── embedding_firestore.py   # Firestore embedding system
├── embedding_vertex.py      # Vertex AI system
├── test_similarity_search.py # Testing utilities
└── data/                    # Sample data and tests
```

## 🔍 Features

### Multi-Modal Search
- **Text embeddings**: Product descriptions, specifications
- **Image embeddings**: Product photos, visual features
- **Fusion search**: Combined text+image ranking using RRF

### Flexible Storage
- **Firestore**: Easy setup, automatic scaling
- **Vertex AI**: High performance, production ready

### Web Interface
- Product catalog management
- Real-time search interface
- Batch import capabilities
- Visual similarity browsing

### Batch Processing
- CSV import/export
- Web scraping with Firecrawl
- Automated embedding generation
- Data validation and cleanup

## 📚 Documentation

- [Detailed Setup Guide](docs/SETUP.md)
- [API Documentation](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Batch Processor Guide](product_batch_processor/docs/README.md)

## 🔒 Security

- Environment variables for all sensitive data
- `.env` files excluded from version control
- Secure Flask session management
- Google Cloud IAM integration

## 🤝 Contributing

1. Copy `.env.template` to `.env`
2. Configure your Google Cloud credentials
3. Install development dependencies
4. Run tests before submitting changes

## 📄 License

This project is configured for internal/educational use. Update license as needed for your specific use case.