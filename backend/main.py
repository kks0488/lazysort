from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from engine.parser import analyze_filename_with_gemini, analyze_filenames_batch, parse_filename_regex, clean_tokens
from engine.vision import analyze_image, analyze_image_with_category, get_image_resolution
def analyze_images_batch_mobileclip(paths):
    """Lazy import so the server starts without torch / MobileCLIP installed."""
    from engine.mobileclip_analyzer import analyze_images_batch_mobileclip as _run
    return _run(paths)
from engine.hybrid_analyzer import hybrid_classify, extract_filename_hints
from engine.session_cluster import analyze_folder_sessions, get_session_brand
from engine.image_cluster import cluster_by_similarity, propagate_brand_to_cluster
from engine.merger import smart_merge, smart_merge_v2
from safety.history import save_log, get_undo_operations
from organizer.cleaner import Cleaner
from organizer.clustering import VectorCluster
from organizer.transaction import TransactionManager
from organizer.metadata import MetadataExtractor

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Instances ---
cleaner = Cleaner()
cluster_engine = VectorCluster()
transaction_manager = TransactionManager()
metadata_extractor = MetadataExtractor()

class AnalyzeRequest(BaseModel):
    file_path: str

class RenameRequest(BaseModel):
    original_path: str
    new_name: str

class UndoRequest(BaseModel):
    pass

class OrganizeRequest(BaseModel):
    folder_path: str

class ExecuteMoveRequest(BaseModel):
    moves: list[dict] # [{'src': '...', 'dst': '...'}]

class ScanFolderRequest(BaseModel):
    folder_path: str
    include_subfolders: bool = False

class BatchRenameRequest(BaseModel):
    renames: list[dict] # [{'original_path': '...', 'new_name': '...'}]

class SmartOrganizeRequest(BaseModel):
    folder_path: str
    create_category_folders: bool = True  # 카테고리별 폴더 생성
    include_subfolders: bool = False
    use_clip: bool = True  # MobileCLIP2 로컬 분석 (빠름!) vs Gemini API (느림)

class SessionOrganizeRequest(BaseModel):
    folder_path: str
    gap_minutes: int = 30  # 세션 구분 기준 시간 (분)
    use_ocr: bool = True   # Apple Vision OCR 사용
    use_mobileclip: bool = True  # MobileCLIP2 보완 분석
    dry_run: bool = False  # 시뮬레이션 모드 (파일 이동 안함)

# --- 폴더 기반 일괄 처리 API ---

@app.post("/scan-folder")
async def scan_folder_for_rename(request: ScanFolderRequest):
    """
    폴더 내 이미지 파일들을 스캔하고 AI 분석 결과를 반환합니다.
    """
    if not os.path.exists(request.folder_path):
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다")
    
    # 이미지 확장자
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    
    files_to_analyze = []
    
    if request.include_subfolders:
        for root, _, files in os.walk(request.folder_path):
            for file in files:
                if file.startswith('.'): continue
                ext = os.path.splitext(file)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    files_to_analyze.append(os.path.join(root, file))
    else:
        for file in os.listdir(request.folder_path):
            if file.startswith('.'): continue
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                files_to_analyze.append(os.path.join(request.folder_path, file))
    
    # 분석 결과 수집
    results = []
    for file_path in files_to_analyze:
        try:
            filename = os.path.basename(file_path)
            ext = filename.rsplit('.', 1)[-1] if '.' in filename else ""
            
            # Step 1: AI Text Analysis (파일명에서 정보 추출)
            user_tokens = analyze_filename_with_gemini(filename)
            
            # Step 2: AI Vision Analysis (이미지 분석 - 대분류 포함)
            category = ""
            brand = ""
            ai_tags = []
            specs = []
            
            if ext.lower() in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                # 새로운 카테고리 기반 분석
                analysis = analyze_image_with_category(file_path, user_context=user_tokens)
                category = analysis.get("category", "기타")
                brand = analysis.get("brand", "")
                ai_tags = analysis.get("tags", [])
                
                resolution = get_image_resolution(file_path)
                if resolution:
                    specs.append(resolution)
            
            # Step 3: Smart Merge V2 (새 구조: 대분류_브랜드_태그_해상도)
            new_name = smart_merge_v2(category, brand, user_tokens, ai_tags, specs, ext)
            
            results.append({
                "original_path": file_path,
                "original_name": filename,
                "new_name": new_name,
                "category": category,
                "brand": brand,
                "user_tokens": user_tokens,
                "ai_tags": ai_tags,
                "specs": specs,
                "status": "ready"
            })
        except Exception as e:
            results.append({
                "original_path": file_path,
                "original_name": os.path.basename(file_path),
                "new_name": "",
                "user_tokens": [],
                "ai_tags": [],
                "specs": [],
                "status": "error",
                "error": str(e)
            })
    
    return {
        "folder": request.folder_path,
        "total_files": len(files_to_analyze),
        "files": results
    }

