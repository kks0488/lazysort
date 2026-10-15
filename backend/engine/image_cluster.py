"""
이미지 유사도 클러스터링 + 브랜드 인식
- MobileCLIP 임베딩으로 비슷한 이미지 그룹화
- Apple Vision OCR로 브랜드명 추출
"""

import os
import numpy as np
from PIL import Image
from collections import Counter

# Apple Vision OCR
try:
    import Vision
    from Foundation import NSURL
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

# MobileCLIP
try:
    import torch
    import open_clip
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False

# 전역 모델
_model = None
_preprocess = None
_tokenizer = None

# 알려진 브랜드명
KNOWN_BRANDS = [
    "K-SWISS", "KSWISS", "케이스위스",
    "NIKE", "나이키",
    "ADIDAS", "아디다스", 
    "AGATHA", "아가타",
    "ZARA", "H&M", "UNIQLO", "유니클로",
    "SAMSUNG", "삼성", "LG", "APPLE"
]


def load_clip_model():
    """MobileCLIP 모델 로드"""
    global _model, _preprocess, _tokenizer
    
    if _model is None and CLIP_AVAILABLE:
        print("🔄 MobileCLIP 로딩...")
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            'ViT-B-32', pretrained='openai'
        )
        _model.eval()
        print("✅ MobileCLIP 로드 완료")
    
    return _model, _preprocess


def get_image_embedding(image_path: str) -> np.ndarray:
    """이미지 임베딩 벡터 추출"""
    model, preprocess = load_clip_model()
    
    if model is None:
        return None
    
    try:
        image = preprocess(Image.open(image_path).convert('RGB')).unsqueeze(0)
        with torch.no_grad():
            embedding = model.encode_image(image)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        return embedding.numpy().flatten()
    except Exception as e:
        print(f"임베딩 오류: {e}")
        return None


def cluster_by_similarity(image_paths: list, threshold: float = 0.85) -> dict:
    """
    이미지 유사도로 클러스터링
    
    Args:
        image_paths: 이미지 경로 리스트
        threshold: 유사도 임계값 (0.85 = 85% 이상 유사하면 같은 그룹)
    
    Returns:
        {0: [이미지1, 이미지2], 1: [이미지3], ...}
    """
    if not CLIP_AVAILABLE:
        return {0: image_paths}
    
    print(f"🔍 {len(image_paths)}개 이미지 임베딩 추출 중...")
    
    # 임베딩 추출
    embeddings = []
    valid_paths = []
    
    for path in image_paths:
        emb = get_image_embedding(path)
        if emb is not None:
            embeddings.append(emb)
            valid_paths.append(path)
    
    if not embeddings:
        return {0: image_paths}
    
    embeddings = np.array(embeddings)
    
    # 유사도 행렬 계산
    similarity = np.dot(embeddings, embeddings.T)
    
    # 클러스터링 (Union-Find)
    n = len(valid_paths)
    parent = list(range(n))
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    # 유사도 높은 쌍 병합
    for i in range(n):
        for j in range(i + 1, n):
            if similarity[i][j] >= threshold:
                union(i, j)
    
    # 클러스터 생성
    clusters = {}
    for i, path in enumerate(valid_paths):
        cluster_id = find(i)
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(path)
    
    # 클러스터 ID 재정렬
    result = {}
    for idx, (_, paths) in enumerate(sorted(clusters.items(), key=lambda x: -len(x[1]))):
        result[idx] = paths
    
    print(f"✅ {len(result)}개 클러스터 생성")
    return result


def detect_brand_ocr(image_path: str) -> str:
    """Apple Vision OCR로 브랜드명 추출"""
    if not VISION_AVAILABLE:
        return ""
    
    try:
        image_url = NSURL.fileURLWithPath_(image_path)
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(["en", "ko"])
        
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(image_url, None)
        handler.performRequests_error_([request], None)
        
        results = request.results()
        
        for observation in results:
            if observation.confidence() > 0.5:
                text = observation.topCandidates_(1)[0].string().upper()
                # 브랜드명 매칭
                for brand in KNOWN_BRANDS:
                    if brand.upper() in text:
                        return brand.upper().replace("케이스위스", "K-SWISS").replace("나이키", "NIKE")
        
        return ""
    except:
        return ""


