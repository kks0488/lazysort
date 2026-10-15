"""
Apple MobileCLIP2를 사용한 초고속 이미지 분류
Apple Silicon 최적화! CLIP보다 13배 빠름!
https://github.com/apple/ml-mobileclip
"""

import torch
from PIL import Image
import mobileclip
import os

MODEL_DIR = os.environ.get("LAZYSORT_MODEL_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models"))

# 전역 모델 (한번만 로드)
_model = None
_preprocess = None
_tokenizer = None

# 카테고리 라벨
CATEGORIES = {
    "상품": "a photo of clothing product, fashion item, shirt jacket pants shoes",
    "배너": "a photo of advertising banner, promotion sale marketing",
    "스크린샷": "a photo of screenshot, screen capture, mobile phone screen",
    "라벨": "a photo of care label, product tag, size chart",
    "문서": "a photo of document, contract paper invoice",
    "사진": "a photo of person, portrait selfie people",
    "기타": "a photo of something"
}


def load_model():
    """MobileCLIP2 모델 로드 (최초 1회만)"""
    global _model, _preprocess, _tokenizer
    
    if _model is None:
        print("🔄 MobileCLIP2-S0 모델 로딩 중... (최초 1회)")
        
        # MobileCLIP2-S0 (가장 빠름!)
        _model, _, _preprocess = mobileclip.create_model_and_transforms(
            'mobileclip_s0', 
            pretrained=os.path.join(MODEL_DIR, 'mobileclip_s0.pt')
        )
        _tokenizer = mobileclip.get_tokenizer('mobileclip_s0')
        
        # Apple Silicon 사용
        if torch.backends.mps.is_available():
            _model = _model.to("mps")
            print("✅ MobileCLIP2-S0 로드 완료 (Apple Silicon)")
        elif torch.cuda.is_available():
            _model = _model.to("cuda")
            print("✅ MobileCLIP2-S0 로드 완료 (GPU)")
        else:
            print("✅ MobileCLIP2-S0 로드 완료 (CPU)")
        
        _model.eval()
    
    return _model, _preprocess, _tokenizer


def download_model_if_needed():
    """모델 파일이 없으면 다운로드"""
    model_dir = MODEL_DIR
    model_path = os.path.join(model_dir, "mobileclip_s0.pt")
    
    if not os.path.exists(model_path):
        os.makedirs(model_dir, exist_ok=True)
        print("📥 MobileCLIP2-S0 모델 다운로드 중...")
        
        # Hugging Face에서 다운로드
        from huggingface_hub import hf_hub_download
        hf_hub_download(
            repo_id="apple/MobileCLIP-S0",
            filename="mobileclip_s0.pt",
            local_dir=model_dir
        )
        print("✅ 모델 다운로드 완료!")
    
    return model_path


def analyze_image_mobileclip(image_path: str) -> dict:
    """
    MobileCLIP2로 이미지 분류
    """
    try:
        model, preprocess, tokenizer = load_model()
        device = next(model.parameters()).device
        
        # 이미지 로드 및 전처리
        image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
        
        # 텍스트 토큰화
        texts = list(CATEGORIES.values())
        text_tokens = tokenizer(texts).to(device)
        
        # 추론
        with torch.no_grad():
            image_features = model.encode_image(image)
            text_features = model.encode_text(text_tokens)
            
            # 정규화
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            
            # 유사도 계산
            probs = (100.0 * image_features @ text_features.T).softmax(dim=-1)[0]
        
        # 결과
        category_names = list(CATEGORIES.keys())
        all_scores = {cat: float(prob) for cat, prob in zip(category_names, probs.cpu().numpy())}
        
        best_idx = probs.argmax().item()
        best_category = category_names[best_idx]
        confidence = float(probs[best_idx])
        
        return {
            "category": best_category,
            "confidence": round(confidence, 3),
            "all_scores": {k: round(v, 3) for k, v in all_scores.items()}
        }
        
    except Exception as e:
        print(f"MobileCLIP 분석 오류: {e}")
        return {"category": "기타", "confidence": 0.0, "all_scores": {}}


def analyze_images_batch_mobileclip(image_paths: list[str]) -> dict:
    """
    여러 이미지를 배치로 분류 (MobileCLIP2)
    """
    results = {}
    
    try:
        model, preprocess, tokenizer = load_model()
        device = next(model.parameters()).device
        
        # 텍스트 인코딩 (한번만)
        texts = list(CATEGORIES.values())
        text_tokens = tokenizer(texts).to(device)
        
        with torch.no_grad():
            text_features = model.encode_text(text_tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)
        
        category_names = list(CATEGORIES.keys())
        
        # 이미지 배치 처리
        for path in image_paths:
            try:
                image = preprocess(Image.open(path).convert("RGB")).unsqueeze(0).to(device)
                
                with torch.no_grad():
                    image_features = model.encode_image(image)
                    image_features /= image_features.norm(dim=-1, keepdim=True)
                    probs = (100.0 * image_features @ text_features.T).softmax(dim=-1)[0]
                
                best_idx = probs.argmax().item()
                results[path] = {
                    "category": category_names[best_idx],
                    "confidence": round(float(probs[best_idx]), 3)
                }
            except Exception as e:
                print(f"이미지 분석 실패: {os.path.basename(path)}")
                results[path] = {"category": "기타", "confidence": 0.0}
        
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
    
    # 모델 다운로드 확인
    download_model_if_needed()
    
    test_dir = os.environ.get("LAZYSORT_TEST_DIR", "samples")
    
    # 테스트 이미지
    test_images = []
    for f in os.listdir(test_dir):
        if f.endswith(('.jpg', '.jpeg', '.png')):
            test_images.append(os.path.join(test_dir, f))
            if len(test_images) >= 50:
                break
    
    print(f"\n🧪 테스트: {len(test_images)}개 이미지")
    
    # 모델 로드
    load_model()
    
    # 분석
    start = time.time()
    results = analyze_images_batch_mobileclip(test_images)
    elapsed = time.time() - start
    
    print(f"\n⏱️ 소요 시간: {elapsed:.2f}초")
    print(f"📊 초당 처리: {len(test_images)/elapsed:.1f}개/초")
    
    # 결과
    cats = {}
    for r in results.values():
        c = r['category']
        cats[c] = cats.get(c, 0) + 1
    
    print("\n📋 카테고리 집계:")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}개")

