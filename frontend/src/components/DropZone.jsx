import React from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud } from 'lucide-react';

const DropZone = ({ onFilesAdded }) => {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: onFilesAdded,
    accept: {
      'image/*': ['.jpg', '.jpeg', '.png', '.webp', '.gif'],
      'application/pdf': ['.pdf']
    }
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 cursor-pointer
        ${isDragActive 
          ? 'border-blue-500 bg-blue-500/10 scale-[1.02]' 
          : 'border-gray-700 hover:border-blue-500 hover:bg-gray-800/50'}
      `}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center justify-center gap-4">
        <div className={`p-5 rounded-2xl transition-colors ${isDragActive ? 'bg-blue-500/20' : 'bg-gray-800'}`}>
          <UploadCloud className={`w-10 h-10 ${isDragActive ? 'text-blue-400' : 'text-gray-400'}`} />
        </div>
        <div>
          <p className="text-lg font-medium text-gray-200">
            {isDragActive ? "파일을 놓으세요..." : "파일을 드래그 & 드롭하세요"}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            또는 클릭하여 파일 선택
          </p>
        </div>
      </div>
    </div>
  );
};

export default DropZone;
