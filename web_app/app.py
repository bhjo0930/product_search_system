import os
import uuid
import numpy as np
import base64
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from dotenv import load_dotenv
from google.cloud import aiplatform, firestore, storage
from vertexai.language_models import TextEmbeddingModel
from vertexai.vision_models import MultiModalEmbeddingModel
from vertexai.generative_models import GenerativeModel, Part, Image as VertexAIImage
from PIL import Image
import io
import json

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-key-change-in-production')  # 환경 변수에서 로드

# Google Cloud 설정
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION", "asia-northeast3")
GCS_BUCKET = os.getenv("GCS_BUCKET")
FIRESTORE_COLLECTION = "firestore"
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# 업로드 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 제한

# 초기화
aiplatform.init(project=PROJECT_ID, location=LOCATION)
db = firestore.Client(project=PROJECT_ID, database='firestore')
storage_client = storage.Client(project=PROJECT_ID)
bucket = storage_client.bucket(GCS_BUCKET)
text_embedding_model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
multimodal_embedding_model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")

# Gemini 2.5 Flash 모델 초기화 (이미지 분석용)
import vertexai
vertexai.init(project=PROJECT_ID, location=LOCATION)
multimodal_model = GenerativeModel("gemini-2.5-flash")

# Gemini 2.5 Flash 모델 초기화 (검색어 생성용) - 안정적이고 성능이 좋은 모델
search_query_model = GenerativeModel("gemini-2.5-flash")

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_gcs(file, filename):
    """파일을 GCS에 업로드하고 공개 URL을 반환합니다."""
    try:
        # GCS blob 생성
        blob = bucket.blob(f"products/{filename}")
        
        # 파일 업로드
        file.seek(0)  # 파일 포인터를 처음으로 되돌림
        blob.upload_from_file(file, content_type=file.content_type)
        
        # 파일을 공개로 설정
        blob.make_public()
        
        # 공개 URL 반환
        return blob.public_url
        
    except Exception as e:
        print(f"GCS 업로드 오류: {e}")
        return None

def download_from_gcs(gcs_url, local_path):
    """GCS URL에서 파일을 다운로드하여 로컬에 임시 저장합니다."""
    try:
        # GCS URL에서 blob 이름 추출
        if gcs_url.startswith('https://storage.googleapis.com/'):
            # URL에서 버킷명과 파일명 추출
            url_parts = gcs_url.replace('https://storage.googleapis.com/', '').split('/', 1)
            if len(url_parts) == 2:
                bucket_name, blob_name = url_parts
                blob = storage_client.bucket(bucket_name).blob(blob_name)
                blob.download_to_filename(local_path)
                return True
        return False
    except Exception as e:
        print(f"GCS 다운로드 오류: {e}")
        return False

def get_text_embedding(text: str):
    """텍스트로부터 임베딩을 생성합니다 (1536차원)."""
    if not text: 
        return []
    try:
        embeddings = text_embedding_model.get_embeddings([text], output_dimensionality=1536)
        return embeddings[0].values
    except Exception as e:
        print(f"텍스트 임베딩 생성 오류: {e}")
        return []

def get_image_embedding(image_path: str):
    """이미지로부터 임베딩을 생성합니다 (1408차원)."""
    if not image_path:
        return []
    
    try:
        image_bytes = None
        
        # GCS URL인지 확인
        if image_path.startswith('https://storage.googleapis.com/'):
            # GCS에서 이미지 데이터 다운로드
            url_parts = image_path.replace('https://storage.googleapis.com/', '').split('/', 1)
            if len(url_parts) == 2:
                bucket_name, blob_name = url_parts
                blob = storage_client.bucket(bucket_name).blob(blob_name)
                image_bytes = blob.download_as_bytes()
        else:
            # 로컬 파일 경로인 경우
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
        
        if not image_bytes:
            return [0.0] * 1408
        
        # Vertex AI Image 객체로 변환
        from vertexai.preview.vision_models import Image as VertexImage
        vertex_image = VertexImage(image_bytes)
        
        # MultiModalEmbeddingModel을 사용하여 이미지 임베딩 생성 (1408차원)
        embeddings = multimodal_embedding_model.get_embeddings(
            image=vertex_image,
            dimension=1408
        )
        return embeddings.image_embedding
    except Exception as e:
        print(f"이미지 임베딩 생성 오류: {e}")
        # 대안: 빈 리스트 대신 1408차원의 0벡터 반환
        return [0.0] * 1408

