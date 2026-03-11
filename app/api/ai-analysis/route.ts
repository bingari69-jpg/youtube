import { NextRequest, NextResponse } from 'next/server';
import { analyzeChannelInsights, summarizeVideoContent } from '@/lib/gemini';

/**
 * AI 분석 API
 * GET /api/ai-analysis?type=channel&channelTitle=이름&videos=[]
 */
export async function POST(request: NextRequest) {
  try {
    const { type, channelTitle, videos, videoTitle, description, apiKey } = await request.json();

    if (type === 'channel') {
      if (!channelTitle || !videos || !Array.isArray(videos)) {
        return NextResponse.json({ error: '채널명과 영상 목록이 누락되었습니다.' }, { status: 400 });
      }
      const insights = await analyzeChannelInsights(channelTitle, videos, apiKey);
      return NextResponse.json({ insights });
    }

    if (type === 'video') {
      if (!videoTitle || !description) {
        return NextResponse.json({ error: '영상 제목과 설명이 누락되었습니다.' }, { status: 400 });
      }
      const summary = await summarizeVideoContent(videoTitle, description, apiKey);
      return NextResponse.json({ summary });
    }

    return NextResponse.json({ error: '지원되지 않는 분석 유형입니다.' }, { status: 400 });
  } catch (error) {
    console.error('AI 분석 API 오류:', error);
    const message = error instanceof Error ? error.message : 'AI 분석 중 오류가 발생했습니다.';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
