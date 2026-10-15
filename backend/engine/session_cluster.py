"""
세션 기반 스마트 클러스터링
- 시간축 기반 그룹화 (작업 세션 구분)
- Apple Vision OCR (브랜드명 추출)
- MobileCLIP2 보완 (텍스트 없을 때)
"""

import os
from datetime import datetime
from collections import Counter
from PIL import Image

# Apple Vision OCR (macOS 네이티브)
try:
    import Vision
    import Quartz
    from Foundation import NSURL
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    print("⚠️ Apple Vision 사용 불가 - PyObjC 설치 필요")


def get_file_sessions(folder_path: str, gap_minutes: int = 30) -> dict:
    """
    파일 수정 시간 기반으로 세션(작업 그룹) 분리
    
    Args:
        folder_path: 폴더 경로
        gap_minutes: 세션 구분 기준 시간 (분)
    
    Returns:
        {
            0: [파일1, 파일2, ...],  # 세션 0
            1: [파일3, 파일4, ...],  # 세션 1
            ...
        }
    """
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    
    # 파일 목록 및 시간 수집
    files_data = []
    for f in os.listdir(folder_path):
        if f.startswith('.'):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
            
        full_path = os.path.join(folder_path, f)
        if os.path.isfile(full_path):
            mtime = os.path.getmtime(full_path)
            files_data.append({
                'path': full_path,
                'name': f,
                'mtime': mtime,
                'dt': datetime.fromtimestamp(mtime)
            })
    
    if not files_data:
        return {}
    
    # 시간순 정렬
    files_data.sort(key=lambda x: x['mtime'])
    
    # 세션 구분 (시간 차이 기준)
    sessions = {}
    current_session = 0
    sessions[current_session] = [files_data[0]]
    
    gap_seconds = gap_minutes * 60
    
    for i in range(1, len(files_data)):
        time_diff = files_data[i]['mtime'] - files_data[i-1]['mtime']
        
        if time_diff > gap_seconds:
            # 새로운 세션 시작
            current_session += 1
        
        if current_session not in sessions:
            sessions[current_session] = []
        sessions[current_session].append(files_data[i])
    
    return sessions


def detect_text_apple_vision(image_path: str) -> list[str]:
    """
    Apple Vision Framework로 이미지에서 텍스트 추출 (macOS 네이티브)
    """
    if not VISION_AVAILABLE:
        return []
    
    try:
        # 이미지 로드
        image_url = NSURL.fileURLWithPath_(image_path)
        
        # Vision 요청 생성
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(["en", "ko"])  # 영어, 한국어
        
        # 이미지 핸들러
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(image_url, None)
        
        # 실행
        success = handler.performRequests_error_([request], None)
        
        if not success:
            return []
        
        # 결과 추출
        results = request.results()
        texts = []
        
        for observation in results:
            if observation.confidence() > 0.5:  # 신뢰도 50% 이상
                text = observation.topCandidates_(1)[0].string()
                # 3글자 이상, 의미있는 텍스트만
                if len(text) >= 3:
                    texts.append(text.upper())
        
        return texts
        
    except Exception as e:
        print(f"OCR 오류: {e}")
        return []


def detect_text_simple(image_path: str) -> list[str]:
    """
    파일명에서 키워드 추출 (OCR 대안)
    """
    filename = os.path.basename(image_path)
    name = os.path.splitext(filename)[0]
    
    # 구분자로 분리
    import re
    tokens = re.split(r'[_\-\s\.\(\)\[\]]+', name)
    
    # 필터링 (3글자 이상, 숫자만 있는 것 제외)
    keywords = []
    for token in tokens:
        if len(token) >= 3 and not token.isdigit():
            # 쓰레기 패턴 제외
            if token.lower() not in ['img', 'image', 'dsc', 'photo', 'screenshot', 'capture']:
                keywords.append(token.upper())
    
    return keywords


def get_session_brand(session_files: list, use_ocr: bool = True) -> tuple[str, str]:
    """
    세션(작업 그룹)의 브랜드명/키워드 추출
    
    Args:
        session_files: 세션 내 파일 목록
        use_ocr: Apple Vision OCR 사용 여부
    
    Returns:
        (브랜드명, 날짜문자열)
    """
    # 샘플 이미지 선택 (최대 5개)
    sample_size = min(5, len(session_files))
    samples = session_files[:sample_size]
    
    all_keywords = []
    
    for file_data in samples:
        path = file_data['path']
        
        # 1. OCR로 텍스트 추출 시도
        if use_ocr and VISION_AVAILABLE:
            texts = detect_text_apple_vision(path)
            all_keywords.extend(texts)
        
        # 2. 파일명에서 키워드 추출 (보조)
        keywords = detect_text_simple(path)
        all_keywords.extend(keywords)
    
    # 가장 많이 등장한 키워드
    if all_keywords:
        counter = Counter(all_keywords)
        # 상위 키워드 (최소 2회 이상 등장하거나 가장 많은 것)
        most_common = counter.most_common(3)
        brand = most_common[0][0] if most_common else "기타"
    else:
        brand = "기타"
    
    # 날짜 문자열 (세션 첫 파일 기준)
    first_file = session_files[0]
    date_str = first_file['dt'].strftime("%y%m%d")
    
    return brand, date_str


def analyze_folder_sessions(folder_path: str, gap_minutes: int = 30) -> dict:
    """
    폴더 분석: 세션 기반 클러스터링
    
    Returns:
        {
            "sessions": [
                {
                    "id": 0,
                    "brand": "NIKE",
                    "date": "251202",
                    "folder_name": "251202_NIKE",
                    "files": [...],
                    "count": 15
                },
                ...
            ],
            "total_files": 100,
            "total_sessions": 5
        }
    """
    sessions = get_file_sessions(folder_path, gap_minutes)
    
    result = {
        "sessions": [],
        "total_files": 0,
        "total_sessions": len(sessions)
    }
    
    for session_id, files in sessions.items():
        brand, date_str = get_session_brand(files)
        
        # 폴더명 생성
        folder_name = f"{date_str}_{brand}"
        
        session_info = {
            "id": session_id,
            "brand": brand,
            "date": date_str,
            "folder_name": folder_name,
            "files": [f['path'] for f in files],
            "file_names": [f['name'] for f in files],
            "count": len(files),
            "time_range": {
                "start": files[0]['dt'].isoformat(),
                "end": files[-1]['dt'].isoformat()
            }
        }
        
        result["sessions"].append(session_info)
        result["total_files"] += len(files)
    
    return result


# 테스트
if __name__ == "__main__":
    test_dir = os.environ.get("LAZYSORT_TEST_DIR", "samples")
    
    print("🔍 세션 기반 클러스터링 테스트")
    print(f"📁 폴더: {test_dir}")
    print(f"⚙️ Apple Vision OCR: {'✅ 사용 가능' if VISION_AVAILABLE else '❌ 사용 불가'}")
    print()
    
    result = analyze_folder_sessions(test_dir, gap_minutes=30)
    
    print(f"📊 총 {result['total_files']}개 파일 → {result['total_sessions']}개 세션")
    print()
    
    for session in result["sessions"][:5]:  # 상위 5개만
        print(f"📂 세션 {session['id']}: {session['folder_name']}")
        print(f"   파일 수: {session['count']}개")
        print(f"   시간: {session['time_range']['start']} ~ {session['time_range']['end']}")
        print(f"   샘플: {session['file_names'][:3]}")
        print()