def get_multimodal_embeddings(text: str = None, image_path: str = None):
    """텍스트와 이미지 임베딩을 각각 생성하여 반환합니다."""
    try:
        text_embedding = []
        image_embedding = []
        
        # 텍스트 임베딩 생성 (1536차원)
        if text:
            text_embedding = get_text_embedding(text)
        
        # 이미지 임베딩 생성 (1408차원)
        if image_path:
            image_embedding = get_image_embedding(image_path)
        
        return {
            'text_embedding': text_embedding,
            'image_embedding': image_embedding
        }
            
    except Exception as e:
        print(f"멀티모달 임베딩 생성 오류: {e}")
        return {
            'text_embedding': [],
            'image_embedding': []
        }

def cosine_similarity(vec1, vec2):
    """코사인 유사도 계산"""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    # 벡터의 노름이 0인 경우 처리
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return np.dot(vec1, vec2) / (norm1 * norm2)

def analyze_product_image(image_path: str):
    """이미지를 분석하여 상품 정보를 추출합니다."""
    if not image_path:
        return None
    
    try:
        image_bytes = None
        
        # GCS URL인지 로컬 파일인지 확인
        if image_path.startswith('https://storage.googleapis.com/'):
            # GCS에서 이미지 데이터 다운로드
            url_parts = image_path.replace('https://storage.googleapis.com/', '').split('/', 1)
            if len(url_parts) == 2:
                bucket_name, blob_name = url_parts
                blob = storage_client.bucket(bucket_name).blob(blob_name)
                image_bytes = blob.download_as_bytes()
        else:
            # 로컬 파일인 경우
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
        
        if not image_bytes:
            return None
        
        # Vertex AI Image 객체 생성
        image = VertexAIImage.from_bytes(image_bytes)
        
        # 프롬프트 정의
        prompt_text = """
이 이미지를 바탕으로 상품 정보를 추출하여 다음 형식으로 답변해주세요.

상품명: [추정되는 상품명]
카테고리: [의류/가전/식품/기타]
색상: [주요 색상]
소재/재질: [추정되는 소재나 재질]
주요 특징: [눈에 띄는 특징들을 나열]
용도/기능: [상품의 주요 용도나 기능]
스타일: [디자인 스타일이나 분위기]
브랜드: [식별 가능한 브랜드나 로고]
크기/규격: [추정되는 크기나 규격]
기타 정보: [추가로 확인되는 정보]

각 항목별로 간단명료하게 작성하고, 확인이 어려운 항목은 '확인불가'로 표시해주세요.
상품 설명문 형태가 아닌 정보 추출 형태로 답변해주세요.
        """
        
        # 이미지 분석 요청
        response = multimodal_model.generate_content([image, prompt_text])
        
        return response.text.strip()
        
    except Exception as e:
        print(f"이미지 분석 오류: {e}")
        return None

