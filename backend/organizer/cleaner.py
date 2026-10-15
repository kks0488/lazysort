import os
import hashlib
from PIL import Image
import shutil

class Cleaner:
    def __init__(self, low_res_threshold: int = 800):
        self.low_res_threshold = low_res_threshold
        self.seen_hashes = {} # hash -> file_path

    def calculate_hash(self, file_path: str) -> str:
        """Calculates MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"Error hashing {file_path}: {e}")
            return ""

    def is_low_res(self, file_path: str) -> bool:
        """Checks if image is low resolution."""
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                return width < self.low_res_threshold or height < self.low_res_threshold
        except Exception:
            return False

    def is_screenshot(self, file_path: str) -> bool:
        """
        Checks if file is a screenshot based on multiple criteria.
        PNG 확장자만으로 스크린샷 판단하지 않음 (디자인 에셋도 PNG일 수 있음)
        """
        filename = os.path.basename(file_path).lower()
        
        # 1. 파일명 패턴으로 스크린샷 판단
        screenshot_patterns = [
            'screenshot', 'screen_shot', 'screen shot',
            '스크린샷', '스크린_샷', 'capture', 'img_', 
            '화면 캡처', '화면캡처', '이미지 2025', '이미지 2024'
        ]
        for pattern in screenshot_patterns:
            if pattern in filename:
                return True
        
        # 2. 스마트폰 스크린샷 비율 체크 (PNG 파일만)
        if filename.endswith('.png'):
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    # 세로가 긴 스마트폰 비율 (예: 1206x2622 → 약 1:2.17)
                    if height > width:
                        ratio = height / width
                        # 스마트폰 비율: 1:1.8 ~ 1:2.5 (iPhone, Android 등)
                        if 1.8 <= ratio <= 2.5 and width > 500:
                            return True
            except Exception:
                pass
        
        return False

    def scan_folder(self, folder_path: str) -> dict:
        """
        Scans folder and categorizes files.
        Returns a dict of actions: {'duplicates': [], 'low_res': [], 'screenshots': [], 'valid': []}
        """
        # 스캔 시작 시 해시 캐시 초기화
        self.seen_hashes = {}
        
        actions = {
            'duplicates': [],
            'low_res': [],
            'screenshots': [],
            'valid': []
        }
        
        # Walk through all files
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.startswith('.'): continue # Skip hidden files
                
                file_path = os.path.join(root, file)
                
                # 1. Check Hash (Deduplication)
                file_hash = self.calculate_hash(file_path)
                if file_hash in self.seen_hashes:
                    actions['duplicates'].append(file_path)
                    continue
                self.seen_hashes[file_hash] = file_path
                
                # 2. Check Screenshot
                if self.is_screenshot(file_path):
                    actions['screenshots'].append(file_path)
                    continue
                    
                # 3. Check Low Res
                if self.is_low_res(file_path):
                    actions['low_res'].append(file_path)
                    continue
                    
                # 4. Valid
                actions['valid'].append(file_path)
                
        return actions