def analyze_cluster_brand(cluster_paths: list) -> str:
    """
    클러스터의 대표 브랜드명 추출
    
    핵심: 클러스터 내 하나의 파일에서 브랜드를 찾으면
          같은 클러스터의 "제목없음" 같은 파일도 그 브랜드로 분류
    """
    brands = []
    
    # 1. 파일명에서 브랜드 추출 (가장 신뢰도 높음)
    for path in cluster_paths:
        filename = os.path.basename(path).upper()
        for brand in KNOWN_BRANDS:
            if brand.upper() in filename:
                normalized = brand.upper().replace("케이스위스", "K-SWISS").replace("나이키", "NIKE").replace("아디다스", "ADIDAS").replace("아가타", "AGATHA")
                brands.append(normalized)
    
    # 2. OCR로 이미지에서 브랜드 추출 (파일명에 없을 때)
    if not brands:
        samples = cluster_paths[:5]  # 최대 5개
        for path in samples:
            brand = detect_brand_ocr(path)
            if brand:
                brands.append(brand)
    
    # 가장 많이 나온 브랜드 반환
    if brands:
        return Counter(brands).most_common(1)[0][0]
    return ""


def propagate_brand_to_cluster(clusters: dict) -> dict:
    """
    클러스터 내 브랜드 전파
    
    예: 클러스터 [케이스위스_상품.jpg, 제목없음.png, IMG_1234.jpg]
        → 모두 "K-SWISS" 브랜드로 분류
    """
    result = {}
    
    for cluster_id, paths in clusters.items():
        brand = analyze_cluster_brand(paths)
        
        # 각 파일에 브랜드 할당
        for path in paths:
            result[path] = {
                "cluster_id": cluster_id,
                "brand": brand,
                "cluster_size": len(paths)
            }
    
    return result


def smart_cluster_organize(folder_path: str, threshold: float = 0.85) -> dict:
    """
    스마트 클러스터 정리
    
    Returns:
        {
            "clusters": [
                {"id": 0, "brand": "K-SWISS", "count": 15, "files": [...]},
                ...
            ]
        }
    """
    # 이미지 파일 수집
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    
    image_paths = []
    for root, dirs, files in os.walk(folder_path):
        # _정리됨 폴더 제외
        if '_정리됨' in root:
            continue
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                image_paths.append(os.path.join(root, f))
    
    if not image_paths:
        return {"clusters": [], "total_files": 0}
    
    # 클러스터링
    clusters = cluster_by_similarity(image_paths, threshold)
    
    # 각 클러스터 분석
    result = {"clusters": [], "total_files": len(image_paths)}
    
    for cluster_id, paths in clusters.items():
        brand = analyze_cluster_brand(paths)
        
        result["clusters"].append({
            "id": cluster_id,
            "brand": brand or f"그룹{cluster_id}",
            "count": len(paths),
            "files": [os.path.basename(p) for p in paths],
            "sample": paths[0] if paths else ""
        })
    
    return result


# 테스트
if __name__ == "__main__":
    print("=== 이미지 클러스터링 테스트 ===")
    print(f"CLIP 사용 가능: {CLIP_AVAILABLE}")
    print(f"Vision OCR 사용 가능: {VISION_AVAILABLE}")
    print()
    
    test_folder = os.environ.get("LAZYSORT_TEST_DIR", "samples")
    
    if os.path.exists(test_folder):
        result = smart_cluster_organize(test_folder, threshold=0.80)
        
        print(f"총 {result['total_files']}개 파일")
        print()
        
        for cluster in result["clusters"][:5]:
            print(f"📂 클러스터 {cluster['id']}: {cluster['brand']} ({cluster['count']}개)")
            print(f"   샘플: {cluster['files'][:3]}")
            print()