def generate_search_query(product_info: str):
    """상품 정보로부터 Google Custom Search용 검색어를 생성합니다."""
    if not product_info:
        return ""
    
    try:
        prompt_text = f"""
다음 상품 정보를 바탕으로 Google 검색에서 유사한 상품을 찾기 위한 최적의 검색어를 생성해주세요.

상품 정보:
{product_info}

요구사항:
1. 상품의 핵심 특징을 포함한 간결한 검색어 생성
2. 브랜드명이 있다면 포함
3. 카테고리와 주요 특징을 조합
4. 불필요한 단어는 제거하고 검색에 효과적인 키워드만 선별
5. 한국어로 작성하되, 영어 브랜드명은 그대로 유지
6. 검색어는 한 줄로 작성 (최대 10개 단어)

검색어만 답변해주세요.
        """
        
        response = search_query_model.generate_content(prompt_text)
        return response.text.strip()
        
    except Exception as e:
        print(f"검색어 생성 오류: {e}")
        return ""

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/products')
def products():
    """상품 목록 페이지"""
    try:
        # 정렬 옵션 받기
        sort_by = request.args.get('sort', 'created_at')  # 기본: 등록일
        order = request.args.get('order', 'desc')  # 기본: 내림차순
        
        collection_ref = db.collection(FIRESTORE_COLLECTION)
        docs = list(collection_ref.stream())
        
        products = []
        for doc in docs:
            doc_data = doc.to_dict()
            products.append({
                'id': doc.id,
                'content': doc_data.get('text_content', ''),
                'image_path': doc_data.get('image_path', ''),
                'created_at': doc_data.get('created_at', ''),
                'preview': doc_data.get('text_content', '')[:200] + "..." if len(doc_data.get('text_content', '')) > 200 else doc_data.get('text_content', '')
            })
        
        # 정렬 적용
        if sort_by == 'created_at':
            products.sort(key=lambda x: x['created_at'] or '', reverse=(order == 'desc'))
        elif sort_by == 'name':
            products.sort(key=lambda x: x['content'][:50].lower(), reverse=(order == 'desc'))
        elif sort_by == 'id':
            products.sort(key=lambda x: x['id'], reverse=(order == 'desc'))
        
        return render_template('products.html', products=products, sort_by=sort_by, order=order)
    except Exception as e:
        flash(f'Error loading products: {str(e)}', 'error')
        return render_template('products.html', products=[], sort_by='created_at', order='desc')

