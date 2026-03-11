'use client';

import type { VideoType } from '@/lib/youtube';

interface SearchFiltersProps {
  order: string;
  setOrder: (v: string) => void;
  duration: string;
  setDuration: (v: string) => void;
  dateRange: string;
  setDateRange: (v: string) => void;
  country: string;
  setCountry: (v: string) => void;
  videoType: VideoType;
  setVideoType: (v: VideoType) => void;
  onFilterChange: () => void;
}

// 검색 필터 패널
export function SearchFilters({
  order, setOrder,
  duration, setDuration,
  dateRange, setDateRange,
  country, setCountry,
  videoType, setVideoType,
  onFilterChange,
}: SearchFiltersProps) {

  const handleChange = (setter: (v: string) => void, value: string) => {
    setter(value);
    setTimeout(onFilterChange, 0);
  };

  return (
    <div className="glass rounded-[24px] p-6 mb-8 border border-white/5 shadow-2xl">
      <div className="flex flex-wrap gap-8 items-end">
        {/* 정렬 레벨 */}
        <FilterSelect
          label="Sort By"
          value={order}
          onChange={(v) => handleChange(setOrder, v)}
          options={[
            { value: 'relevance', label: '관련성' },
            { value: 'viewCount', label: '조회수' },
            { value: 'date', label: '최신순' },
            { value: 'rating', label: '평점순' },
          ]}
        />

        {/* 길이 */}
        <FilterSelect
          label="Duration"
          value={duration}
          onChange={(v) => handleChange(setDuration, v)}
          options={[
            { value: 'any', label: '전체 길이' },
            { value: 'short', label: '4분 미만' },
            { value: 'medium', label: '4~20분' },
            { value: 'long', label: '20분 이상' },
          ]}
        />

        {/* 업로드 날짜 */}
        <FilterSelect
          label="Upload Date"
          value={dateRange}
          onChange={(v) => handleChange(setDateRange, v)}
          options={[
            { value: 'all', label: '전체 기간' },
            { value: '1h', label: '1시간 이내' },
            { value: '1d', label: '오늘' },
            { value: '7d', label: '이번 주' },
            { value: '30d', label: '이번 달' },
            { value: '1y', label: '올해' },
          ]}
        />

        {/* 국가별 */}
        <FilterSelect
          label="Region"
          value={country}
          onChange={(v) => handleChange(setCountry, v)}
          options={[
            { value: 'KR', label: '한국 🇰🇷' },
            { value: 'US', label: '미국 🇺🇸' },
            { value: 'JP', label: '일본 🇯🇵' },
            { value: 'all', label: '전체 🌏' },
          ]}
        />

        {/* 영상 유형 선택 도구 */}
        <div className="space-y-2">
          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest pl-1">Content Type</label>
          <div className="flex p-1 bg-white/[0.03] border border-white/10 rounded-xl overflow-hidden backdrop-blur-md">
            {([
              { value: 'all', label: '전체' },
              { value: 'long', label: '롱폼' },
              { value: 'shorts', label: '숏츠' },
            ] as const).map((opt) => (
              <button
                key={opt.value}
                onClick={() => setVideoType(opt.value)}
                className={`px-5 py-2 text-xs font-bold transition-all duration-300 rounded-lg ${videoType === opt.value
                  ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/20'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                  }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// 개별 필터 셀렉트
function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div className="space-y-2">
      <label className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest pl-1">{label}</label>
      <div className="relative group">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="bg-white/[0.03] border border-white/10 rounded-xl px-5 py-2.5 text-xs font-bold text-gray-200 outline-none focus:border-orange-500/50 focus:ring-4 focus:ring-orange-500/10 transition-all appearance-none cursor-pointer min-w-[140px]"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-neutral-900 text-gray-200">
              {opt.label}
            </option>
          ))}
        </select>
        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-gray-600 group-hover:text-orange-500 transition-colors">
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>
    </div>
  );
}
