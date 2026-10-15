"""
파일명 병합 모듈
새 구조: [대분류]_[브랜드]_[상세정보]_[해상도].확장자
예: 상품_케이스위스_맨투맨_블랙_800x800.jpg
"""

def smart_merge_v2(category: str, brand: str, user_tokens: list[str], ai_tags: list[str], specs: list[str], ext: str, max_length: int = 80) -> str:
    """
    새로운 체계적 파일명 생성
    구조: [대분류]_[브랜드]_[상세태그]_[해상도].확장자
    """
    parts = []
    used_words = set()  # 중복 방지
    
    # 1. 대분류 (필수)
    if category:
        parts.append(category)
        used_words.add(category.lower())
    
    # 2. 브랜드 (있으면 추가, 이미 포함되어 있으면 스킵)
    if brand:
        clean_brand = brand.replace(" ", "")
        # 이미 사용된 단어거나, 기존 parts에 브랜드 관련 단어가 있으면 스킵
        brand_variants = {clean_brand.lower(), 'k-swiss', 'kswiss', 'swiss', 'nike', 'adidas', 'agatha'}
        already_has_brand = any(p.lower() in brand_variants for p in parts)
        if clean_brand.lower() not in used_words and not already_has_brand:
            parts.append(clean_brand)
            used_words.add(clean_brand.lower())
            # 브랜드 관련 단어 모두 used에 추가
            used_words.update(brand_variants)
    
    # 3. 사용자 토큰에서 의미있는 것만 추가 (브랜드, 숫자 제외)
    for token in user_tokens:
        clean = token.replace(" ", "_")
        # 순수 숫자, 이미 사용된 단어, 대분류와 같은 단어 제외
        if (clean.lower() not in used_words and 
            not clean.isdigit() and
            len(clean) > 1):
            parts.append(clean)
            used_words.add(clean.lower())
            if len(parts) >= 5:  # 너무 길어지지 않게
                break
    
    # 4. AI 태그 추가 (중복 제외)
    for tag in ai_tags:
        clean = tag.replace(" ", "_")
        if clean.lower() not in used_words and len(clean) > 1:
            parts.append(clean)
            used_words.add(clean.lower())
            if len(parts) >= 6:  # 적정 길이 유지
                break
    
    # 5. 해상도 (항상 마지막)
    if specs:
        parts.extend(specs)
    
    # 조합
    base_name = "_".join(parts)
    full_name = f"{base_name}.{ext}"
    
    # 길이 제한 처리
    if len(full_name) > max_length:
        # AI 태그부터 제거
        while len(full_name) > max_length and len(parts) > 3:
            # 해상도 전 위치에서 제거
            if specs and parts[-1] in specs:
                parts.pop(-2)  # 해상도 앞의 태그 제거
            else:
                parts.pop()
            base_name = "_".join(parts)
            full_name = f"{base_name}.{ext}"
    
    return full_name


def smart_merge(user_tokens: list[str], ai_tags: list[str], specs: list[str], ext: str, max_length: int = 80) -> str:
    """
    기존 API 호환용 - 카테고리 없이 사용
    (새 API에서는 smart_merge_v2 사용 권장)
    """
    return smart_merge_v2("", "", user_tokens, ai_tags, specs, ext, max_length)


# 레거시 함수들 (하위 호환성)
def merge_tokens(user_tokens: list[str], ai_tags: list[str], specs: list[str]) -> str:
    """레거시: 단순 병합"""
    parts = user_tokens + ai_tags + specs
    return "_".join(parts)

def enforce_length_limit(filename: str, max_length: int = 80) -> str:
    """레거시: 길이 제한"""
    return filename[:max_length] if len(filename) > max_length else filename
