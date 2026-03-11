'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import Image from 'next/image';
import { Header } from '@/components/layout/header';
import { formatCount, formatDuration, type YouTubeVideo, type YouTubeChannel } from '@/lib/youtube';
import {
  calcViewToSubConversion,
  calcDailySubGrowth,
  calcVideoPerformance,
} from '@/lib/channel-metrics';
import { calcContribution, calcPerformance, calcExposure } from '@/lib/metrics';
import { ChannelGradeBadge } from '@/components/channel/channel-grade-badge';
import { ScoreBadge } from '@/components/search/score-badge';
import { getApiKey } from '@/lib/api-key';
import {
  getRegisteredChannels,
  registerChannel,
  unregisterChannel,
  isChannelRegistered,
  type RegisteredChannel,
} from '@/lib/channel-registry';
import { extractTrendKeywords } from '@/lib/utils';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { 
  BrainCircuit, TrendingUp, RefreshCw, Presentation, LayoutList, LayoutGrid, 
  FolderDown, X, Plus, Trash2, Mail, Search, ChevronUp, ChevronDown, SlidersHorizontal 
} from 'lucide-react';
import { exportToPPT } from '@/lib/export-ppt';

// 영상 + 참여율 타입
interface VideoWithEngagement extends YouTubeVideo {
  engagementRate: number;
}

// API 응답 타입
interface ChannelAnalysisData {
  channel: YouTubeChannel;
  videos: VideoWithEngagement[];
  stats: {
    totalViews: number;
    avgViews: number;
    avgLikes: number;
    videoCount: number;
    daysSinceCreation: number;
  };
}

// 정렬 키
type SortKey = 'viewCount' | 'contribution' | 'performance' | 'exposure' | 'publishedAt';
type SortDir = 'asc' | 'desc';
type ViewMode = 'table' | 'grid';

// 다중 정렬 조건
interface SortCriterion {
  key: SortKey;
  dir: SortDir;
}

// sessionStorage 키
const SESSION_KEY = 'cl_channel_analysis_state';

// 저장할 상태 타입
interface ChannelAnalysisState {
  query: string;
  data: ChannelAnalysisData | null;
  sortCriteria: SortCriterion[];
  viewMode: ViewMode;
}

// sessionStorage에서 상태 복원
function loadState(): ChannelAnalysisState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// sessionStorage에 상태 저장
function saveState(state: ChannelAnalysisState): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
  } catch { /* 용량 초과 등 무시 */ }
}