@app.post("/batch-rename")
async def batch_rename_files(request: BatchRenameRequest):
    """
    여러 파일을 일괄 리네이밍합니다.
    """
    success_count = 0
    errors = []
    
    for item in request.renames:
        original_path = item.get('original_path')
        new_name = item.get('new_name')
        
        if not original_path or not new_name:
            errors.append({"path": original_path, "error": "경로 또는 새 이름이 없습니다"})
            continue
            
        if not os.path.exists(original_path):
            errors.append({"path": original_path, "error": "파일을 찾을 수 없습니다"})
            continue
        
        try:
            dir_name = os.path.dirname(original_path)
            new_name_with_ext = new_name
            original_ext = os.path.splitext(original_path)[1]
            if not new_name_with_ext.endswith(original_ext):
                new_name_with_ext += original_ext
            
            new_path = os.path.join(dir_name, new_name_with_ext)
            
            # 충돌 처리: 같은 이름이 있으면 _1, _2 등 추가
            counter = 1
            base_new_path = new_path
            while os.path.exists(new_path) and new_path != original_path:
                name_part = os.path.splitext(base_new_path)[0]
                new_path = f"{name_part}_{counter}{original_ext}"
                counter += 1
            
            if new_path != original_path:
                os.rename(original_path, new_path)
                save_log(original_path, new_path)
                success_count += 1
            else:
                # 이름이 같으면 스킵
                pass
                
        except Exception as e:
            errors.append({"path": original_path, "error": str(e)})
    
    return {
        "success_count": success_count,
        "error_count": len(errors),
        "errors": errors
    }

@app.post("/smart-organize")
async def smart_organize(request: SmartOrganizeRequest):
    """
    빠른 정리: 파일명 배치 AI 분석 + 해상도 추출 → 리네이밍
    """
    if not os.path.exists(request.folder_path):
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다")
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    
    # 1. 파일 수집
    files_to_process = []
    if request.include_subfolders:
        for root, _, files in os.walk(request.folder_path):
            for file in files:
                if file.startswith('.'): continue
                ext = os.path.splitext(file)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    files_to_process.append(os.path.join(root, file))
    else:
        for file in os.listdir(request.folder_path):
            if file.startswith('.'): continue
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                files_to_process.append(os.path.join(request.folder_path, file))
    
    # 2. 출력 폴더 생성 (카테고리별)
    output_base = os.path.join(request.folder_path, "_정리됨")
    os.makedirs(output_base, exist_ok=True)
    
    # 카테고리별 폴더 생성 ("사진" 제거 - 모든 이미지가 사진이므로 의미없음)
    category_folders = {
        "상품": os.path.join(output_base, "01_상품"),
        "배너": os.path.join(output_base, "02_배너"),
        "스크린샷": os.path.join(output_base, "03_스크린샷"),
        "라벨": os.path.join(output_base, "04_라벨"),
        "문서": os.path.join(output_base, "05_문서"),
        "기타": os.path.join(output_base, "06_기타")
    }
    for folder in category_folders.values():
        os.makedirs(folder, exist_ok=True)
    
    # 3. 이미지 분석 (CLIP 또는 Gemini)
    clip_results = {}
    filename_analysis = {}
    cluster_brands = {}  # 클러스터 기반 브랜드 전파
    
    if request.use_clip:
        # MobileCLIP2 로컬 분석 (Apple 최적화!)
        clip_results = analyze_images_batch_mobileclip(files_to_process)
        
        # 클러스터링으로 비슷한 이미지 그룹화 & 브랜드 전파
        # "제목없음.png"도 같은 클러스터의 "케이스위스_상품.jpg"에서 브랜드 상속
        if len(files_to_process) >= 3:  # 3개 이상일 때만
            clusters = cluster_by_similarity(files_to_process, threshold=0.82)
            cluster_brands = propagate_brand_to_cluster(clusters)
    else:
        # Gemini 파일명 분석 (느림)
        filenames = [os.path.basename(fp) for fp in files_to_process]
        batch_size = 20
        for i in range(0, len(filenames), batch_size):
            batch = filenames[i:i+batch_size]
            batch_results = analyze_filenames_batch(batch)
            filename_analysis.update(batch_results)
    
    # 4. 파일 이동
    results = []
    success_count = 0
    error_count = 0
    
    for file_path in files_to_process:
        try:
            filename = os.path.basename(file_path)
            ext = filename.rsplit('.', 1)[-1] if '.' in filename else ""
            
            # 분석 결과 사용
            if request.use_clip:
                # 하이브리드: MobileCLIP + 파일명 힌트 결합
                clip_data = clip_results.get(file_path, {"category": "기타", "confidence": 0})
                hybrid_result = hybrid_classify(clip_data, filename)
                category = hybrid_result.get("category", "기타")
                brand = hybrid_result.get("brand", "")
                
                # 클러스터 브랜드 전파: 파일명에 브랜드가 없어도 비슷한 이미지에서 상속
                if not brand and file_path in cluster_brands:
                    cluster_info = cluster_brands[file_path]
                    if cluster_info.get("brand"):
                        brand = cluster_info["brand"]
                
                keywords = clean_tokens(parse_filename_regex(filename))
            else:
                # Gemini 결과
                analysis = filename_analysis.get(filename, {"category": "기타", "brand": "", "keywords": []})
                category = analysis.get("category", "기타")
                brand = analysis.get("brand", "")
                keywords = analysis.get("keywords", [])
            
            # 해상도 추출 (빠름)
            specs = []
            if ext.lower() in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                resolution = get_image_resolution(file_path)
                if resolution:
                    specs.append(resolution)
            
            # 키워드가 없거나 의미없으면 카테고리 사용
            meaningful_keywords = [k for k in keywords if len(k) > 2 and not k.isdigit()]
            if not meaningful_keywords:
                # 카테고리를 파일명에 포함
                new_name = smart_merge_v2(category, brand, [], [], specs, ext)
            else:
                # 키워드가 있으면 카테고리 없이 (폴더로 구분)
                new_name = smart_merge_v2("", brand, meaningful_keywords, [], specs, ext)
            
            # 카테고리별 폴더로 이동
            dest_folder = category_folders.get(category, category_folders["기타"])
            dest_path = os.path.join(dest_folder, new_name)
            
            # 충돌 처리
            counter = 1
            base_dest = dest_path
            while os.path.exists(dest_path):
                name_part = os.path.splitext(base_dest)[0]
                dest_path = f"{name_part}_{counter}.{ext}"
                counter += 1
            
            # 파일 이동
            shutil.move(file_path, dest_path)
            save_log(file_path, dest_path)
            
            results.append({
                "original": filename,
                "new_name": os.path.basename(dest_path),
                "category": category,
                "status": "success"
            })
            success_count += 1
            
        except Exception as e:
            results.append({
                "original": filename if 'filename' in dir() else file_path,
                "error": str(e),
                "status": "error"
            })
            error_count += 1
    
    return {
        "output_folder": output_base,
        "total_files": len(files_to_process),
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }

