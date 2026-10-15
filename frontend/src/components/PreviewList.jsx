import React from 'react';
import { Check, AlertCircle, Loader2 } from 'lucide-react';

const PreviewList = ({ files, onToggle, onRenameChange }) => {
  if (files.length === 0) return null;

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-900/50 border-b border-gray-700">
            <tr>
              <th className="px-6 py-4 font-semibold text-gray-400 w-12">
                <input type="checkbox" className="rounded border-gray-600 bg-gray-700" checked readOnly />
              </th>
              <th className="px-6 py-4 font-semibold text-gray-400">원본 파일명</th>
              <th className="px-6 py-4 font-semibold text-gray-400">새 파일명</th>
              <th className="px-6 py-4 font-semibold text-gray-400">태그</th>
              <th className="px-6 py-4 font-semibold text-gray-400">상태</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {files.map((file, index) => (
              <tr key={index} className="hover:bg-gray-700/30 transition-colors">
                <td className="px-6 py-4">
                  <input
                    type="checkbox"
                    checked={file.selected !== false}
                    onChange={() => onToggle(index)}
                    className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                  />
                </td>
                <td className="px-6 py-4 text-gray-400 max-w-xs truncate" title={file.originalName}>
                  {file.originalName}
                </td>
                <td className="px-6 py-4 font-medium text-white">
                  <div className="flex items-center gap-2">
                     {file.newName || <span className="text-gray-500">분석 중...</span>}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {file.userTokens?.map((t, i) => (
                      <span key={`u-${i}`} className="px-2 py-0.5 bg-gray-700 text-gray-300 rounded text-xs">{t}</span>
                    ))}
                    {file.tags?.map((t, i) => (
                      <span key={`a-${i}`} className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs">{t}</span>
                    ))}
                    {file.specs?.map((t, i) => (
                      <span key={`s-${i}`} className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">{t}</span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4">
                  {file.status === 'pending' && <span className="text-gray-500">대기 중</span>}
                  {file.status === 'analyzing' && (
                    <span className="text-blue-400 flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" /> 분석 중...
                    </span>
                  )}
                  {file.status === 'ready' && (
                    <span className="text-green-400 flex items-center gap-1">
                      <Check size={14}/> 준비 완료
                    </span>
                  )}
                  {file.status === 'done' && <span className="text-gray-400">✓ 완료</span>}
                  {file.status === 'error' && (
                    <span className="text-red-400 flex items-center gap-1">
                      <AlertCircle size={14}/> 오류
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PreviewList;
