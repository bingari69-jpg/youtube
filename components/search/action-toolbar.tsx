'use client';

import { LayoutGrid, List, Download, Trash2 } from 'lucide-react';
import { KeywordBanner } from './keyword-banner';

export type ViewMode = 'grid' | 'table';

interface ActionToolbarProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  selectedCount: number;
  totalCount: number;
  onCollect?: () => void;
  onRemove?: () => void;
  query?: string;
  onKeywordClick?: (keyword: string) => void;
}

// 액션 툴바: 뷰 토글 + 영상 관리 버튼
export function ActionToolbar({
  viewMode, onViewModeChange, selectedCount, totalCount,
  onCollect, onRemove, query, onKeywordClick,
}: ActionToolbarProps) {
  return (
    <div className="flex items-center justify-between mb-6 gap-6">
      {/* 왼쪽: 결과 수 + AI 키워드 + 뷰 토글 */}
      <div className="flex items-center gap-6 flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-sm font-bold text-gray-400 whitespace-nowrap">
            {totalCount.toLocaleString()}개 결과
          </span>

          {/* 뷰 모드 토글 */}
          <div className="flex items-center bg-white/[0.03] rounded-xl border border-white/5 p-1">
            <button
              onClick={() => onViewModeChange('table')}
              className={`p-1.5 rounded-lg transition-all duration-200 ${
                viewMode === 'table'
                  ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/20'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
              title="테이블 뷰"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => onViewModeChange('grid')}
              className={`p-1.5 rounded-lg transition-all duration-200 ${
                viewMode === 'grid'
                  ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/20'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
              title="그리드 뷰"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* AI 키워드 (인라인) */}
        {query && onKeywordClick && (
          <div className="hidden lg:block flex-1 min-w-0 border-l border-white/5 pl-6">
            <KeywordBanner query={query} onKeywordClick={onKeywordClick} />
          </div>
        )}
      </div>

      {/* 오른쪽: 액션 버튼들 */}
      <div className="flex items-center gap-2">
        <button
          onClick={onCollect}
          disabled={selectedCount === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border border-cl-200 text-cl-600 hover:bg-cl-50 disabled:opacity-30 disabled:cursor-not-allowed"
          title="선택한 영상 수집"
        >
          <Download className="w-4 h-4" />
          <span className="hidden sm:inline">영상수집</span>
        </button>
        <button
          onClick={onRemove}
          disabled={selectedCount === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border border-gray-800 text-gray-400 hover:bg-gray-800 hover:text-red-500 hover:border-red-800 disabled:opacity-30 disabled:cursor-not-allowed"
          title="선택한 영상 제거"
        >
          <Trash2 className="w-4 h-4" />
          <span className="hidden sm:inline">영상제거</span>
        </button>
      </div>
    </div>
  );
}