@app.route('/search', methods=['GET', 'POST'])
def search():
    """검색 페이지"""
    if request.method == 'POST':
        query_text = request.form.get('query_text', '').strip()
        search_type = request.form.get('search_type', 'text')  # text, image, multimodal
        
        if not query_text and search_type != 'image':
            flash('Please enter search text.', 'warning')
            return render_template('search.html', results=[])
        
        try:
            query_embedding = []
            
            # 검색 타입에 따른 임베딩 생성
            if search_type == 'text':
                query_embedding = get_text_embedding(query_text)
            elif search_type == 'image':
                # 이미지 검색의 경우 업로드된 이미지 처리
                if 'search_image' in request.files:
                    file = request.files['search_image']
                    if file and file.filename != '' and allowed_file(file.filename):
                        # 임시 파일로 저장
                        temp_filename = f"temp_search_{uuid.uuid4().hex[:8]}.{file.filename.rsplit('.', 1)[1].lower()}"
                        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                        file.save(temp_path)
                        
                        try:
                            query_embedding = get_image_embedding(temp_path)
                        finally:
                            # 임시 파일 삭제
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                    else:
                        flash('Please upload a valid image file.', 'warning')
                        return render_template('search.html', results=[])
                else:
                    flash('Please upload an image for image search.', 'warning')
                    return render_template('search.html', results=[])
            elif search_type == 'multimodal':
                # 텍스트 + 이미지 검색
                image_path = None
                if 'search_image' in request.files:
                    file = request.files['search_image']
                    if file and file.filename != '' and allowed_file(file.filename):
                        temp_filename = f"temp_search_{uuid.uuid4().hex[:8]}.{file.filename.rsplit('.', 1)[1].lower()}"
                        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
                        file.save(temp_path)
                        image_path = temp_path
                
                try:
                    # 텍스트와 이미지 임베딩을 각각 생성
                    query_embeddings = get_multimodal_embeddings(text=query_text if query_text else None, image_path=image_path)
                    query_text_embedding = query_embeddings['text_embedding']
                    query_image_embedding = query_embeddings['image_embedding']
                    
                    # 검색 가능한 임베딩이 없는 경우 오류 처리
                    if not query_text_embedding and not query_image_embedding:
                        flash('Error processing search query.', 'error')
                        return render_template('search.html', results=[])
                        
                finally:
                    # 임시 파일 삭제
                    if image_path and os.path.exists(image_path):
                        os.remove(image_path)
            
            # 단일 모드 검색에 대한 오류 처리
            if search_type in ['text', 'image'] and not query_embedding:
                flash('Error processing search query.', 'error')
                return render_template('search.html', results=[])
            
            # 모든 문서 가져오기
            collection_ref = db.collection(FIRESTORE_COLLECTION)
            all_docs = list(collection_ref.stream())
            
            # 각 문서와의 유사도 계산
            similarities = []
            for doc in all_docs:
                doc_data = doc.to_dict()
                
                if search_type == 'text':
                    # 텍스트 검색: 텍스트 임베딩만 사용
                    if not query_embedding:
                        continue
                    product_text_embedding = doc_data.get('text_embedding', [])
                    if product_text_embedding:
                        similarity = cosine_similarity(query_embedding, product_text_embedding)
                    else:
                        similarity = 0.0
                
                elif search_type == 'image':
                    # 이미지 검색: 이미지 임베딩만 사용
                    if not query_embedding:
                        continue
                    product_image_embedding = doc_data.get('image_embedding', [])
                    if product_image_embedding:
                        similarity = cosine_similarity(query_embedding, product_image_embedding)
                    else:
                        similarity = 0.0
                
                elif search_type == 'multimodal':
                    # 멀티모달 검색: 텍스트와 이미지 유사도를 결합
                    text_similarity = 0.0
                    image_similarity = 0.0
                    
                    # 텍스트 유사도 계산
                    if query_text_embedding:
                        product_text_embedding = doc_data.get('text_embedding', [])
                        if product_text_embedding:
                            text_similarity = cosine_similarity(query_text_embedding, product_text_embedding)
                    
                    # 이미지 유사도 계산
                    if query_image_embedding:
                        product_image_embedding = doc_data.get('image_embedding', [])
                        if product_image_embedding:
                            image_similarity = cosine_similarity(query_image_embedding, product_image_embedding)
                    
                    # 가중평균으로 최종 유사도 계산 (텍스트 70%, 이미지 30%)
                    if query_text_embedding and query_image_embedding:
                        similarity = (text_similarity * 0.7) + (image_similarity * 0.3)
                    elif query_text_embedding:
                        similarity = text_similarity
                    elif query_image_embedding:
                        similarity = image_similarity
                    else:
                        similarity = 0.0
                else:
                    similarity = 0.0
                
                similarities.append({
                    'product_id': doc.id,
                    'similarity': similarity,
                    'text_content': doc_data.get('text_content', ''),
                    'image_path': doc_data.get('image_path', ''),
                    'created_at': doc_data.get('created_at', '')
                })
            
            # 유사도 순으로 정렬
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            # 상위 10개 결과만 반환
            results = similarities[:10]
            
            return render_template('search.html', results=results, query=query_text, search_type=search_type)
            
        except Exception as e:
            flash(f'Search error: {str(e)}', 'error')
            return render_template('search.html', results=[])
    
    return render_template('search.html', results=[])

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    """상품 등록 페이지"""
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        
        if not content:
            flash('Product information is required.', 'warning')
            return render_template('add_product.html')
        
        try:
            # 고유 ID 생성
            product_id = f"P{str(uuid.uuid4())[:8].upper()}"
            image_path = ''
            
            # 이미지 파일 처리
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # 고유한 파일명 생성
                    file_extension = filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"{product_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
                    
                    # GCS에 업로드
                    gcs_url = upload_to_gcs(file, unique_filename)
                    if gcs_url:
                        image_path = gcs_url
                    else:
                        flash('Image upload failed.', 'error')
                        return render_template('add_product.html')
            
            # 텍스트와 이미지 임베딩 각각 생성
            embeddings = get_multimodal_embeddings(text=content, image_path=image_path)
            
            if not embeddings['text_embedding']:
                flash('Error generating text embeddings.', 'error')
                return render_template('add_product.html')
            
            # Firestore에 저장
            product_data = {
                'product_id': product_id,
                'text_content': content,
                'text_embedding': embeddings['text_embedding'],  # 텍스트 임베딩 (1536차원)
                'image_embedding': embeddings['image_embedding'],  # 이미지 임베딩 (1408차원)
                'image_path': image_path,
                'created_at': datetime.now().isoformat()
            }
            
            doc_ref = db.collection(FIRESTORE_COLLECTION).document(product_id)
            doc_ref.set(product_data)
            
            flash('Product successfully registered!', 'success')
            return redirect(url_for('products'))
            
        except Exception as e:
            flash(f'Error registering product: {str(e)}', 'error')
            return render_template('add_product.html')
    
    return render_template('add_product.html')

