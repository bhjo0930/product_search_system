# Detailed Setup Guide

Complete setup instructions for the Product Search System.

## 🔧 System Requirements

### Software Requirements
- **Python**: 3.12 or higher
- **Google Cloud SDK**: Latest version
- **Git**: For version control

### Google Cloud Services
- **Vertex AI API**: For embedding generation and Matching Engine
- **Firestore**: For document storage and vector search
- **Cloud Storage**: For image file storage
- **Cloud IAM**: For service account management

## 📋 Step-by-Step Setup

### 1. Google Cloud Configuration

#### Create Project
```bash
# Create new project
gcloud projects create your-project-id

# Set as default project
gcloud config set project your-project-id

# Enable billing (required)
gcloud billing projects link your-project-id --billing-account=your-billing-account-id
```

#### Enable APIs
```bash
gcloud services enable \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    storage-api.googleapis.com \
    storage-component.googleapis.com \
    compute.googleapis.com
```

#### Setup Authentication
```bash
# For development (interactive)
gcloud auth application-default login

# For production (service account)
gcloud iam service-accounts create product-search-service \
    --display-name="Product Search Service"

# Grant necessary permissions
gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:product-search-service@your-project-id.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:product-search-service@your-project-id.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:product-search-service@your-project-id.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# Create and download key
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=product-search-service@your-project-id.iam.gserviceaccount.com
```

#### Create Cloud Storage Bucket
```bash
# Create bucket for image storage
gsutil mb -l asia-northeast3 gs://your-project-id-product-images

# Set appropriate permissions
gsutil iam ch serviceAccount:product-search-service@your-project-id.iam.gserviceaccount.com:objectAdmin gs://your-project-id-product-images
```

### 2. Environment Setup

#### Clone Repository
```bash
git clone <repository-url>
cd product_search_system
```

#### Python Environment
```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### Environment Configuration
```bash
# Copy template
cp .env.template .env

# Edit with your values
nano .env  # or your preferred editor
```

**Required `.env` configuration**:
```bash
# Google Cloud (Required)
PROJECT_ID="your-project-id"
LOCATION="asia-northeast3"
GCS_BUCKET="your-project-id-product-images"

# Flask Security (Required)
SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

# Firestore (Optional - defaults provided)
FIRESTORE_DATABASE="firestore"
FIRESTORE_COLLECTION="products"

# Logging
LOG_LEVEL="INFO"
```

### 3. Database Setup

#### Firestore Configuration
```bash
# Enable Firestore in Native mode
gcloud firestore databases create --location=asia-northeast3

# Create vector search index (if using vector search)
gcloud alpha firestore indexes composite create \
    --collection-group=products \
    --field-config=field-path=text_embedding,vector-config='{"dimension":768,"flat": {}}' \
    --field-config=field-path=image_embedding,vector-config='{"dimension":1408,"flat": {}}'
```

### 4. Optional Services Setup

#### Google Custom Search (for web search features)
1. Go to [Google Developers Console](https://console.developers.google.com/)
2. Enable Custom Search API
3. Create credentials → API Key
4. Create Custom Search Engine at [cse.google.com](https://cse.google.com/)
5. Add to `.env`:
   ```bash
   GOOGLE_API_KEY="your-api-key"
   CUSTOM_SEARCH_ENGINE_ID="your-search-engine-id"
   ```

#### Firecrawl Setup (for enhanced web scraping)
1. Sign up at [firecrawl.dev](https://www.firecrawl.dev/)
2. Get API key from dashboard
3. Add to `.env`:
   ```bash
   FIRECRAWL_API_KEY="your-firecrawl-api-key"
   ```

### 5. Verification

#### Test Basic Setup
```bash
# Test Google Cloud connection
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
from google.cloud import firestore
db = firestore.Client(project=os.getenv('PROJECT_ID'))
print('✅ Firestore connection successful')
"

# Test Vertex AI connection
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
import vertexai
vertexai.init(project=os.getenv('PROJECT_ID'), location=os.getenv('LOCATION'))
print('✅ Vertex AI connection successful')
"
```

#### Run Tests
```bash
# Test embedding generation
python test_similarity_search.py

# Test web application
cd web_app
python app.py
# Visit http://localhost:5000
```

## 🔍 Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Symptom: "Google Cloud credentials not found"
# Solution: Re-run authentication
gcloud auth application-default login

# Or set service account key
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
```

#### API Not Enabled
```bash
# Symptom: "API not enabled" errors
# Solution: Enable required APIs
gcloud services enable aiplatform.googleapis.com firestore.googleapis.com
```

#### Permission Denied
```bash
# Symptom: Permission denied on Cloud Storage
# Solution: Check IAM roles
gcloud projects get-iam-policy your-project-id
# Add missing roles as shown in step 1
```

#### Firestore Errors
```bash
# Symptom: Firestore not initialized
# Solution: Create database
gcloud firestore databases create --location=asia-northeast3
```

### Environment Variable Issues

**Missing PROJECT_ID**:
```python
# Check if properly loaded
import os
from dotenv import load_dotenv
load_dotenv()
print(f"PROJECT_ID: {os.getenv('PROJECT_ID')}")
```

**Invalid SECRET_KEY**:
```bash
# Generate secure key
python -c "import secrets; print(secrets.token_hex(32))"
# Add to .env file
```

### Performance Issues

**Slow embedding generation**:
- Use Vertex AI Matching Engine for production
- Batch process embeddings
- Use appropriate machine types in Vertex AI

**Memory issues**:
- Process data in smaller batches
- Use streaming for large datasets
- Optimize image sizes before processing

## 📊 Monitoring

### Cloud Monitoring
```bash
# View API usage
gcloud logging read "resource.type=gce_instance AND logName=projects/your-project-id/logs/vertex-ai"

# Monitor costs
gcloud billing budgets list --billing-account=your-billing-account-id
```

### Application Monitoring
- Check logs in `web_app/logs/`
- Monitor Firestore usage in Cloud Console
- Track embedding generation costs

## 🔄 Updates

### Updating Dependencies
```bash
pip install --upgrade -r requirements.txt
```

### Database Migrations
- Firestore is schemaless - no migrations needed
- For major changes, consider data export/import

### API Version Updates
- Monitor Google Cloud API deprecation notices
- Test thoroughly before upgrading Vertex AI models
- Update documentation when APIs change

This setup guide provides comprehensive instructions for getting the Product Search System running in any environment.