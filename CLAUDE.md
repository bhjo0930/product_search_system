# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Google Cloud-based product embedding and similarity search system that uses Google's Gemini embedding models. The project implements two approaches for storing and searching product embeddings: Google Cloud Vertex AI Matching Engine and Google Firestore with vector search capabilities.

## Architecture

### Core Components

- **embedding_vertex.py**: Implements product embedding generation and similarity search using Google Cloud Vertex AI Matching Engine
  - Uses separate text and image indexes for multi-modal search
  - Implements Reciprocal Rank Fusion (RRF) to combine text and image search results
  - Hardcoded project configuration for Vertex AI resources

- **embedding_firestore.py**: Implements the same functionality using Google Firestore as the vector database
  - Uses environment variables for configuration (loaded from .env file)
  - Stores both text and image embeddings in a single Firestore collection
  - Supports optional image search (text-only search is also possible)

### Data Flow

1. **Data Processing**: Both scripts read product data from CSV files that contain file paths to local text and image files
2. **Embedding Generation**: 
   - Text embeddings using "gemini-embedding-001" model (3,072 dimensions for Vertex AI, 768 for Firestore)
   - Image embeddings using "multimodalembedding" model (1,408 dimensions)
3. **Storage**: Embeddings are stored in either Vertex AI Matching Engine indexes or Firestore collections
4. **Search**: Query text/images are embedded and searched against stored embeddings using vector similarity

## Development Setup

### Prerequisites

- Python 3.12+ (project uses Python 3.12.4)
- Google Cloud Project with appropriate APIs enabled:
  - Vertex AI API
  - Firestore API (for Firestore approach)
  - Cloud Storage API
- Google Cloud credentials configured

### Environment Configuration

Create a `.env` file with:
```
PROJECT_ID="your-google-cloud-project-id"
LOCATION="asia-northeast3"
```

### Dependencies

Install required Python packages:
```bash
pip install pandas google-cloud-aiplatform google-cloud-firestore python-dotenv vertexai
```

## Running the Code

### Vertex AI Approach (embedding_vertex.py)

```bash
python embedding_vertex.py
```

This script will:
1. Process products from `products_data.csv`
2. Generate embeddings and store them in pre-configured Vertex AI Matching Engine indexes
3. Run a sample similarity search with fusion results

### Firestore Approach (embedding_firestore.py)

```bash
python embedding_firestore.py
```

This script will:
1. Process products from `products_data_local.csv`
2. Generate embeddings and store them in Firestore
3. Run two sample searches: text+image and text-only

## Key Differences Between Approaches

- **Configuration**: Vertex AI version uses hardcoded values; Firestore version uses environment variables
- **Storage**: Vertex AI uses separate indexes for text/image; Firestore stores both in single collection
- **Search**: Vertex AI requires both text and image for fusion search; Firestore supports optional image search
- **Embedding Dimensions**: Text embeddings differ between implementations (3,072 vs 768 dimensions)

## Data Files

- `products_data.csv`: Used by Vertex AI approach - contains local file paths for text/image data
- `products_data_local.csv`: Used by Firestore approach - CSV with product metadata and file paths
- `.env`: Environment configuration for Firestore approach

## Important Notes

- Both scripts expect local text and image files referenced in the CSV data
- The Vertex AI approach requires pre-created Matching Engine indexes with specific IDs
- Firestore approach creates the collection automatically
- Search functionality demonstrates multi-modal similarity search with text and image inputs