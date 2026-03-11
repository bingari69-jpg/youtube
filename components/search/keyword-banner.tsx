'use client';

import { Sparkles } from 'lucide-react';

interface KeywordBannerProps {
  query: string;
  onKeywordClick: (keyword: string) => void;
}

// 관련 키워드 배너 (인라인 버전)
export function KeywordBanner({ query, onKeywordClick }: KeywordBannerProps) {
  const relatedKeywords = generateRelatedKeywords(query);

  if (relatedKeywords.length === 0) return null;

  return (
    <div className="flex items-center gap-4 py-1 flex-1 min-w-0">
      <div className="flex items-center gap-2 text-orange-400 flex-shrink-0 animate-pulse">
        <Sparkles size={14} />
        <span className="text-[10px] font-bold uppercase tracking-tighter italic whitespace-nowrap">AI Recommend</span>
      </div>
      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
        {relatedKeywords.map((kw) => (
          <button
            key={kw}
            onClick={() => onKeywordClick(kw)}
            className="px-3 py-1 bg-white/[0.03] hover:bg-orange-500/10 border border-white/5 hover:border-orange-500/30 rounded-lg text-xs text-gray-400 hover:text-orange-400 transition-all duration-200 whitespace-nowrap"
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  );
}

// 검색어 기반 간단한 관련 키워드 생성
function generateRelatedKeywords(query: string): string[] {
  if (!query.trim()) return [];

  const base = query.trim();
  const suffixes = ['추천', '순위', '리뷰', '비교', '방법', '꿀팁', '2024', '2025'];

  return suffixes
    .slice(0, 6)
    .map((suffix) => `${base} ${suffix}`);
}
