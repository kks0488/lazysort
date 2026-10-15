import re
import google.generativeai as genai
import os

# --- IMMUTABLE CONSTANTS ---
API_KEY = os.environ.get("GEMINI_API_KEY", "")  # set in your shell, never commit keys
MODEL_NAME = "gemini-2.5-flash"
# ---------------------------

genai.configure(api_key=API_KEY)

def analyze_filename_with_gemini(filename: str) -> dict:
    """단일 파일명 분석 (배치 함수 사용)"""
    results = analyze_filenames_batch([filename])
    return results.get(filename, {"category": "기타", "brand": "", "keywords": []})


def analyze_filenames_batch(filenames: list[str]) -> dict:
    """
    여러 파일명을 한번에 Gemini로 분석 (API 호출 1번!)
    """
    if not filenames:
        return {}
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        
        # 파일명 리스트 생성
        file_list = "\n".join([f"{i+1}. {fn}" for i, fn in enumerate(filenames)])
        
        prompt = f"""다음 파일명들을 분석해서 각각 카테고리, 브랜드, 키워드를 추출해줘.

파일명 목록:
{file_list}

**카테고리** (하나만 선택):
- 상품: 의류, 신발 등 쇼핑몰 상품 (맨투맨, 자켓, 니트, 폴로, 팬츠 등)
- 배너: 광고 배너, 프로모션 (11번가, 쿠팡, 러시딜, 카드뷰, 타임딜 등)
- 스크린샷: 화면 캡처
- 라벨: 케어라벨, 사이즈표
- 문서: 계약서, 운송장
- 사진: 일반 사진
- 기타: 분류 불가 (해상도만 있는 파일명 등)

**출력 형식** (각 파일마다 정확히 이 형식으로, 번호와 함께):
1|카테고리|브랜드|키워드1,키워드2
2|카테고리|브랜드|키워드1

브랜드가 없으면 빈칸으로."""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # 파싱
        results = {}
        for line in text.split('\n'):
            line = line.strip()
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    try:
                        idx = int(parts[0].strip().rstrip('.')) - 1
                        if 0 <= idx < len(filenames):
                            filename = filenames[idx]
                            cat = parts[1].strip()
                            valid_cats = ['상품', '배너', '스크린샷', '라벨', '문서', '사진', '기타']
                            if cat not in valid_cats:
                                cat = '기타'
                            brand = parts[2].strip() if parts[2].strip() != '없음' else ''
                            keywords = [k.strip().replace(" ", "_") for k in parts[3].split(',') if k.strip() and k.strip() != '없음']
                            
                            results[filename] = {
                                "category": cat,
                                "brand": brand.replace(" ", ""),
                                "keywords": keywords
                            }
                    except (ValueError, IndexError):
                        continue
        
        # 분석 안 된 파일은 정규식으로 폴백
        for fn in filenames:
            if fn not in results:
                tokens = clean_tokens(parse_filename_regex(fn))
                results[fn] = {"category": "기타", "brand": "", "keywords": tokens}
        
        return results
        
    except Exception as e:
        print(f"Error batch analyzing filenames: {e}")
        # 폴백: 모든 파일 정규식으로 처리
        results = {}
        for fn in filenames:
            tokens = clean_tokens(parse_filename_regex(fn))
            results[fn] = {"category": "기타", "brand": "", "keywords": tokens}
        return results

def parse_filename_regex(filename: str) -> list[str]:
    """
    Legacy Regex Parser (Fallback)
    """
    name_without_ext = filename.rsplit('.', 1)[0]
    tokens = re.split(r'[_\-\s\[\]\(\)\.]+', name_without_ext)
    return [t for t in tokens if t]

def clean_tokens(tokens: list[str]) -> list[str]:
    """
    Filters out unwanted tokens based on the Hybrid Naming Engine rules.
    """
    # 1. Garbage Patterns (Case Insensitive)
    GARBAGE_EXACT = {
        'untitled', 'image', 'img', 'dsc', 'screen', 'shot', 'screenshot', 'capture',
        'copy', '사본', 'recovered', 'temp', 'tmp', 'download'
    }
    
    # 2. Prefix Patterns to Drop (e.g., KakaoTalk_..., received_...)
    GARBAGE_PREFIXES = ('kakaotalk', 'received', 'msg', 'clip')
    
    cleaned = []
    for token in tokens:
        lower_token = token.lower()
        
        # A. Exact Match Garbage
        if lower_token in GARBAGE_EXACT:
            continue
            
        # B. Prefix Garbage
        if lower_token.startswith(GARBAGE_PREFIXES):
            continue
            
        # C. Numeric Noise (e.g., "12345" is junk, but "24FW" or "v2" is good)
        # Rule: If it's purely numeric and longer than 4 digits, likely a timestamp/sequence -> Drop?
        # User said "12345.jpg" -> Drop.
        # But "2024" (Year) -> Keep?
        # Let's be conservative: Drop pure numbers > 4 digits. Keep <= 4 (could be Year, Version, Index).
        # Exception: If it looks like a resolution (1000x1000) -> Drop (we add it later).
        if re.match(r'^\d+$', lower_token):
            if len(lower_token) > 4: 
                continue # Drop long random numbers
        
        # D. Resolution-like patterns (e.g. 1920x1080) -> Drop (we recalculate)
        if re.match(r'^\d+x\d+$', lower_token):
            continue
            
        # E. Single char noise? (e.g. "a", "b") -> Maybe keep?
        # User said "asdf.jpg" is junk.
        # Let's keep for now unless it's clearly junk.
        
        cleaned.append(token)
        
    return cleaned