@app.route('/product/<product_id>')
def product_detail(product_id):
    """상품 상세 페이지"""
    try:
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(product_id)
        doc = doc_ref.get()
        
        if doc.exists:
            product_data = doc.to_dict()
            return render_template('product_detail.html', product=product_data, product_id=product_id)
        else:
            flash('상품을 찾을 수 없습니다.', 'error')
            return redirect(url_for('products'))
            
    except Exception as e:
        flash(f'상품 정보를 가져오는 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/edit/<product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """상품 수정"""
    try:
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(product_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            flash('상품을 찾을 수 없습니다.', 'error')
            return redirect(url_for('products'))
        
        product_data = doc.to_dict()
        
        if request.method == 'POST':
            content = request.form.get('content', '').strip()
            
            if not content:
                flash('상품 정보는 필수입니다.', 'warning')
                return render_template('edit_product.html', product=product_data, product_id=product_id)
            
            # 기존 이미지 경로 유지
            image_path = product_data.get('image_path', '')
            
            # 새 이미지가 업로드된 경우
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '' and allowed_file(file.filename):
                    # 기존 GCS 이미지 삭제 (필요시)
                    if image_path and image_path.startswith('https://storage.googleapis.com/'):
                        try:
                            url_parts = image_path.replace('https://storage.googleapis.com/', '').split('/', 1)
                            if len(url_parts) == 2:
                                bucket_name, blob_name = url_parts
                                blob = storage_client.bucket(bucket_name).blob(blob_name)
                                if blob.exists():
                                    blob.delete()
                        except Exception as e:
                            print(f"기존 GCS 이미지 삭제 오류: {e}")
                    
                    # 새 이미지 GCS에 업로드
                    filename = secure_filename(file.filename)
                    file_extension = filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"{product_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
                    
                    gcs_url = upload_to_gcs(file, unique_filename)
                    if gcs_url:
                        image_path = gcs_url
                    else:
                        flash('이미지 업로드에 실패했습니다.', 'error')
                        return render_template('edit_product.html', product=product_data, product_id=product_id)
            
            # 새 임베딩 생성
            embeddings = get_multimodal_embeddings(text=content, image_path=image_path)
            
            if not embeddings['text_embedding']:
                flash('텍스트 임베딩 생성 중 오류가 발생했습니다.', 'error')
                return render_template('edit_product.html', product=product_data, product_id=product_id)
            
            # Firestore 업데이트
            updated_data = {
                'text_content': content,
                'text_embedding': embeddings['text_embedding'],  # 텍스트 임베딩 (1536차원)
                'image_embedding': embeddings['image_embedding'],  # 이미지 임베딩 (1408차원)
                'image_path': image_path,
                'updated_at': datetime.now().isoformat()
            }
            
            doc_ref.update(updated_data)
            
            flash('상품이 성공적으로 수정되었습니다!', 'success')
            return redirect(url_for('product_detail', product_id=product_id))
        
        return render_template('edit_product.html', product=product_data, product_id=product_id)
        
    except Exception as e:
        flash(f'상품 수정 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/delete/<product_id>', methods=['POST'])
def delete_product(product_id):
    """상품 삭제"""
    try:
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(product_id)
        doc_ref.delete()
        flash('상품이 삭제되었습니다.', 'success')
    except Exception as e:
        flash(f'상품 삭제 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('products'))

@app.route('/analyze_image', methods=['POST'])
def analyze_image():
    """업로드된 이미지를 분석하여 상품 정보를 반환합니다."""
    try:
        if 'image' not in request.files:
            return jsonify({'error': '이미지 파일이 없습니다.'}), 400
        
        file = request.files['image']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': '유효하지 않은 이미지 파일입니다.'}), 400
        
        # 임시 파일로 저장
        temp_filename = f"temp_analyze_{uuid.uuid4().hex[:8]}.{file.filename.rsplit('.', 1)[1].lower()}"
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        file.save(temp_path)
        
        try:
            # 이미지 분석 수행
            analysis_result = analyze_product_image(temp_path)
            
            if analysis_result:
                return jsonify({
                    'success': True,
                    'analysis': analysis_result
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '이미지 분석에 실패했습니다.'
                }), 500
                
        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/external_search/<product_id>')
def external_search(product_id):
    """상품 정보를 바탕으로 Google Custom Search를 실행합니다."""
    try:
        # 환경 변수 확인
        google_api_key = os.getenv('GOOGLE_API_KEY')
        custom_search_engine_id = os.getenv('CUSTOM_SEARCH_ENGINE_ID')
        
        if not google_api_key or not custom_search_engine_id:
            return jsonify({
                'success': False,
                'error': 'Google Custom Search API 설정이 필요합니다.',
                'setup_guide': [
                    '1. Google Cloud Console에서 Custom Search API를 활성화하세요.',
                    '2. API 키를 생성하고 GOOGLE_API_KEY 환경변수에 설정하세요.',
                    '3. Custom Search Engine을 생성하고 ID를 CUSTOM_SEARCH_ENGINE_ID 환경변수에 설정하세요.'
                ]
            }), 500
        
        # 상품 정보 가져오기
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(product_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({
                'success': False,
                'error': '상품을 찾을 수 없습니다.'
            }), 404
        
        product_data = doc.to_dict()
        product_info = product_data.get('text_content', '')
        
        if not product_info:
            return jsonify({
                'success': False,
                'error': '상품 정보가 없습니다.'
            }), 400
        
        # AI로 검색어 생성
        search_query = generate_search_query(product_info)
        
        if not search_query:
            return jsonify({
                'success': False,
                'error': '검색어 생성에 실패했습니다.'
            }), 500
        
        # Google Custom Search API 호출
        import requests
        search_url = f"https://www.googleapis.com/customsearch/v1"
        params = {
            'key': google_api_key,
            'cx': custom_search_engine_id,
            'q': search_query,
            'num': 10  # 최대 10개 결과
        }
        
        response = requests.get(search_url, params=params, timeout=10)
        
        if not response.ok:
            error_data = response.json() if response.content else {}
            return jsonify({
                'success': False,
                'error': f'Google Search API 오류: {response.status_code}',
                'details': error_data.get('error', {}).get('message', '알 수 없는 오류')
            }), response.status_code
        
        search_results = response.json()
        
        # 검색 결과 정리
        results = []
        if 'items' in search_results:
            for item in search_results['items']:
                results.append({
                    'title': item.get('title', 'No title'),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', 'No description available'),
                    'displayLink': item.get('displayLink', ''),
                    'formattedUrl': item.get('formattedUrl', item.get('link', ''))
                })
        
        return jsonify({
            'success': True,
            'query': search_query,
            'results': results,
            'total': len(results)
        })
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': '검색 요청 시간이 초과되었습니다.'
        }), 408
    
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'네트워크 오류: {str(e)}'
        }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'외부 검색 중 오류가 발생했습니다: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
