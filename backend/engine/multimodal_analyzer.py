"""
멀티모달 퓨전 분석기
- 파일명(텍스트) + 이미지(시각 정보) 동시 분석
- Llama-3.2-Vision via MLX (Apple Silicon 최적화)
"""

import os
from collections import Counter

# MLX VLM 로드
try:
    from mlx_vlm import load, generate
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.utils import load_config
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    print("⚠️ mlx-vlm 사용 불가 - pip install mlx-vlm 필요")

# 전역 모델 (한번만 로드)
_model = None
_processor = None
_config = None
MODEL_PATH = "mlx-community/Llama-3.2-11B-Vision-Instruct-4bit"


def load_model():
    """Llama-3.2-Vision 모델 로드 (최초 1회, 약 7GB)"""
    global _model, _processor, _config
    
    if not MLX_AVAILABLE:
        return None, None, None
    
    if _model is None:
        print("🔄 Llama-3.2-Vision 모델 로딩 중... (최초 1회, ~7GB)")
        _model, _processor = load(MODEL_PATH)
        _config = load_config(MODEL_PATH)
        print("✅ Llama-3.2-Vision 로드 완료 (Apple Silicon MLX)")
    
    return _model, _processor, _config


def analyze_multimodal(file_path: str) -> dict:
    """
    멀티모달 분석: 파일명 + 이미지 동시 분석
    """
    if not MLX_AVAILABLE:
        return {"error": "mlx-vlm 미설치"}
    
    try:
        model, processor, config = load_model()
        if model is None:
            return {"error": "모델 로드 실패"}
        
        filename = os.path.basename(file_path)
        
        # 멀티모달 프롬프트 (파일명 + 이미지 동시 분석)
        prompt = f"""Analyze this image and filename "{filename}".
Identify: 1) Category (상품/배너/스크린샷/라벨/문서/사진/기타), 2) Brand name, 3) Brief description.
Format your answer as:
카테고리: [Korean category]
브랜드: [brand or 없음]
설명: [Korean description]"""

        # 채팅 템플릿 적용
        formatted_prompt = apply_chat_template(processor, config, prompt, num_images=1)
        
        # 이미지 분석
        result = generate(model, processor, formatted_prompt, image=file_path, max_tokens=150, verbose=False)
        
        # 결과 파싱 (한글/영어 모두 지원)
        output_text = result.text if hasattr(result, 'text') else str(result)
        output_lower = output_text.lower()
        
        parsed = {
            "category": "기타",
            "brand": "",
            "folder_name": "",
            "description": output_text[:100],
            "raw_output": output_text
        }
        
        # 카테고리 감지 (영어/한글)
        category_map = {
            "advertisement": "배너", "banner": "배너", "promotion": "배너", "sale": "배너",
            "product": "상품", "clothing": "상품", "fashion": "상품", "shoes": "상품",
            "screenshot": "스크린샷", "screen": "스크린샷", "capture": "스크린샷",
            "label": "라벨", "tag": "라벨", "care": "라벨",
            "document": "문서", "contract": "문서", "paper": "문서",
            "photo": "사진", "portrait": "사진", "person": "사진"
        }
        
        for eng, kor in category_map.items():
            if eng in output_lower:
                parsed["category"] = kor
                break
        
        # 브랜드 감지 (대문자 단어 찾기)
        import re
        brand_patterns = re.findall(r'\b([A-Z][A-Z\-]+(?:\s*[A-Z]+)?)\b', output_text)
        # 일반적인 단어 제외
        exclude = {'THE', 'AND', 'FOR', 'WITH', 'IMAGE', 'TEXT', 'HERE', 'KOREAN'}
        brands = [b for b in brand_patterns if b not in exclude and len(b) >= 2]
        if brands:
            parsed["brand"] = brands[0].replace(' ', '-')
        
        # 폴더명 생성
        if parsed["brand"]:
            parsed["folder_name"] = f"{parsed['brand']}_{parsed['category']}"
        else:
            parsed["folder_name"] = parsed["category"]
        
        return parsed
        
    except Exception as e:
        print(f"멀티모달 분석 오류: {e}")
        return {"error": str(e)}


def analyze_session_representative(session_files: list, sample_size: int = 3) -> dict:
    """
    세션의 대표 이미지만 분석 (속도 최적화)
    """
    if not session_files:
        return {"error": "파일 없음"}
    
    # 대표 이미지 선정 (파일명 길이 + 파일 크기)
    scored_files = []
    for f in session_files:
        path = f['path'] if isinstance(f, dict) else f
        filename = os.path.basename(path)
        try:
            size = os.path.getsize(path)
            score = len(filename) + (size / 100000)
            scored_files.append((path, score))
        except:
            scored_files.append((path, len(filename)))
    
    # 상위 N개 선정
    scored_files.sort(key=lambda x: -x[1])
    representatives = [f[0] for f in scored_files[:sample_size]]
    
    # 대표 이미지 분석
    results = []
    for path in representatives:
        result = analyze_multimodal(path)
        if "error" not in result:
            results.append(result)
    
    if not results:
        return {"error": "분석 실패"}
    
    # 결과 집계
    brands = [r.get("brand", "") for r in results if r.get("brand")]
    categories = [r.get("category", "") for r in results if r.get("category")]
    
    final_brand = Counter(brands).most_common(1)[0][0] if brands else ""
    final_category = Counter(categories).most_common(1)[0][0] if categories else "기타"
    
    return {
        "brand": final_brand,
        "category": final_category,
        "folder_name": f"{final_brand}_{final_category}" if final_brand else final_category,
        "samples_analyzed": len(results),
        "confidence": len(results) / sample_size
    }


# 테스트
if __name__ == "__main__":
    print("=== 멀티모달 분석기 테스트 ===")
    print(f"MLX VLM 사용 가능: {MLX_AVAILABLE}")
    
    if MLX_AVAILABLE:
        test_file = os.environ.get("LAZYSORT_TEST_FILE", "samples/banner.jpg")
        
        if os.path.exists(test_file):
            print(f"\n테스트 파일: {os.path.basename(test_file)}")
            result = analyze_multimodal(test_file)
            print(f"카테고리: {result.get('category')}")
            print(f"브랜드: {result.get('brand')}")
            print(f"폴더명: {result.get('folder_name')}")
            print(f"설명: {result.get('description')}")
