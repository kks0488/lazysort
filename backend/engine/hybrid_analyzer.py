"""
하이브리드 분석기 (가벼운 버전)
- MobileCLIP2 (이미지 분석) + 파일명 키워드 (텍스트 힌트)
- 무거운 LLM 없이 빠르게 분류
"""

import os
import re

# 파일명에서 카테고리 힌트 추출
# "사진" 카테고리 제거 (모든 이미지가 사진이므로 의미없음)
# "스크린샷"은 실제 스크린샷 패턴만 (PNG라고 무조건 스크린샷 아님)
FILENAME_KEYWORDS = {
    "배너": ["배너", "banner", "광고", "프로모션", "promotion", "sale", "할인", "이벤트", "event", "카드뷰", "timedeal", "smartchannel", "규격", "한파", "창고털이", "11st", "11번가", "쿠팡", "네이버", "gmarket"],
    "상품": ["상품", "product", "누끼", "단독", "상세", "detail", "맨투맨", "자켓", "티셔츠", "상의", "하의", "세트", "슬랙스", "셋업", "shorts", "기모", "후리스", "플리스", "니트"],
    "스크린샷": ["스크린샷", "screenshot", "캡처", "capture", "screen shot"],  # IMG_ 제거 (일반 사진일 수 있음)
    "라벨": ["라벨", "label", "케어라벨", "태그", "tag", "사이즈", "케어"],
    "문서": ["문서", "document", "계약", "contract", "송장", "invoice"]
    # "사진" 카테고리 삭제
}

# 파일명에서 브랜드 힌트 추출
KNOWN_BRANDS = [
    "NIKE", "ADIDAS", "K-SWISS", "케이스위스", "KSWISS",
    "AGATHA", "아가타", "ZARA", "H&M", "UNIQLO", "유니클로",
    "SAMSUNG", "삼성", "APPLE", "애플", "LG"
]


def extract_filename_hints(filename: str) -> dict:
    """
    파일명에서 카테고리/브랜드 힌트 추출
    """
    filename_lower = filename.lower()
    filename_upper = filename.upper()
    
    hints = {
        "category_hint": None,
        "brand_hint": None,
        "keywords": []
    }
    
    # 카테고리 힌트
    for category, keywords in FILENAME_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in filename_lower:
                hints["category_hint"] = category
                break
        if hints["category_hint"]:
            break
    
    # 브랜드 힌트
    for brand in KNOWN_BRANDS:
        if brand.upper() in filename_upper or brand in filename:
            hints["brand_hint"] = brand.upper().replace("케이스위스", "K-SWISS").replace("아가타", "AGATHA")
            break
    
    # 의미있는 키워드 추출 (브랜드명 제외!)
    tokens = re.split(r'[_\-\s\.\(\)\[\]]+', filename)
    
    # 브랜드 관련 단어 제외 리스트
    brand_words = {'k', 'swiss', 'kswiss', 'nike', 'adidas', 'agatha', 'zara', 'uniqlo', 
                   '케이스위스', '나이키', '아디다스', '아가타', '유니클로'}
    exclude = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'img', 'image', 'copy', '복사본', 
               'batch', 'gemini', 'generated'}
    
    for token in tokens:
        token_lower = token.lower()
        if len(token) >= 2 and not token.isdigit():
            if token_lower not in exclude and token_lower not in brand_words:
                hints["keywords"].append(token)
    
    return hints


def hybrid_classify(mobileclip_result: dict, filename: str) -> dict:
    """
    MobileCLIP 결과 + 파일명 힌트 결합
    
    규칙:
    1. 파일명에 카테고리 키워드가 있으면 우선 적용
    2. 없으면 MobileCLIP 결과 사용
    3. 브랜드는 파일명에서 추출 (MobileCLIP은 브랜드 인식 못함)
    """
    hints = extract_filename_hints(filename)
    
    # MobileCLIP 결과
    clip_category = mobileclip_result.get("category", "기타")
    clip_confidence = mobileclip_result.get("confidence", 0)
    
    # 최종 결과
    result = {
        "category": clip_category,
        "brand": hints["brand_hint"] or "",
        "confidence": clip_confidence,
        "source": "mobileclip"
    }
    
    # 파일명에 카테고리 힌트가 있으면 우선 적용
    if hints["category_hint"]:
        result["category"] = hints["category_hint"]
        result["source"] = "filename"
        result["confidence"] = 1.0  # 파일명 힌트는 신뢰도 높음
    
    # MobileCLIP 신뢰도가 낮고 (< 0.5) 파일명에 힌트가 없으면 키워드 기반 추론
    elif clip_confidence < 0.5 and hints["keywords"]:
        # 키워드로 다시 한번 체크
        for kw in hints["keywords"]:
            for category, cat_keywords in FILENAME_KEYWORDS.items():
                if kw.lower() in [k.lower() for k in cat_keywords]:
                    result["category"] = category
                    result["source"] = "keyword"
                    break
    
    return result


# 테스트
if __name__ == "__main__":
    # 테스트 파일명들
    test_filenames = [
        "케이스위스_PC_배너_1920x400.png",
        "batch_여성상품_케어라벨1.jpeg",
        "IMG_6303.PNG",
        "아가타_맨투맨_블랙.jpg",
        "11번가_러시딜_배너.jpg",
        "e7df2abd_05eb_4c80.png"
    ]
    
    print("=== 파일명 힌트 추출 테스트 ===\n")
    
    for filename in test_filenames:
        hints = extract_filename_hints(filename)
        print(f"📂 {filename}")
        print(f"   카테고리 힌트: {hints['category_hint']}")
        print(f"   브랜드 힌트: {hints['brand_hint']}")
        print(f"   키워드: {hints['keywords']}")
        print()

