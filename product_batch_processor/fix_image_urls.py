#!/usr/bin/env python3
"""
Fix existing Firestore documents to use full GCS URLs instead of relative paths
"""

import os
from google.cloud import firestore
from dotenv import load_dotenv

def fix_image_urls():
    """Update existing documents to use full GCS URLs"""
    
    # Load environment
    load_dotenv()
    
    project_id = os.getenv('PROJECT_ID')
    gcs_bucket = os.getenv('GCS_BUCKET', 'ferrous-amphora-466402-i9-product-images')
    
    # Initialize Firestore
    db = firestore.Client(project=project_id, database='firestore')
    
    # Collections to check
    collections = ['products', 'firestore', 'local_batch_products']
    
    total_updated = 0
    
    for collection_name in collections:
        print(f"\n📊 Processing collection: {collection_name}")
        
        try:
            docs = db.collection(collection_name).stream()
            collection_updated = 0
            
            for doc in docs:
                data = doc.to_dict()
                image_path = data.get('image_path', '')
                
                # Check if needs updating
                needs_update = False
                new_image_path = image_path
                
                if image_path and not image_path.startswith('https://'):
                    if image_path.startswith('/static/images/'):
                        # Remove /static/images/ prefix and add full GCS URL
                        filename = image_path.replace('/static/images/', '')
                        new_image_path = f"https://storage.googleapis.com/{gcs_bucket}/images/{filename}"
                        needs_update = True
                    elif image_path.startswith('images/'):
                        # Add full GCS URL prefix
                        new_image_path = f"https://storage.googleapis.com/{gcs_bucket}/{image_path}"
                        needs_update = True
                
                if needs_update:
                    # Update document
                    doc.reference.update({'image_path': new_image_path})
                    print(f"   ✅ Updated {doc.id}")
                    print(f"      Old: {image_path}")
                    print(f"      New: {new_image_path}")
                    collection_updated += 1
            
            print(f"   📈 Updated {collection_updated} documents in {collection_name}")
            total_updated += collection_updated
            
        except Exception as e:
            print(f"   ❌ Error processing {collection_name}: {e}")
    
    print(f"\n🎉 COMPLETED: Updated {total_updated} documents total")
    print("✅ All images should now display properly in web_app")

if __name__ == "__main__":
    fix_image_urls()