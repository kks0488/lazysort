import React, { useState, useRef } from 'react';
import PreviewList from './components/PreviewList';
import Organizer from './components/Organizer';
import axios from 'axios';
import { LayoutGrid, Layers, RotateCcw, Wand2, FolderOpen, FolderSearch, Loader2, CheckCircle, XCircle, Upload, Sparkles, FolderTree } from 'lucide-react';

function App() {
  const [files, setFiles] = useState([]);
  const [activeTab, setActiveTab] = useState('renamer');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [folderPath, setFolderPath] = useState('');
  const [includeSubfolders, setIncludeSubfolders] = useState(false);
  const [scanStatus, setScanStatus] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [smartOrganizeResult, setSmartOrganizeResult] = useState(null);
  const [createCategoryFolders, setCreateCategoryFolders] = useState(true);
  const [useClip, setUseClip] = useState(true);  // CLIP 로컬 분석 (기본값: true)
  const inputRef = useRef(null);

  // 한 번에 정리 (리네이밍 + 폴더 정리)
  const handleSmartOrganize = async () => {
    if (!folderPath.trim()) {
      alert('폴더 경로를 입력해주세요!');
      return;
    }

    setIsProcessing(true);
    setScanStatus(useClip ? '🚀 CLIP AI 분석 중... (초고속!)' : '🚀 Gemini 분석 중... (느림)');
    setSmartOrganizeResult(null);

    try {
      const res = await axios.post('http://localhost:2424/smart-organize', {
        folder_path: folderPath,
        create_category_folders: createCategoryFolders,
        include_subfolders: includeSubfolders,
        use_clip: useClip
      });

      setSmartOrganizeResult(res.data);
      setScanStatus(`✅ ${res.data.success_count}개 파일 정리 완료! → ${res.data.output_folder}`);
    } catch (error) {
      console.error(error);
      setScanStatus(`❌ 오류: ${error.response?.data?.detail || error.message}`);
    }

    setIsProcessing(false);
  };

  // 드래그앤드롭 핸들러
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    // 방법 1: URI 리스트에서 file:// 경로 추출 (macOS Finder)
    const uriList = e.dataTransfer.getData('text/uri-list');
    if (uriList) {
      const fileUrl = uriList.split('\n')[0].trim();
      if (fileUrl.startsWith('file://')) {
        const path = decodeURIComponent(fileUrl.replace('file://', ''));
        setFolderPath(path);
        setScanStatus(`📁 폴더 선택됨: ${path.split('/').pop()}`);
        return;
      }
    }

    // 방법 2: 텍스트로 경로 드롭
    const text = e.dataTransfer.getData('text/plain');
    if (text) {
      // file:// URL 형식
      if (text.startsWith('file://')) {
        const path = decodeURIComponent(text.replace('file://', '').trim());
        setFolderPath(path);
        setScanStatus(`📁 폴더 선택됨: ${path.split('/').pop()}`);
        return;
      }
      // 절대 경로
      if (text.startsWith('/')) {
        setFolderPath(text.trim());
        setScanStatus(`📁 폴더 경로 입력됨`);
        return;
      }
    }

    // 방법 3: 파일 path 속성 (Electron)
    const files = e.dataTransfer.files;
    if (files && files.length > 0 && files[0].path) {
      const filePath = files[0].path;
      // 파일이면 상위 폴더, 폴더면 그대로
      const path = filePath.includes('.') ? filePath.substring(0, filePath.lastIndexOf('/')) : filePath;
      setFolderPath(path);
      setScanStatus(`📁 폴더 선택됨: ${path.split('/').pop()}`);
      return;
    }

    // 안내 메시지
    setScanStatus('⚠️ 경로를 직접 입력해주세요. (Finder → 폴더 우클릭 → 옵션 → 경로 복사)');
  };

  // 폴더 스캔 및 AI 분석
  const handleScanFolder = async () => {
    if (!folderPath.trim()) {
      alert('폴더 경로를 입력해주세요!');
      return;
    }

    setIsScanning(true);
    setScanStatus('폴더 스캔 및 AI 분석 중...');
    setFiles([]);

    try {
      const res = await axios.post('http://localhost:2424/scan-folder', {
        folder_path: folderPath,
        include_subfolders: includeSubfolders
      });

      const filesWithSelection = res.data.files.map(f => ({
        ...f,
        selected: f.status === 'ready'
      }));

      setFiles(filesWithSelection);
      setScanStatus(`✅ ${res.data.total_files}개 파일 분석 완료`);
    } catch (error) {
      console.error(error);
      setScanStatus(`❌ 오류: ${error.response?.data?.detail || error.message}`);
    }

    setIsScanning(false);
  };

  // 일괄 리네이밍 실행
  const handleBatchRename = async () => {
    const filesToRename = files.filter(f => f.selected && f.status === 'ready');
    
    if (filesToRename.length === 0) {
      alert('리네이밍할 파일을 선택해주세요!');
      return;
    }

    setIsProcessing(true);
    setScanStatus('파일 이름 변경 중...');

    try {
      const renames = filesToRename.map(f => ({
        original_path: f.original_path,
        new_name: f.new_name
      }));

      const res = await axios.post('http://localhost:2424/batch-rename', { renames });

      // 상태 업데이트
      setFiles(prev => prev.map(f => {
        if (f.selected && f.status === 'ready') {
          return { ...f, status: 'done' };
        }
        return f;
      }));

      setScanStatus(`✅ ${res.data.success_count}개 파일 이름 변경 완료`);
      
      if (res.data.error_count > 0) {
        console.error('Errors:', res.data.errors);
        setScanStatus(prev => prev + ` (${res.data.error_count}개 오류)`);
      }
    } catch (error) {
      console.error(error);
      setScanStatus(`❌ 오류: ${error.response?.data?.detail || error.message}`);
    }

    setIsProcessing(false);
  };

  // Undo
  const handleUndo = async () => {
    try {
      const res = await axios.post('http://localhost:2424/undo', {});
      if (res.data.status === 'success') {
        setScanStatus(`↩️ 복원됨: ${res.data.restored}`);
      } else {
        setScanStatus(`ℹ️ ${res.data.message || '복원할 항목이 없습니다'}`);
      }
    } catch (error) {
      console.error(error);
    }
  };

  // 파일 선택 토글
  const handleToggle = (index) => {
    setFiles(prev => prev.map((f, i) => i === index ? { ...f, selected: !f.selected } : f));
  };

  // 전체 선택/해제
  const handleSelectAll = () => {
    const allSelected = files.every(f => f.selected);
    setFiles(prev => prev.map(f => ({ ...f, selected: !allSelected })));
  };

  const readyCount = files.filter(f => f.status === 'ready').length;
  const selectedCount = files.filter(f => f.selected && f.status === 'ready').length;
  const doneCount = files.filter(f => f.status === 'done').length;

  return (
    <div className="min-h-screen bg-gray-900 text-white font-sans">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-900 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-8">
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            lazysort
          </h1>
          <nav className="flex gap-1">
            <button 
              onClick={() => setActiveTab('smart')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${activeTab === 'smart' ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              <Sparkles size={18} /> 한 번에 정리
            </button>
            <button 
              onClick={() => setActiveTab('renamer')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${activeTab === 'renamer' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              <LayoutGrid size={18} /> 리네이머
            </button>
            <button 
              onClick={() => setActiveTab('organizer')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${activeTab === 'organizer' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              <Layers size={18} /> 정리기
            </button>
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'smart' ? (
          /* ============ 한 번에 정리 탭 ============ */
          <div className="space-y-6">
            {/* 헤더 */}
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent mb-2">
                ✨ 한 번에 정리
              </h2>
              <p className="text-gray-400">AI 분석 → 리네이밍 → 카테고리별 폴더 정리를 한 번에!</p>
            </div>

            {/* 폴더 입력 */}
            <div 
              className={`bg-gray-800 rounded-2xl p-6 border-2 transition-all duration-200 ${
                isDragOver ? 'border-purple-500 bg-purple-500/10' : 'border-gray-700'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="flex items-center gap-3 mb-4">
                <FolderTree className="text-purple-400" size={24} />
                <h3 className="text-lg font-bold">정리할 폴더 선택</h3>
              </div>

              <div className="border-2 border-dashed border-gray-600 rounded-xl p-6 text-center mb-4">
                {isDragOver ? (
                  <div className="flex flex-col items-center gap-3">
                    <Upload className="w-12 h-12 text-purple-400 animate-bounce" />
                    <p className="text-purple-400 font-medium">여기에 놓으세요!</p>
                  </div>
                ) : (
                  <>
                    <FolderOpen className="w-10 h-10 text-gray-500 mx-auto mb-3" />
                    <p className="text-gray-400 mb-3">Finder에서 폴더를 드래그하거나</p>
                    <input 
                      type="text"
                      value={folderPath}
                      onChange={(e) => setFolderPath(e.target.value)}
                      placeholder="폴더 경로 입력"
                      className="w-full max-w-md mx-auto bg-gray-900 border border-gray-600 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:ring-2 focus:ring-purple-500 outline-none text-center"
                    />
                  </>
                )}
              </div>

              {folderPath && (
                <div className="flex items-center gap-2 bg-gray-900/50 rounded-lg px-4 py-2 mb-4">
                  <FolderOpen size={16} className="text-purple-400" />
                  <span className="text-sm text-gray-300 truncate flex-1">{folderPath}</span>
                  <button onClick={() => setFolderPath('')} className="text-gray-500 hover:text-white">✕</button>
                </div>
              )}

              {/* 옵션 */}
              <div className="flex flex-wrap items-center gap-6 text-sm">
                <label className="flex items-center gap-2 text-gray-400 cursor-pointer">
                  <input 
                    type="checkbox"
                    checked={includeSubfolders}
                    onChange={(e) => setIncludeSubfolders(e.target.checked)}
                    className="rounded border-gray-600 bg-gray-700 text-purple-500 focus:ring-purple-500"
                  />
                  하위 폴더도 포함
                </label>
                <label className="flex items-center gap-2 text-gray-400 cursor-pointer">
                  <input 
                    type="checkbox"
                    checked={useClip}
                    onChange={(e) => setUseClip(e.target.checked)}
                    className="rounded border-gray-600 bg-gray-700 text-green-500 focus:ring-green-500"
                  />
                  <span className="text-green-400">⚡ CLIP 로컬 분석</span>
                  <span className="text-gray-500 text-xs">(50개/초, 추천!)</span>
                </label>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {useClip 
                  ? '🚀 CLIP 로컬 AI로 이미지 분석 (초고속!) + 파일명 키워드 추출' 
                  : '🐢 Gemini API로 파일명 분석 (느림, 20개당 ~10초)'}
              </p>
            </div>

            {/* 실행 버튼 */}
            <div className="flex justify-center">
              <button
                onClick={handleSmartOrganize}
                disabled={isProcessing || !folderPath.trim()}
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed px-10 py-4 rounded-2xl font-bold text-lg transition-all hover:scale-105 active:scale-95 flex items-center gap-3 shadow-lg shadow-purple-500/25"
              >
                {isProcessing ? (
                  <>
                    <Loader2 size={24} className="animate-spin" /> 정리 중...
                  </>
                ) : (
                  <>
                    <Sparkles size={24} /> 한 번에 정리 시작
                  </>
                )}
              </button>
            </div>

            {/* 상태 메시지 */}
            {scanStatus && (
              <div className={`p-4 rounded-xl border text-center ${
                scanStatus.startsWith('✅') ? 'bg-green-500/10 border-green-500/30 text-green-400' :
                scanStatus.startsWith('❌') ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                'bg-purple-500/10 border-purple-500/30 text-purple-400'
              }`}>
                {scanStatus}
              </div>
            )}

            {/* 결과 미리보기 */}
            {smartOrganizeResult && (
              <div className="bg-gray-800 rounded-2xl p-6 border border-gray-700">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                  <CheckCircle className="text-green-400" /> 정리 완료
                </h3>
                
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="bg-gray-900 rounded-xl p-4 text-center">
                    <div className="text-3xl font-bold text-white">{smartOrganizeResult.total_files}</div>
                    <div className="text-sm text-gray-400">전체 파일</div>
                  </div>
                  <div className="bg-green-500/10 rounded-xl p-4 text-center">
                    <div className="text-3xl font-bold text-green-400">{smartOrganizeResult.success_count}</div>
                    <div className="text-sm text-gray-400">성공</div>
                  </div>
                  <div className="bg-red-500/10 rounded-xl p-4 text-center">
                    <div className="text-3xl font-bold text-red-400">{smartOrganizeResult.error_count}</div>
                    <div className="text-sm text-gray-400">오류</div>
                  </div>
                </div>

                <div className="bg-gray-900 rounded-xl p-4 mb-4">
                  <div className="text-sm text-gray-400 mb-1">📁 결과 폴더</div>
                  <div className="text-white font-mono text-sm">{smartOrganizeResult.output_folder}</div>
                </div>

                {/* 카테고리별 통계 */}
                <div className="text-sm text-gray-400 mb-2">카테고리별 파일 수</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(
                    smartOrganizeResult.results.reduce((acc, r) => {
                      if (r.status === 'success') {
                        acc[r.category] = (acc[r.category] || 0) + 1;
                      }
                      return acc;
                    }, {})
                  ).map(([cat, count]) => (
                    <span key={cat} className={`px-3 py-1 rounded-full text-sm font-medium ${
                      cat === '상품' ? 'bg-green-500/20 text-green-400' :
                      cat === '배너' ? 'bg-yellow-500/20 text-yellow-400' :
                      cat === '스크린샷' ? 'bg-blue-500/20 text-blue-400' :
                      cat === '라벨' ? 'bg-purple-500/20 text-purple-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {cat}: {count}개
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : activeTab === 'renamer' ? (
          <div className="space-y-6">
            {/* 폴더 입력 섹션 - 드래그앤드롭 지원 */}
            <div 
              className={`bg-gray-800 rounded-2xl p-6 border-2 transition-all duration-200 ${
                isDragOver 
                  ? 'border-blue-500 bg-blue-500/10 scale-[1.01]' 
                  : 'border-gray-700 hover:border-gray-600'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="flex items-center gap-3 mb-4">
                <FolderOpen className="text-blue-400" size={24} />
                <h2 className="text-lg font-bold">폴더 선택</h2>
                <span className="text-xs text-gray-500 bg-gray-700 px-2 py-1 rounded-full">
                  드래그앤드롭 가능
                </span>
              </div>
              
              <div className="space-y-4">
                {/* 드래그앤드롭 영역 */}
                <div 
                  className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all ${
                    isDragOver 
                      ? 'border-blue-500 bg-blue-500/5' 
                      : 'border-gray-600 hover:border-gray-500'
                  }`}
                >
                  {isDragOver ? (
                    <div className="flex flex-col items-center gap-3">
                      <Upload className="w-12 h-12 text-blue-400 animate-bounce" />
                      <p className="text-blue-400 font-medium">여기에 놓으세요!</p>
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-col items-center gap-3 mb-4">
                        <FolderOpen className="w-10 h-10 text-gray-500" />
                        <p className="text-gray-400">
                          <span className="text-blue-400 font-medium">Finder에서 폴더를 드래그</span>하여 여기에 놓거나
                        </p>
                      </div>
                      <input 
                        ref={inputRef}
                        type="text"
                        value={folderPath}
                        onChange={(e) => setFolderPath(e.target.value)}
                        placeholder="폴더 경로를 직접 입력하세요 (예: /Users/username/Pictures)"
                        className="w-full bg-gray-900 border border-gray-600 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-center"
                      />
                    </>
                  )}
                </div>

                {/* 선택된 폴더 표시 */}
                {folderPath && (
                  <div className="flex items-center gap-2 bg-gray-900/50 rounded-lg px-4 py-2">
                    <FolderOpen size={16} className="text-blue-400" />
                    <span className="text-sm text-gray-300 truncate flex-1">{folderPath}</span>
                    <button 
                      onClick={() => setFolderPath('')}
                      className="text-gray-500 hover:text-white transition-colors"
                    >
                      ✕
                    </button>
                  </div>
                )}
                
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                    <input 
                      type="checkbox"
                      checked={includeSubfolders}
                      onChange={(e) => setIncludeSubfolders(e.target.checked)}
                      className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                    />
                    하위 폴더도 포함
                  </label>
                  
                  <button
                    onClick={handleScanFolder}
                    disabled={isScanning || !folderPath.trim()}
                    className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 rounded-xl font-bold transition-all flex items-center gap-2"
                  >
                    {isScanning ? (
                      <>
                        <Loader2 size={18} className="animate-spin" /> 스캔 중...
                      </>
                    ) : (
                      <>
                        <FolderSearch size={18} /> 스캔 & 분석
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* 상태 바 */}
            {scanStatus && (
              <div className={`p-4 rounded-xl border ${
                scanStatus.startsWith('✅') ? 'bg-green-500/10 border-green-500/30 text-green-400' :
                scanStatus.startsWith('❌') ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                'bg-blue-500/10 border-blue-500/30 text-blue-400'
              }`}>
                {scanStatus}
              </div>
            )}

            {/* 파일 목록 */}
            {files.length > 0 && (
              <>
                {/* 통계 바 */}
                <div className="flex items-center justify-between bg-gray-800/50 rounded-xl p-4 border border-gray-700">
                  <div className="flex items-center gap-6 text-sm">
                    <span className="text-gray-400">
                      전체: <span className="text-white font-bold">{files.length}</span>개
                    </span>
                    <span className="text-green-400">
                      <CheckCircle size={14} className="inline mr-1" />
                      준비: <span className="font-bold">{readyCount}</span>개
                    </span>
                    <span className="text-blue-400">
                      선택: <span className="font-bold">{selectedCount}</span>개
                    </span>
                    {doneCount > 0 && (
                      <span className="text-purple-400">
                        완료: <span className="font-bold">{doneCount}</span>개
                      </span>
                    )}
                  </div>
                  <button
                    onClick={handleSelectAll}
                    className="text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    {files.every(f => f.selected) ? '전체 해제' : '전체 선택'}
                  </button>
                </div>

                {/* 파일 테이블 */}
                <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
                  <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-gray-900/50 border-b border-gray-700 sticky top-0">
                        <tr>
                          <th className="px-3 py-3 font-semibold text-gray-400 w-10">선택</th>
                          <th className="px-3 py-3 font-semibold text-gray-400 w-20">분류</th>
                          <th className="px-3 py-3 font-semibold text-gray-400">원본</th>
                          <th className="px-3 py-3 font-semibold text-gray-400">→</th>
                          <th className="px-3 py-3 font-semibold text-gray-400">새 파일명</th>
                          <th className="px-3 py-3 font-semibold text-gray-400 w-20">상태</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700/50">
                        {files.map((file, index) => (
                          <tr key={index} className={`transition-colors ${file.status === 'done' ? 'bg-green-500/5' : 'hover:bg-gray-700/30'}`}>
                            <td className="px-3 py-3">
                              <input
                                type="checkbox"
                                checked={file.selected}
                                onChange={() => handleToggle(index)}
                                disabled={file.status === 'done'}
                                className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 disabled:opacity-50"
                              />
                            </td>
                            <td className="px-3 py-3">
                              {file.category && (
                                <span className={`px-2 py-1 rounded text-xs font-medium ${
                                  file.category === '상품' ? 'bg-green-500/20 text-green-400' :
                                  file.category === '배너' ? 'bg-yellow-500/20 text-yellow-400' :
                                  file.category === '스크린샷' ? 'bg-blue-500/20 text-blue-400' :
                                  file.category === '라벨' ? 'bg-purple-500/20 text-purple-400' :
                                  file.category === '문서' ? 'bg-orange-500/20 text-orange-400' :
                                  file.category === '사진' ? 'bg-pink-500/20 text-pink-400' :
                                  'bg-gray-500/20 text-gray-400'
                                }`}>
                                  {file.category}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-3 text-gray-400 max-w-[180px] truncate" title={file.original_name}>
                              {file.original_name}
                            </td>
                            <td className="px-3 py-3 text-gray-600">→</td>
                            <td className="px-3 py-3 font-medium text-white max-w-[280px]">
                              <div className="truncate" title={file.new_name}>
                                {file.new_name || <span className="text-gray-500">-</span>}
                              </div>
                              {file.brand && (
                                <span className="text-xs text-cyan-400 mt-1 block">
                                  브랜드: {file.brand}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-3">
                              {file.status === 'ready' && (
                                <span className="text-green-400 flex items-center gap-1">
                                  <CheckCircle size={14} /> 준비
                                </span>
                              )}
                              {file.status === 'done' && (
                                <span className="text-purple-400">✓ 완료</span>
                              )}
                              {file.status === 'error' && (
                                <span className="text-red-400 flex items-center gap-1">
                                  <XCircle size={14} /> 오류
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}

            {/* 액션 바 (파일이 있을 때만 표시) */}
            {files.length > 0 && (
              <div className="fixed bottom-8 left-1/2 -translate-x-1/2 bg-gray-800/95 backdrop-blur border border-gray-700 p-3 rounded-2xl shadow-2xl flex gap-3">
                <button 
                  onClick={handleBatchRename}
                  disabled={isProcessing || selectedCount === 0}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8 py-3 rounded-xl font-bold transition-all hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100 flex items-center gap-2"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 size={18} className="animate-spin" /> 처리 중...
                    </>
                  ) : (
                    <>
                      <Wand2 size={18} /> {selectedCount}개 파일 이름 변경
                    </>
                  )}
                </button>
                <button 
                  onClick={handleUndo}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-6 py-3 rounded-xl font-medium transition-colors flex items-center gap-2"
                >
                  <RotateCcw size={18} /> 되돌리기
                </button>
              </div>
            )}
          </div>
        ) : (
          <Organizer />
        )}
      </div>
    </div>
  );
}

export default App;
