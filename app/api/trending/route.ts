import { NextRequest, NextResponse } from 'next/server';
import { getTrendingChannels } from '@/lib/youtube';

/**
 * 떡상 채널 추천 API
 * GET /api/trending?regionCode=KR
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const regionCode = searchParams.get('regionCode') || 'KR';
    const apiKey = searchParams.get('apiKey') || undefined;

    const channels = await getTrendingChannels(regionCode, 30, apiKey);
    
    return NextResponse.json({ channels });
  } catch (error) {
    console.error('Trending API Error:', error);
    const message = error instanceof Error ? error.message : '실시간 인기 채널을 가져오는데 실패했습니다.';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