@app.post("/analyze")
async def analyze_file(request: AnalyzeRequest):
    file_path = request.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    filename = os.path.basename(file_path)
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ""
    
    # Step 1: AI Text Analysis (Gemini)
    user_tokens = analyze_filename_with_gemini(filename)
    
    # Step 2: AI Enrichment
    ai_tags = []
    specs = []
    if ext.lower() in ['jpg', 'jpeg', 'png', 'webp']:
        ai_tags = analyze_image(file_path, user_context=user_tokens)
        resolution = get_image_resolution(file_path)
        if resolution:
            specs.append(resolution)
            
    # Step 3: Smart Merge (with length limit)
    new_name = smart_merge(user_tokens, ai_tags, specs, ext)
    
    return {
        "original": filename,
        "new_name": new_name,
        "user_tokens": user_tokens,
        "ai_tags": ai_tags,
        "specs": specs
    }

@app.post("/rename")
async def rename_file(request: RenameRequest):
    try:
        if not os.path.exists(request.original_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        dir_name = os.path.dirname(request.original_path)
        new_name_with_ext = request.new_name
        if not new_name_with_ext.endswith(os.path.splitext(request.original_path)[1]):
            new_name_with_ext += os.path.splitext(request.original_path)[1]

        new_path = os.path.join(dir_name, new_name_with_ext)
        
        # Check collision
        if os.path.exists(new_path):
            raise HTTPException(status_code=400, detail="Target filename already exists")
            
        os.rename(request.original_path, new_path)
        
        # Log for Undo
        save_log(request.original_path, new_path)
        
        return {"status": "success", "new_path": new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/undo")
async def undo_last_operation(request: UndoRequest):
    ops = get_undo_operations(1)
    if not ops:
        return {"status": "no_history"}
        
    last_op = ops[0]
    original = last_op["original"]
    current = last_op["new"] # This was the 'new' path
    
    if not os.path.exists(current):
        return {"status": "error", "message": "File to undo not found"}
        
    if os.path.exists(original):
        return {"status": "error", "message": "Original file path already exists"}
        
    try:
        os.rename(current, original)
        return {"status": "success", "restored": original}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Organizer Endpoints ---

@app.post("/organize/scan")
async def scan_folder(request: OrganizeRequest):
    """Step 1: Clean & Scan"""
    if not os.path.exists(request.folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")
        
    results = cleaner.scan_folder(request.folder_path)
    return results

@app.post("/organize/cluster")
async def cluster_folder(request: OrganizeRequest):
    """Step 2: Vector Clustering"""
    if not os.path.exists(request.folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")
        
    # Get valid images
    valid_files = []
    for root, _, files in os.walk(request.folder_path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                valid_files.append(os.path.join(root, file))
    
    # Limit for demo
    if len(valid_files) > 50:
        valid_files = valid_files[:50]
        
    clusters = cluster_engine.cluster_files(valid_files)
    
    # Format for frontend
    response = []
    for cid, data in clusters.items():
        response.append({
            "cluster_id": int(cid),
            "name": data['name'],
            "files": data['files']
        })
        
    return response

@app.post("/organize/execute")
async def execute_moves(request: ExecuteMoveRequest):
    """Step 4: Execute Transaction"""
    for move in request.moves:
        transaction_manager.add_move(move['src'], move['dst'])
        
    count, errors = transaction_manager.execute()
    return {"processed": count, "errors": errors}

@app.post("/organize/rollback")
async def rollback_moves():
    """Safety: Rollback"""
    count = transaction_manager.rollback()
    return {"rolled_back": count}


# --- 세션 기반 스마트 정리 API ---

@app.post("/session-analyze")
async def session_analyze(request: SessionOrganizeRequest):
    """
    세션(작업 시간) 기반 폴더 분석
    - 시간축 기반 그룹화
    - OCR로 브랜드명 추출
    """
    if not os.path.exists(request.folder_path):
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다")
    
    result = analyze_folder_sessions(request.folder_path, request.gap_minutes)
    return result


@app.post("/session-organize")
async def session_organize(request: SessionOrganizeRequest):
    """
    세션 기반 스마트 정리 (시간 + OCR + MobileCLIP2)
    """
    if not os.path.exists(request.folder_path):
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다")
    
    # 1. 세션 분석
    analysis = analyze_folder_sessions(request.folder_path, request.gap_minutes)
    
    if analysis["total_sessions"] == 0:
        return {"error": "분석할 파일이 없습니다"}
    
    # 2. 출력 폴더 생성
    output_base = os.path.join(request.folder_path, "_세션정리")
    
    if not request.dry_run:
        os.makedirs(output_base, exist_ok=True)
    
    # 3. 세션별 폴더 생성 및 파일 이동
    results = []
    success_count = 0
    error_count = 0
    
    for session in analysis["sessions"]:
        session_folder = os.path.join(output_base, session["folder_name"])
        
        if not request.dry_run:
            os.makedirs(session_folder, exist_ok=True)
        
        # MobileCLIP2로 세션 내 파일 추가 분류 (선택)
        category_counts = {}
        if request.use_mobileclip and not request.dry_run:
            clip_results = analyze_images_batch_mobileclip(session["files"][:10])  # 샘플 10개만
            for r in clip_results.values():
                cat = r.get("category", "기타")
                category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # 파일 이동
        moved_files = []
        for file_path in session["files"]:
            try:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(session_folder, filename)
                
                if not request.dry_run:
                    # 충돌 처리
                    counter = 1
                    base_dest = dest_path
                    while os.path.exists(dest_path):
                        name, ext = os.path.splitext(base_dest)
                        dest_path = f"{name}_{counter}{ext}"
                        counter += 1
                    
                    shutil.move(file_path, dest_path)
                    save_log(file_path, dest_path)
                
                moved_files.append(filename)
                success_count += 1
            except Exception as e:
                error_count += 1
        
        results.append({
            "session_id": session["id"],
            "folder_name": session["folder_name"],
            "brand": session["brand"],
            "file_count": session["count"],
            "moved_files": len(moved_files),
            "categories": category_counts,
            "time_range": session["time_range"]
        })
    
    return {
        "output_folder": output_base,
        "total_files": analysis["total_files"],
        "total_sessions": analysis["total_sessions"],
        "success_count": success_count,
        "error_count": error_count,
        "dry_run": request.dry_run,
        "sessions": results
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("LAZYSORT_HOST", "127.0.0.1"), port=int(os.environ.get("LAZYSORT_PORT", "2424")))
