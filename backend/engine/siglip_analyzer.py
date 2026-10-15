"""
Google SigLIP을 사용한 초고속 이미지 분류
공식 가이드: https://huggingface.co/docs/transformers/ko/model_doc/siglip
"""

import torch
from PIL import Image
from transformers import AutoProcessor, AutoModel
import os

# 전역 모델 (한번만 로드)
_model = None
_processor = None

# 카테고리 라벨
CATEGORIES = {
    "상품": "clothing product, fashion item, shirt, jacket, pants, shoes",
    "배너": "advertising banner, promotion, sale, marketing image",
    "스크린샷": "screenshot, screen capture, mobile phone screen",
    "라벨": "care label, product tag, size chart, clothing label",
    "문서": "document, contract, paper, invoice, receipt",
    "사진": "photograph, portrait, selfie, person",
    "기타": "other, miscellaneous"
}


def load_model():
    """SigLIP 모델 로드 (최초 1회만)"""
    global _model, _processor
    
    if _model is None:
        print("🔄 SigLIP 모델 로딩 중... (최초 1회)")
        
        model_name = "google/siglip-base-patch16-224"
        
        _model = AutoModel.from_pretrained(model_name)
        _processor = AutoProcessor.from_pretrained(model_name)
        
        # GPU/MPS 사용
        if torch.backends.mps.is_available():
            _model = _model.to("mps")
            print("✅ SigLIP 모델 로드 완료 (Apple Silicon)")
        elif torch.cuda.is_available():
            _model = _model.to("cuda")
            print("✅ SigLIP 모델 로드 완료 (GPU)")
        else:
            print("✅ SigLIP 모델 로드 완료 (CPU)")
        
        _model.eval()
    
    return _model, _processor


def analyze_image_siglip(image_path: str) -> dict:
    """
    SigLIP으로 이미지 분류 (직접 모델 사용)
    """
    try:
        model, processor = load_model()
        device = next(model.parameters()).device
        
        # 이미지 로드
        image = Image.open(image_path).convert("RGB")
        
        # 프롬프트 템플릿 적용 (필수!)
        texts = [f"This is a photo of {desc}." for desc in CATEGORIES.values()]
        
        # 전처리 (padding="max_length" 필수!)
        inputs = processor(
            text=texts,
            images=image,
            padding="max_length",
            return_tensors="pt"
        ).to(device)
        
        # 추론
        with torch.no_grad():
            outputs = model(**inputs)
        
        # SigLIP은 sigmoid 사용 (softmax 아님!)
        logits_per_image = outputs.logits_per_image
        probs = torch.sigmoid(logits_per_image)[0].cpu().numpy()
        
        # 카테고리별 점수
        category_names = list(CATEGORIES.keys())
        all_scores = {cat: float(prob) for cat, prob in zip(category_names, probs)}
        
        # 최고 점수 카테고리
        best_idx = probs.argmax()
        best_category = category_names[best_idx]
        confidence = float(probs[best_idx])
        
        return {
            "category": best_category,
            "confidence": round(confidence, 3),
            "all_scores": {k: round(v, 3) for k, v in all_scores.items()}
        }
        
    except Exception as e:
        print(f"SigLIP 분석 오류: {e}")
        return {"category": "기타", "confidence": 0.0, "all_scores": {}}


def analyze_images_batch_siglip(image_paths: list[str]) -> dict:
    """
    여러 이미지를 배치로 분류
    """
    results = {}
    
    try:
        model, processor = load_model()
        device = next(model.parameters()).device
        
        # 이미지 로드
        images = []
        valid_paths = []
        for path in image_paths:
            try:
                img = Image.open(path).convert("RGB")
                images.append(img)
                valid_paths.append(path)
            except Exception as e:
                print(f"이미지 로드 실패: {path}")
                results[path] = {"category": "기타", "confidence": 0.0}
        
        if not images:
            return results
        
        # 프롬프트 템플릿
        texts = [f"This is a photo of {desc}." for desc in CATEGORIES.values()]
        category_names = list(CATEGORIES.keys())
        
        # 배치 처리
        for path, image in zip(valid_paths, images):
            inputs = processor(
                text=texts,
                images=image,
                padding="max_length",
                return_tensors="pt"
            ).to(device)
            
            with torch.no_grad():
                outputs = model(**inputs)
            
            probs = torch.sigmoid(outputs.logits_per_image)[0].cpu().numpy()
            
            best_idx = probs.argmax()
            results[path] = {
                "category": category_names[best_idx],
                "confidence": round(float(probs[best_idx]), 3)
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
    
    # 테스트 이미지
    test_images = []
    for f in os.listdir(test_dir):
        if f.endswith(('.jpg', '.jpeg', '.png')):
            test_images.append(os.path.join(test_dir, f))
            if len(test_images) >= 10:
                break
    
    print(f"\n🧪 테스트: {len(test_images)}개 이미지")
    
    # 모델 로드
    load_model()
    
    # 분석
    start = time.time()
    results = analyze_images_batch_siglip(test_images)
    elapsed = time.time() - start
    
    print(f"\n⏱️ 소요 시간: {elapsed:.2f}초")
    print(f"📊 초당 처리: {len(test_images)/elapsed:.1f}개/초")
    
    # 결과
    cats = {}
    print("\n📋 상세 결과:")
    for path, r in list(results.items())[:5]:
        cat = r['category']
        conf = r['confidence']
        cats[cat] = cats.get(cat, 0) + 1
        print(f"  {os.path.basename(path)[:35]:35} → {cat} ({conf:.0%})")
    
    print("\n📊 카테고리 집계:")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}개")