export default function ChannelAnalysisPage() {
  const [query, setQuery] = useState('');
  const [data, setData] = useState<ChannelAnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sortCriteria, setSortCriteria] = useState<SortCriterion[]>([
    { key: 'viewCount', dir: 'desc' },
  ]);
  const [viewMode, setViewMode] = useState<ViewMode>('table');

  // 등록 채널 관련
  const [registeredChannels, setRegisteredChannels] = useState<RegisteredChannel[]>([]);
  const [isRegistered, setIsRegistered] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [collectMessage, setCollectMessage] = useState<string | null>(null);

  // AI 분석 관련
  const [aiInsights, setAiInsights] = useState<string | null>(null);
  const [isAnalyzingAI, setIsAnalyzingAI] = useState(false);
  const [trendKeywords, setTrendKeywords] = useState<Array<{ text: string; value: number }>>([]);

  // 초기 마운트 시 sessionStorage에서 복원
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;

    setRegisteredChannels(getRegisteredChannels());

    const saved = loadState();
    if (saved) {
      setQuery(saved.query);
      setData(saved.data);
      if (saved.sortCriteria) {
        setSortCriteria(saved.sortCriteria);
      }
      setViewMode(saved.viewMode);
    }
  }, []);

  // 상태가 변경될 때마다 sessionStorage에 저장
  useEffect(() => {
    if (!restored.current) return;
    saveState({ query, data, sortCriteria, viewMode });
  }, [query, data, sortCriteria, viewMode]);

  // 현재 채널 등록 여부 체크
  useEffect(() => {
    if (data) {
      setIsRegistered(isChannelRegistered(data.channel.id));
    }
  }, [data]);

  // 채널 검색/분석
  const handleSearch = useCallback(async (searchQuery?: string) => {
    const q = searchQuery ?? query;
    if (!q.trim()) return;

    setLoading(true);
    setError(null);
    setSelectedIds(new Set());

    try {
      const res = await fetch(`/youtube/api/channel-analysis?q=${encodeURIComponent(q)}`, {
        headers: { 'x-youtube-api-key': getApiKey() },
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error);
      setData(json);
      // 키워드 추출
      setTrendKeywords(extractTrendKeywords(json.videos));
      setAiInsights(null); // 새로운 채널 검색 시 기존 AI 인사이트 초기화
    } catch (err) {
      setError(err instanceof Error ? err.message : '채널 분석 중 오류가 발생했습니다.');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  // 최신화 (데이터 새로고침)
  const handleRefresh = () => {
    if (data) {
      handleSearch(data.channel.title);
    }
  };

  // 채널 등록/해제
  const handleToggleRegister = () => {
    if (!data) return;
    if (isRegistered) {
      unregisterChannel(data.channel.id);
      setIsRegistered(false);
    } else {
      registerChannel({
        id: data.channel.id,
        title: data.channel.title,
        thumbnailUrl: data.channel.thumbnailUrl,
        subscriberCount: data.channel.subscriberCount,
        videoCount: data.channel.videoCount,
      });
      setIsRegistered(true);
    }
    setRegisteredChannels(getRegisteredChannels());
  };

  // 등록 채널 선택 (드롭다운에서)
  const handleSelectRegistered = (ch: RegisteredChannel) => {
    setQuery(ch.title);
    setShowDropdown(false);
    handleSearch(ch.title);
  };

  // 등록 채널 삭제 (드롭다운에서)
  const handleRemoveRegistered = (e: React.MouseEvent, channelId: string) => {
    e.stopPropagation();
    unregisterChannel(channelId);
    setRegisteredChannels(getRegisteredChannels());
    if (data && data.channel.id === channelId) {
      setIsRegistered(false);
    }
  };

  // 영상 수집 (선택한 영상들을 localStorage에 저장)
  const handleCollectVideos = () => {
    if (!data || selectedIds.size === 0) return;
    const selected = data.videos.filter((v) => selectedIds.has(v.id));
    // VideoWithChannel 형태로 변환
    const videosToCollect = selected.map((v) => ({
      ...v,
      subscriberCount: data.channel.subscriberCount,
      channelVideoCount: data.channel.videoCount,
      channelThumbnailUrl: data.channel.thumbnailUrl,
    }));

    // collection.ts의 addCollectedVideos 사용
    try {
      const STORAGE_KEY = 'cl_collected_videos';
      const raw = localStorage.getItem(STORAGE_KEY);
      const existing = raw ? JSON.parse(raw) : [];
      const existingIds = new Set(existing.map((v: { id: string }) => v.id));

      const newVideos = videosToCollect
        .filter((v) => !existingIds.has(v.id))
        .map((v) => ({ ...v, collectedAt: new Date().toISOString() }));

      if (newVideos.length === 0) {
        setCollectMessage('이미 수집된 영상입니다.');
      } else {
        const updated = [...newVideos, ...existing];
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        setCollectMessage(`${newVideos.length}개 영상이 수집되었습니다.`);
      }
    } catch {
      setCollectMessage('영상 수집 중 오류가 발생했습니다.');
    }

    // 3초 후 메시지 제거
    setTimeout(() => setCollectMessage(null), 3000);
  };

  // PPT 내보내기
  const handleExportPPT = async () => {
    if (!data) return;
    try {
      await exportToPPT({
        channelTitle: data.channel.title,
        subscriberCount: data.channel.subscriberCount,
        videoCount: data.channel.videoCount,
        totalViews: data.stats.totalViews,
        avgViews: data.stats.avgViews,
        videos: data.videos.map(v => ({
          title: v.title,
          viewCount: v.viewCount,
          contribution: calcContribution(v.viewCount, data.channel.subscriberCount).label,
          performance: calcPerformance(v.viewCount, v.likeCount, v.commentCount, data.channel.subscriberCount).label
        }))
      });
    } catch (err) {
      alert('PPT 내보내기 중 오류가 발생했습니다.');
    }
  };

  // AI 분석 실행
  const handleAIAnalysis = async () => {
    if (!data) return;
    setIsAnalyzingAI(true);
    setAiInsights(null);

    try {
      // 상위 성과 영상 데이터 준비 (조회수 기준 상위 10개)
      const topVideos = [...data.videos]
        .sort((a, b) => b.viewCount - a.viewCount)
        .slice(0, 10)
        .map(v => ({
          title: v.title,
          viewCount: v.viewCount,
          contribution: calcContribution(v.viewCount, data.channel.subscriberCount).value
        }));

      const res = await fetch('/youtube/api/ai-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'channel',
          channelTitle: data.channel.title,
          videos: topVideos,
          apiKey: getApiKey()
        })
      });

      const json = await res.json();
      if (!res.ok) throw new Error(json.error);
      setAiInsights(json.insights);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'AI 분석 중 오류가 발생했습니다.');
    } finally {
      setIsAnalyzingAI(false);
    }
  };

  // 정렬 클릭 핸들러 (3단계 토글)
  // 1) 없으면 → desc(↑ 높은순) 추가
  // 2) desc → asc(↓ 낮은순) 전환
  // 3) asc → 해당 조건 제거
  const handleSort = useCallback((key: SortKey) => {
    setSortCriteria((prev) => {
      const existingIdx = prev.findIndex((c) => c.key === key);
      if (existingIdx < 0) {
        return [...prev, { key, dir: 'desc' }];
      }
      if (prev[existingIdx].dir === 'desc') {
        const updated = [...prev];
        updated[existingIdx] = { ...updated[existingIdx], dir: 'asc' };
        return updated;
      }
      const filtered = prev.filter((c) => c.key !== key);
      return filtered.length > 0 ? filtered : [{ key: 'viewCount', dir: 'desc' }];
    });
  }, []);

  // 정렬 조건 제거
  const removeCriterion = useCallback((key: SortKey) => {
    setSortCriteria((prev) => {
      const filtered = prev.filter((c) => c.key !== key);
      return filtered.length > 0 ? filtered : [{ key: 'viewCount', dir: 'desc' }];
    });
  }, []);

  // 정렬 초기화
  const resetSort = useCallback(() => {
    setSortCriteria([{ key: 'viewCount', dir: 'desc' }]);
  }, []);

  // 해당 컬럼의 정렬 정보 조회
  const getSortInfo = (key: SortKey) => {
    const idx = sortCriteria.findIndex((c) => c.key === key);
    if (idx < 0) return null;
    return { order: idx + 1, dir: sortCriteria[idx].dir };
  };

  // 체크박스 토글
  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleToggleSelectAll = () => {
    if (!data) return;
    if (selectedIds.size === data.videos.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(data.videos.map((v) => v.id)));
    }
  };

  // 영상의 정렬 값 가져오기
  const getSortValue = useCallback((video: VideoWithEngagement, key: SortKey): number => {
    if (!data) return 0;
    switch (key) {
      case 'viewCount': return video.viewCount;
      case 'contribution': return calcContribution(video.viewCount, data.channel.subscriberCount).value;
      case 'performance': return calcPerformance(video.viewCount, video.likeCount, video.commentCount, data.channel.subscriberCount).value;
      case 'exposure': return calcExposure({ title: video.title, query: '', viewCount: video.viewCount, likeCount: video.likeCount, commentCount: video.commentCount, subscriberCount: data.channel.subscriberCount, publishedAt: video.publishedAt, channelVideoCount: data.channel.videoCount }).percent;
      case 'publishedAt': return new Date(video.publishedAt).getTime();
      default: return 0;
    }
  }, [data]);

  // 정렬된 영상 목록
  // - 단일 정렬: 해당 기준으로 직접 정렬
  // - 다중 정렬: 각 기준값을 0~1로 정규화한 뒤 합산하여 종합 점수로 정렬
  const sortedVideos = data
    ? (() => {
        const list = [...data.videos];

        if (sortCriteria.length === 1) {
          const { key, dir } = sortCriteria[0];
          const mult = dir === 'asc' ? 1 : -1;
          return list.sort((a, b) => (getSortValue(a, key) - getSortValue(b, key)) * mult);
        }

        // 다중 정렬: 가중 평균 합산 방식
        const ranges = sortCriteria.map(({ key }) => {
          const vals = list.map((v) => getSortValue(v, key));
          const min = Math.min(...vals);
          const max = Math.max(...vals);
          return { min, range: max - min };
        });

        const scores = new Map<string, number>();
        for (const video of list) {
          let total = 0;
          sortCriteria.forEach(({ key, dir }, i) => {
            const val = getSortValue(video, key);
            const norm = ranges[i].range > 0 ? (val - ranges[i].min) / ranges[i].range : 0;
            total += dir === 'desc' ? norm : 1 - norm;
          });
          scores.set(video.id, total);
        }

        return list.sort((a, b) => {
          const diff = (scores.get(b.id) ?? 0) - (scores.get(a.id) ?? 0);
          if (diff !== 0) return diff;
          return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime();
        });
      })()
    : [];

  // 날짜 포맷
  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${String(d.getFullYear()).slice(2)}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
  };

  const formatFullDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
  };

  const allSelected = data ? data.videos.length > 0 && selectedIds.size === data.videos.length : false;

  const columns: Array<{ key: SortKey; label: string }> = [
    { key: 'viewCount', label: '조회수' },
    { key: 'contribution', label: '기여도' },
    { key: 'performance', label: '성과도' },
    { key: 'exposure', label: '노출 확률' },
    { key: 'publishedAt', label: '게시일' },
  ];

  const labelMap: Record<SortKey, string> = {
    viewCount: '조회수',
    contribution: '기여도',
    performance: '성과도',
    exposure: '노출확률',
    publishedAt: '게시일',
  };

  return (
    <div className="min-h-screen bg-gray-950">
      <Header />

      <main className="max-w-[1400px] mx-auto px-4 py-6">
        {/* 검색바 영역 */}
        <div className="flex gap-3 mb-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="채널명 또는 채널 URL 입력"
              className="w-full pl-12 pr-4 py-3 bg-gray-950 border border-gray-800 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cl-500 focus:ring-1 focus:ring-cl-500 transition-colors"
            />
          </div>

          <button
            onClick={() => handleSearch()}
            disabled={loading || !query.trim()}
            className="cl-search-btn"
          >
            {loading ? '분석 중...' : '검색'}
          </button>
        </div>

        {/* 채널 태그 + 등록 채널 드롭다운 + 필터 */}
        <div className="flex items-center gap-2 mb-6">
          {/* 현재 분석 중인 채널 태그 */}
          {data && (
            <button
              onClick={handleToggleRegister}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                isRegistered
                  ? 'bg-emerald-500 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {isRegistered ? (
                <>
                  <span className="w-2 h-2 bg-gray-950 rounded-full" />
                  {data.channel.title} ({data.channel.videoCount})
                  <X className="w-3.5 h-3.5 ml-0.5" />
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5" />
                  채널 등록
                </>
              )}
            </button>
          )}

          {/* 등록 채널 드롭다운 */}
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-950 border border-gray-800 rounded-full text-sm text-gray-400 hover:border-gray-700 transition-colors"
            >
              등록 채널
              <ChevronDown className="w-3.5 h-3.5" />
            </button>

            {showDropdown && (
              <>
                {/* 배경 클릭시 닫기 */}
                <div className="fixed inset-0 z-10" onClick={() => setShowDropdown(false)} />
                <div className="absolute top-full left-0 mt-1 w-72 bg-gray-950 border border-gray-800 rounded-lg shadow-lg z-20 py-1 max-h-80 overflow-y-auto">
                  {registeredChannels.length === 0 ? (
                    <div className="px-4 py-6 text-center text-sm text-gray-400">
                      등록된 채널이 없습니다.
                    </div>
                  ) : (
                    registeredChannels.map((ch) => (
                      <button
                        key={ch.id}
                        onClick={() => handleSelectRegistered(ch)}
                        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800 transition-colors text-left"
                      >
                        <Image
                          src={ch.thumbnailUrl}
                          alt={ch.title}
                          width={32}
                          height={32}
                          className="rounded-full flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-gray-100 font-medium truncate">{ch.title}</p>
                          <p className="text-xs text-gray-400">{formatCount(ch.subscriberCount)}명 / {ch.videoCount}개</p>
                        </div>
                        <button
                          onClick={(e) => handleRemoveRegistered(e, ch.id)}
                          className="p-1 text-gray-400 hover:text-red-400 transition-colors flex-shrink-0"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </button>
                    ))
                  )}
                </div>
              </>
            )}
          </div>

          {/* 필터 버튼 */}
          <button className="flex items-center gap-1 px-3 py-1.5 bg-gray-950 border border-gray-800 rounded-full text-sm text-gray-400 hover:text-gray-300 transition-colors">
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* 에러 표시 */}
        {error && (
          <div className="mb-6 p-4 bg-red-950 border border-red-800 rounded-lg text-red-400">
            {error}
          </div>
        )}

        {/* 수집 메시지 토스트 */}
        {collectMessage && (
          <div className="fixed top-20 right-6 z-50 px-4 py-3 bg-gray-900 text-white text-sm rounded-lg shadow-lg animate-pulse">
            {collectMessage}
          </div>
        )}

        {/* 채널 분석 결과 */}
        {data && (
          <>
            {/* 채널 프로필 카드 */}
            <div className="bg-gray-950 border border-gray-800 rounded-xl mb-6 shadow-sm overflow-hidden">
              {/* 채널 이름 + 썸네일 */}
              <div className="flex items-center gap-4 p-5 pb-0">
                <Image
                  src={data.channel.thumbnailUrl}
                  alt={data.channel.title}
                  width={56}
                  height={56}
                  className="rounded-full"
                />
                <h2 className="text-lg font-bold text-gray-100">{data.channel.title}</h2>
              </div>

              {/* 통계 그리드 (2행 x 3열) */}
              <div className="grid grid-cols-3 gap-px bg-gray-800 mx-5 mt-4 rounded-lg overflow-hidden border border-gray-800">
                <div className="bg-gray-950 p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-400">구독자</span>
                  <span className="text-sm font-bold text-gray-100">{formatCount(data.channel.subscriberCount)}명</span>
                </div>
                <div className="bg-gray-950 p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-400">총 영상수</span>
                  <span className="text-sm font-bold text-gray-100">{data.channel.videoCount.toLocaleString()}개</span>
                </div>
                <div className="bg-gray-950 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">채널 개설</span>
                    <div className="text-right">
                      <span className="text-xs text-gray-400 block">{formatFullDate(data.channel.publishedAt)}</span>
                      <span className="text-sm font-bold text-gray-100">{data.stats.daysSinceCreation}일 경과</span>
                    </div>
                  </div>
                </div>
                <div className="bg-gray-950 p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-400">누적 조회수</span>
                  <span className="text-sm font-bold text-gray-100">{formatCount(data.channel.viewCount)}회</span>
                </div>
                <div className="bg-gray-950 p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-400">평균 좋아요</span>
                  <span className="text-sm font-bold text-gray-100">{formatCount(data.stats.avgLikes)}개</span>
                </div>
                <div className="bg-gray-950 p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-400">평균 조회수</span>
                  <span className="text-sm font-bold text-gray-100">{formatCount(data.stats.avgViews)}회</span>
                </div>
              </div>

              {/* 채널 분석 지표 (3개 배지) */}
              <div className="grid grid-cols-3 gap-px bg-gray-800 mx-5 mt-3 mb-5 rounded-lg overflow-hidden border border-gray-800">
                {(() => {
                  const viewToSub = calcViewToSubConversion(data.channel.subscriberCount, data.channel.viewCount);
                  const dailySub = calcDailySubGrowth(data.channel.subscriberCount, data.channel.publishedAt);
                  const videoPerf = calcVideoPerformance(data.channel.viewCount, data.channel.videoCount, data.channel.subscriberCount);
                  return (
                    <>
                      <div className="bg-gray-950 p-4 flex items-center justify-between">
                        <span className="text-sm text-gray-400">조회수대비 구독전환</span>
                        <ChannelGradeBadge grade={viewToSub.grade} label={viewToSub.label} dots={viewToSub.dots} />
                      </div>
                      <div className="bg-gray-950 p-4 flex items-center justify-between">
                        <span className="text-sm text-gray-400">일평균 구독전환</span>
                        <ChannelGradeBadge grade={dailySub.grade} label={dailySub.label} dots={dailySub.dots} />
                      </div>
                      <div className="bg-gray-950 p-4 flex items-center justify-between">
                        <span className="text-sm text-gray-400">영상성과</span>
                        <ChannelGradeBadge grade={videoPerf.grade} label={videoPerf.label} dots={videoPerf.dots} />
                      </div>
                    </>
                  );
                })()}
              </div>

              {/* 채널 연락처 버튼 */}
              <div className="px-5 pb-5">
                <button className="flex items-center gap-2 px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-sm text-gray-400 hover:text-gray-300 transition-colors">
                  <Mail className="w-4 h-4" />
                  채널 연락처
                </button>
              </div>
            </div>

            {/* AI 인사이트 & 성과 차트 영역 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              {/* 성과 추이 차트 */}
              <div className="lg:col-span-2 bg-gray-950 border border-gray-800 rounded-xl p-5">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-gray-100 font-bold flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-cl-500" />
                    최근 영상 성과 추이
                  </h3>
                  <div className="text-xs text-gray-400">최근 20개 영상 기준</div>
                </div>
                <div className="h-[280px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[...data.videos].slice(0, 20).reverse()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                      <XAxis 
                        dataKey="publishedAt" 
                        hide 
                      />
                      <YAxis 
                        stroke="#9ca3af" 
                        fontSize={12} 
                        tickFormatter={(val) => formatCount(val)}
                      />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
                        itemStyle={{ color: '#f3f4f6' }}
                        labelStyle={{ display: 'none' }}
                        formatter={(value: any) => [formatCount(value), '조회수']}
                      />
                      <Bar dataKey="viewCount" radius={[4, 4, 0, 0]}>
                        {data.videos.slice(0, 20).reverse().map((entry, index) => (
                          <Cell 
                            key={`cell-${index}`} 
                            fill={calcContribution(entry.viewCount, data.channel.subscriberCount).value > 100 ? '#f59e0b' : '#3b82f6'} 
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-4 flex justify-center gap-6">
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <div className="w-3 h-3 bg-blue-500 rounded-sm" /> 보통 성과
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <div className="w-3 h-3 bg-amber-500 rounded-sm" /> 고성과 (기여도 100%+)
                  </div>
                </div>
              </div>

              {/* 트렌드 키워드 */}
              <div className="bg-gray-950 border border-gray-800 rounded-xl p-5">
                <h3 className="text-gray-100 font-bold flex items-center gap-2 mb-6">
                  <TrendingUp className="w-5 h-5 text-emerald-500" />
                  핵심 키워드 트렌드
                </h3>
                <div className="flex flex-wrap gap-2">
                  {trendKeywords.map((kw, i) => (
                    <div 
                      key={i}
                      className="px-3 py-1.5 bg-gray-900 border border-gray-800 rounded-lg flex items-center gap-2 group hover:border-cl-500 transition-colors"
                    >
                      <span className="text-sm text-gray-200">{kw.text}</span>
                      <span className="text-xs text-gray-500 group-hover:text-cl-500">{kw.value}</span>
                    </div>
                  ))}
                  {trendKeywords.length === 0 && (
                    <div className="text-center py-10 text-gray-500 w-full text-sm">키워드 분석 중...</div>
                  )}
                </div>
              </div>
            </div>

            {/* AI 인사이트 상세 영역 */}
            <div className="bg-gray-950 border border-gray-800 rounded-xl mb-8 overflow-hidden">
              <div className="p-5 border-b border-gray-800 flex items-center justify-between">
                <h3 className="text-gray-100 font-bold flex items-center gap-2">
                  <BrainCircuit className="w-5 h-5 text-cl-500" />
                  Gemini AI 채널 성장 분석
                </h3>
                <button
                  onClick={handleAIAnalysis}
                  disabled={isAnalyzingAI}
                  className="px-4 py-2 bg-cl-500 hover:bg-cl-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                  {isAnalyzingAI ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      AI 분석 중...
                    </>
                  ) : (
                    <>
                      <BrainCircuit className="w-4 h-4" />
                      AI 인사이트 도출
                    </>
                  )}
                </button>
              </div>
              <div className="p-6">
                {aiInsights ? (
                  <div className="prose prose-invert max-w-none text-sm leading-relaxed text-gray-300">
                    <div className="whitespace-pre-wrap">{aiInsights}</div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <BrainCircuit className="w-12 h-12 mx-auto mb-4 opacity-20" />
                    <p>AI가 채널의 성공 요인과 향후 전략을 분석해 드립니다.</p>
                    <p className="text-xs mt-1">상단 버튼을 눌러 분석을 시작하세요.</p>
                  </div>
                )}
              </div>
            </div>

            {/* 액션 바 (뷰토글 + 영상수집 + 최신화 + 카운트) */}
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-400">
                영상 {data.stats.videoCount}개
                {selectedIds.size > 0 && (
                  <span className="text-cl-500 ml-2 font-medium">{selectedIds.size}개 선택</span>
                )}
              </span>

              <div className="flex items-center gap-2">
                {/* 뷰 토글 */}
                <div className="flex items-center border border-gray-800 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setViewMode('table')}
                    className={`p-2 transition-colors ${viewMode === 'table' ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:text-gray-300'}`}
                  >
                    <LayoutList className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setViewMode('grid')}
                    className={`p-2 transition-colors ${viewMode === 'grid' ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:text-gray-300'}`}
                  >
                    <LayoutGrid className="w-4 h-4" />
                  </button>
                </div>

                {/* 영상 수집 버튼 */}
                <button
                  onClick={handleCollectVideos}
                  disabled={selectedIds.size === 0}
                  className="flex items-center gap-1.5 px-3 py-2 border border-gray-800 rounded-lg text-sm text-gray-400 hover:border-gray-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <FolderDown className="w-4 h-4" />
                  영상 수집
                </button>

                {/* PPT 내보내기 버튼 */}
                <button
                  onClick={handleExportPPT}
                  className="flex items-center gap-1.5 px-3 py-2 border border-blue-900/50 bg-blue-900/10 rounded-lg text-sm text-blue-400 hover:bg-blue-900/20 transition-colors"
                >
                  <Presentation className="w-4 h-4" />
                  PPT 리포트
                </button>

                {/* 최신화 버튼 */}
                <button
                  onClick={handleRefresh}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-2 border border-gray-800 rounded-lg text-sm text-gray-400 hover:border-gray-700 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                  최신화
                </button>

                {/* 영상 카운트 */}
                <span className="text-sm text-gray-400 tabular-nums ml-1">
                  {data.videos.length}
                </span>
              </div>
            </div>

            {/* 영상 테이블 뷰 */}
            {viewMode === 'table' && (
              <div>
                {/* 정렬 조건 태그 */}
                <div className="flex items-center gap-2 mb-3 px-1 overflow-x-auto whitespace-nowrap">
                  <span className="text-xs text-gray-400 flex-shrink-0">정렬:</span>
                  {sortCriteria.map((c, idx) => (
                    <span
                      key={c.key}
                      className="inline-flex items-center gap-1 px-2 py-1 bg-cl-50 border border-cl-200 rounded-full text-xs text-cl-700 font-medium flex-shrink-0"
                    >
                      <span className="w-4 h-4 bg-cl-500 text-white rounded-full text-[10px] flex items-center justify-center font-bold">
                        {idx + 1}
                      </span>
                      {labelMap[c.key]}{c.dir === 'desc' ? '↑' : '↓'}
                      <button
                        onClick={() => removeCriterion(c.key)}
                        className="ml-0.5 text-cl-400 hover:text-cl-600 transition-colors"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  <button
                    onClick={resetSort}
                    className="text-xs text-gray-400 hover:text-gray-300 transition-colors flex-shrink-0"
                  >
                    초기화
                  </button>
                  <span className="text-[10px] text-gray-400 ml-auto flex-shrink-0">클릭: 추가(↑) → 전환(↓) → 제거</span>
                </div>

                <div className="bg-gray-950 border border-gray-800 rounded-lg overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1100px]">
                    <thead>
                      <tr className="text-[11px] uppercase tracking-wider text-gray-400 border-b border-gray-800 bg-gray-900">
                        <th className="w-12 py-3.5 pl-4">
                          <input
                            type="checkbox"
                            checked={allSelected}
                            onChange={handleToggleSelectAll}
                            className="w-4 h-4 rounded border-gray-700 accent-cl-500 cursor-pointer"
                          />
                        </th>
                        <th className="text-left py-3.5 pl-2 font-semibold min-w-[100px]">썸네일</th>
                        <th className="text-left py-3.5 pl-2 font-semibold min-w-[300px]">제목</th>
                        {columns.map((col) => {
                          const sortInfo = getSortInfo(col.key);
                          const isActive = sortInfo !== null;
                          return (
                            <th
                              key={col.key}
                              className={`py-3.5 px-3 cursor-pointer select-none hover:text-gray-200 transition-colors font-semibold text-center whitespace-nowrap min-w-[90px] ${
                                isActive ? 'text-gray-100' : ''
                              } ${col.key === 'exposure' ? 'bg-cl-50' : ''}`}
                              onClick={() => handleSort(col.key)}
                              title="클릭: 추가(↑) → 전환(↓) → 제거"
                            >
                              <span className="inline-flex items-center gap-1 whitespace-nowrap">
                                {col.label}
                                {isActive ? (
                                  <span className="inline-flex items-center gap-0.5">
                                    <span className="w-4 h-4 bg-cl-500 text-white rounded-full text-[9px] flex items-center justify-center font-bold leading-none">
                                      {sortInfo.order}
                                    </span>
                                    {sortInfo.dir === 'desc'
                                      ? <ChevronUp className="w-3.5 h-3.5 text-cl-500" />
                                      : <ChevronDown className="w-3.5 h-3.5 text-cl-500" />
                                    }
                                  </span>
                                ) : (
                                  <span className="inline-flex flex-col -space-y-1">
                                    <ChevronUp className="w-3 h-3 text-gray-400" />
                                    <ChevronDown className="w-3 h-3 text-gray-400" />
                                  </span>
                                )}
                              </span>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>

                    <tbody>
                      {sortedVideos.map((video, idx) => {
                        const contribution = calcContribution(video.viewCount, data.channel.subscriberCount);
                        const performance = calcPerformance(video.viewCount, video.likeCount, video.commentCount, data.channel.subscriberCount);
                        const exposure = calcExposure({
                          title: video.title, query: '',
                          viewCount: video.viewCount, likeCount: video.likeCount,
                          commentCount: video.commentCount, subscriberCount: data.channel.subscriberCount,
                          publishedAt: video.publishedAt, channelVideoCount: data.channel.videoCount,
                        });
                        const isSelected = selectedIds.has(video.id);
                        const rowBg = isSelected
                          ? 'bg-cl-50'
                          : idx % 2 === 1
                            ? 'bg-gray-800/30'
                            : '';

                        return (
                          <tr
                            key={video.id}
                            className={`border-b border-gray-800 hover:bg-gray-800 transition-colors ${rowBg}`}
                          >
                            <td className="py-4 pl-4">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => handleToggleSelect(video.id)}
                                className="w-4 h-4 rounded border-gray-700 accent-cl-500 cursor-pointer"
                              />
                            </td>
                            <td className="py-4 pl-2">
                              <a
                                href={`https://www.youtube.com/watch?v=${video.id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block relative w-[120px] aspect-video flex-shrink-0"
                              >
                                <Image
                                  src={video.thumbnailUrl}
                                  alt={video.title}
                                  width={120}
                                  height={68}
                                  className="rounded object-cover w-full h-full"
                                />
                                {video.durationSeconds > 0 && (
                                  <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[10px] px-1 py-0.5 rounded">
                                    {formatDuration(video.durationSeconds)}
                                  </span>
                                )}
                              </a>
                            </td>
                            <td className="py-4 pl-2 pr-4">
                              <a
                                href={`https://www.youtube.com/watch?v=${video.id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[13px] text-gray-100 hover:text-cl-500 font-medium transition-colors line-clamp-2"
                              >
                                {video.title}
                              </a>
                            </td>
                            <td className="py-4 px-3 text-center">
                              <span className="text-[13px] text-gray-100 font-medium tabular-nums">
                                {video.viewCount.toLocaleString()}
                              </span>
                            </td>
                            <td className="py-4 px-3 text-center">
                              <ScoreBadge grade={contribution.grade} label={contribution.label} />
                            </td>
                            <td className="py-4 px-3 text-center">
                              <ScoreBadge grade={performance.grade} label={performance.label} />
                            </td>
                            <td className="py-4 px-3 text-center bg-cl-50/30">
                              <ExposureBar percent={exposure.percent} label={exposure.label} />
                            </td>
                            <td className="py-4 px-3 text-center">
                              <span className="text-[13px] text-gray-400 tabular-nums">
                                {formatDate(video.publishedAt)}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              </div>
            )}

            {/* 그리드 뷰 */}
            {viewMode === 'grid' && (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {sortedVideos.map((video) => {
                  const contribution = calcContribution(video.viewCount, data.channel.subscriberCount);
                  const isSelected = selectedIds.has(video.id);

                  return (
                    <div
                      key={video.id}
                      className={`bg-gray-950 border rounded-lg overflow-hidden transition-colors cursor-pointer ${
                        isSelected ? 'border-cl-400 ring-1 ring-cl-200' : 'border-gray-800 hover:border-gray-700'
                      }`}
                      onClick={() => handleToggleSelect(video.id)}
                    >
                      <div className="relative aspect-video">
                        <Image
                          src={video.thumbnailUrl}
                          alt={video.title}
                          fill
                          className="object-cover"
                        />
                        {video.durationSeconds > 0 && (
                          <span className="absolute bottom-1 right-1 bg-black/80 text-white text-[10px] px-1 py-0.5 rounded">
                            {formatDuration(video.durationSeconds)}
                          </span>
                        )}
                        {/* 선택 체크 */}
                        <div className="absolute top-2 left-2">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleSelect(video.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="w-4 h-4 rounded border-gray-700 accent-cl-500 cursor-pointer"
                          />
                        </div>
                      </div>
                      <div className="p-3">
                        <a
                          href={`https://www.youtube.com/watch?v=${video.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-[13px] text-gray-100 hover:text-cl-500 font-medium line-clamp-2 transition-colors"
                        >
                          {video.title}
                        </a>
                        <div className="flex items-center justify-between mt-2">
                          <span className="text-xs text-gray-400 tabular-nums">
                            {formatCount(video.viewCount)}회
                          </span>
                          <ScoreBadge grade={contribution.grade} label={contribution.label} />
                        </div>
                        <span className="text-xs text-gray-400 mt-1 block">
                          {formatDate(video.publishedAt)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* 로딩 스켈레톤 */}
        {loading && (
          <div className="space-y-6">
            <div className="bg-gray-950 border border-gray-800 rounded-xl p-6 animate-pulse">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-14 h-14 bg-gray-700 rounded-full" />
                <div className="h-5 bg-gray-700 rounded w-40" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-14 bg-gray-800 rounded" />
                ))}
              </div>
              <div className="grid grid-cols-3 gap-3 mt-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-14 bg-gray-800 rounded" />
                ))}
              </div>
            </div>
            <div className="bg-gray-950 border border-gray-800 rounded-lg overflow-hidden">
              <div className="p-4 space-y-0">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4 py-4 border-b border-gray-800 animate-pulse">
                    <div className="w-4 h-4 bg-gray-700 rounded" />
                    <div className="w-[120px] h-[68px] bg-gray-700 rounded flex-shrink-0" />
                    <div className="flex-1 h-4 bg-gray-700 rounded w-1/2" />
                    <div className="h-4 bg-gray-700 rounded w-16" />
                    <div className="h-4 bg-gray-700 rounded w-16" />
                    <div className="h-4 bg-gray-700 rounded w-12" />
                    <div className="h-4 bg-gray-700 rounded w-12" />
                    <div className="h-4 bg-gray-700 rounded w-16" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 초기 상태 */}
        {!data && !loading && !error && (
          <div className="text-center py-20 text-gray-400">
            <div className="text-6xl mb-4">📊</div>
            <p className="text-lg text-gray-400">YouTube 채널을 분석해보세요</p>
            <p className="text-sm mt-2">채널명이나 URL을 입력하면 구독자, 영상 성과, 성장 지표를 한눈에 볼 수 있습니다.</p>
            {registeredChannels.length > 0 && (
              <div className="mt-8">
                <p className="text-sm text-gray-400 mb-3">등록된 채널</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {registeredChannels.map((ch) => (
                    <button
                      key={ch.id}
                      onClick={() => { setQuery(ch.title); handleSearch(ch.title); }}
                      className="flex items-center gap-2 px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-sm text-gray-400 hover:border-cl-300 hover:text-cl-600 transition-colors"
                    >
                      <Image
                        src={ch.thumbnailUrl}
                        alt={ch.title}
                        width={24}
                        height={24}
                        className="rounded-full"
                      />
                      {ch.title}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

// 노출확률 프로그레스 바 (채널분석용)
function ExposureBar({ percent, label }: { percent: number; label: string }) {
  const barColor =
    percent >= 75 ? 'bg-emerald-500' :
    percent >= 50 ? 'bg-sky-500' :
    percent >= 25 ? 'bg-amber-500' :
    'bg-red-400';

  return (
    <div className="flex flex-col items-center gap-1 min-w-[70px]">
      <span className="text-[13px] font-semibold text-gray-100 tabular-nums">{percent}%</span>
      <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${barColor} transition-all`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-[10px] text-gray-400 font-medium">{label}</span>
    </div>
  );
}
