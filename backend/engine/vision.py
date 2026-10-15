import google.generativeai as genai
from PIL import Image
import os

# --- IMMUTABLE CONSTANTS ---
API_KEY = os.environ.get("GEMINI_API_KEY", "")  # set in your shell, never commit keys
MODEL_NAME = "gemini-2.5-flash"
# ---------------------------

# 대분류 카테고리 정의
CATEGORIES = {
    "상품": "의류, 신발, 가방, 악세서리 등 쇼핑몰/이커머스 판매용 상품 이미지",
    "배너": "가로로 긴 웹사이트 광고 배너, 프로모션 이미지 (보통 가로:세로 비율 3:1 이상)",
    "스크린샷": "스마트폰이나 PC 화면을 캡처한 이미지, 채팅, 앱 화면",
    "문서": "계약서, 운송장, 영수증, 송장 등 문서/서류 사진",
    "라벨": "케어라벨, 상품택, 사이즈표, 성분표 등",
    "사진": "풍경, 인물, 일상 사진 등 일반적인 사진",
    "기타": "위 카테고리에 해당하지 않는 이미지"
}

# Configure API
genai.configure(api_key=API_KEY)

def analyze_image_with_category(image_path: str, user_context: list[str] = None) -> dict:
    """
    이미지를 분석하여 대분류와 상세 태그를 반환합니다.
    Returns: {"category": "상품", "brand": "케이스위스", "tags": ["블랙", "겨울"]}
    """
    try:
        if not os.path.exists(image_path):
            return {"category": "기타", "brand": "", "tags": []}

        model = genai.GenerativeModel(MODEL_NAME)
        image = Image.open(image_path)
        
        # 이미지 비율 계산 (배너 판단용)
        width, height = image.size
        aspect_ratio = width / height if height > 0 else 1
        
        context_str = ", ".join(user_context) if user_context else "없음"
        
        # 체계적인 분석 프롬프트
        prompt = f"""이 이미지를 분석해서 파일명에 사용할 정보를 추출해줘.

현재 파일명에서 추출된 정보: [{context_str}]
이미지 비율: {aspect_ratio:.2f} (가로/세로)

**대분류 카테고리** (반드시 하나만 선택):
- 상품: 의류, 신발, 가방 등 쇼핑몰 판매용 상품 이미지
- 배너: 가로로 긴 광고 배너 (비율 2.5 이상이면 배너일 가능성 높음)
- 스크린샷: 스마트폰/PC 화면 캡처, 채팅 화면
- 문서: 계약서, 운송장, 영수증 등 서류
- 라벨: 케어라벨, 상품택, 사이즈표
- 사진: 풍경, 인물 등 일반 사진
- 기타: 분류 불가

**출력 형식** (정확히 이 형식으로만 출력):
대분류: [카테고리]
브랜드: [브랜드명 또는 없음]
태그: [태그1], [태그2], [태그3]

**태그 규칙**:
1. 이미 파일명에 있는 단어와 중복되지 않게
2. 대분류별 중요 정보:
   - 상품: 색상, 종류(맨투맨/자켓/바지 등), 시즌
   - 배너: 테마, 분위기, 대상(남성/여성/커플)
   - 스크린샷: 앱종류, 내용요약
   - 문서: 문서종류, 발신/수신
   - 라벨: 상품종류, 소재
3. 한국어로 출력
4. 태그는 최대 3개"""

        response = model.generate_content([prompt, image])
        text = response.text.strip()
        
        # 파싱
        result = {"category": "기타", "brand": "", "tags": []}
        
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('대분류:'):
                cat = line.replace('대분류:', '').strip()
                if cat in CATEGORIES:
                    result["category"] = cat
            elif line.startswith('브랜드:'):
                brand = line.replace('브랜드:', '').strip()
                if brand and brand != '없음':
                    result["brand"] = brand.replace(" ", "")
            elif line.startswith('태그:'):
                tags_str = line.replace('태그:', '').strip()
                tags = [t.strip().replace(" ", "_") for t in tags_str.split(',')]
                result["tags"] = [t for t in tags if t and t != '없음']
        
        return result
        
    except Exception as e:
        print(f"Error analyzing image {image_path}: {e}")
        return {"category": "기타", "brand": "", "tags": []}


def analyze_image(image_path: str, user_context: list[str] = None) -> list[str]:
    """
    기존 API 호환용 - 태그만 반환
    """
    result = analyze_image_with_category(image_path, user_context)
    return result.get("tags", [])

def get_image_resolution(image_path: str) -> str:
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            return f"{width}x{height}"
    except Exception:
        return ""
