"""
로컬 CLIP 모델을 사용한 초고속 이미지 분석
API 호출 없이 로컬에서 즉시 분석!
"""

import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
import os

# 전역 모델 (한번만 로드)
_model = None
_processor = None

# 카테고리 정의 (한글 + 영어 혼합으로 정확도 향상)
CATEGORIES = {
    "상품": ["clothing product photo", "fashion item", "shirt", "jacket", "pants", "shoes", "apparel"],
    "배너": ["advertising banner", "promotion", "sale banner", "marketing image", "discount"],
    "스크린샷": ["screenshot", "screen capture", "mobile screenshot", "computer screen"],
    "라벨": ["care label", "product tag", "clothing label", "size chart"],
    "문서": ["document", "contract", "paper", "invoice", "receipt"],
    "사진": ["photograph", "portrait", "landscape photo", "selfie"],
}

def load_model():
    """CLIP 모델 로드 (최초 1회만)"""
    global _model, _processor
    
    if _model is None:
        print("🔄 CLIP 모델 로딩 중... (최초 1회)")
        _model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        # GPU 사용 가능하면 GPU로
        if torch.cuda.is_available():
            _model = _model.to("cuda")
            print("✅ CLIP 모델 로드 완료 (GPU)")
        elif torch.backends.mps.is_available():
            _model = _model.to("mps")  # Apple Silicon
            print("✅ CLIP 모델 로드 완료 (Apple Silicon)")
        else:
            print("✅ CLIP 모델 로드 완료 (CPU)")
    
    return _model, _processor


def analyze_image_clip(image_path: str) -> dict:
    """
    CLIP으로 이미지 분석하여 카테고리 분류
    
    Returns:
        {
            "category": "상품",
            "confidence": 0.85,
            "all_scores": {"상품": 0.85, "배너": 0.10, ...}
        }
    """
    try:
        model, processor = load_model()
        
        # 이미지 로드 및 리사이즈 (속도 향상)
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((224, 224))  # CLIP 입력 크기
        
        # 모든 카테고리 텍스트 준비
        all_texts = []
        category_mapping = []
        for cat, keywords in CATEGORIES.items():
            for kw in keywords:
                all_texts.append(f"a photo of {kw}")
                category_mapping.append(cat)
        
        # CLIP 추론
        inputs = processor(
            text=all_texts,
            images=image,
            return_tensors="pt",
            padding=True
        )
        
        # GPU로 이동
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits_per_image[0]
            probs = logits.softmax(dim=0).cpu().numpy()
        
        # 카테고리별 최고 점수 집계
        category_scores = {}
        for cat in CATEGORIES.keys():
            category_scores[cat] = 0.0
        
        for i, prob in enumerate(probs):
            cat = category_mapping[i]
            category_scores[cat] = max(category_scores[cat], float(prob))
        
        # 최고 점수 카테고리
        best_category = max(category_scores, key=category_scores.get)
        confidence = category_scores[best_category]
        
        # 신뢰도가 낮으면 "기타"
        if confidence < 0.15:
            best_category = "기타"
        
        return {
            "category": best_category,
            "confidence": round(confidence, 3),
            "all_scores": {k: round(v, 3) for k, v in category_scores.items()}
        }
        
    except Exception as e:
        print(f"CLIP 분석 오류: {e}")
        return {
            "category": "기타",
            "confidence": 0.0,
            "all_scores": {}
        }


def analyze_images_batch(image_paths: list[str]) -> dict:
    """
    여러 이미지를 배치로 분석 (더 빠름!)
    
    Returns:
        {
            "path1.jpg": {"category": "상품", "confidence": 0.85},
            "path2.jpg": {"category": "배너", "confidence": 0.72},
            ...
        }
    """
    results = {}
    
    try:
        model, processor = load_model()
        
        # 이미지 로드
        images = []
        valid_paths = []
        for path in image_paths:
            try:
                img = Image.open(path).convert("RGB")
                img.thumbnail((224, 224))
                images.append(img)
                valid_paths.append(path)
            except Exception as e:
                print(f"이미지 로드 실패: {path} - {e}")
                results[path] = {"category": "기타", "confidence": 0.0}
        
        if not images:
            return results
        
        # 카테고리 텍스트 준비
        all_texts = []
        category_mapping = []
        for cat, keywords in CATEGORIES.items():
            for kw in keywords:
                all_texts.append(f"a photo of {kw}")
                category_mapping.append(cat)
        
        # 배치 처리
        inputs = processor(
            text=all_texts,
            images=images,
            return_tensors="pt",
            padding=True
        )
        
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs_per_image = logits_per_image.softmax(dim=1).cpu().numpy()
        
        # 각 이미지별 결과 집계
        for img_idx, path in enumerate(valid_paths):
            probs = probs_per_image[img_idx]
            
            category_scores = {cat: 0.0 for cat in CATEGORIES.keys()}
            for i, prob in enumerate(probs):
                cat = category_mapping[i]
                category_scores[cat] = max(category_scores[cat], float(prob))
            
            best_category = max(category_scores, key=category_scores.get)
            confidence = category_scores[best_category]
            
            if confidence < 0.15:
                best_category = "기타"
            
            results[path] = {
                "category": best_category,
                "confidence": round(confidence, 3)
            }
        
        return results
        
    except Exception as e:
        print(f"배치 분석 오류: {e}")
        for path in image_paths:
            if path not in results:
                results[path] = {"category": "기타", "confidence": 0.0}
        return results


# 테스트
if __name__ == "__main__":
    import time
    
    test_dir = os.environ.get("LAZYSORT_TEST_DIR", "samples")
    
    # 테스트 이미지 찾기
    test_images = []
    for f in os.listdir(test_dir):
        if f.endswith(('.jpg', '.jpeg', '.png')):
            test_images.append(os.path.join(test_dir, f))
            if len(test_images) >= 10:
                break
    
    print(f"\n🧪 테스트: {len(test_images)}개 이미지")
    
    # 배치 분석 테스트
    start = time.time()
    results = analyze_images_batch(test_images)
    elapsed = time.time() - start
    
    print(f"\n⏱️ 소요 시간: {elapsed:.2f}초 ({len(test_images)}개)")
    print(f"📊 초당 처리: {len(test_images)/elapsed:.1f}개/초")
    
    print("\n📋 결과:")
    for path, result in list(results.items())[:5]:
        print(f"  {os.path.basename(path)[:30]:30} → {result['category']} ({result['confidence']:.0%})")

