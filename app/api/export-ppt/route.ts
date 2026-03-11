import { NextRequest, NextResponse } from 'next/server';
import pptxgen from 'pptxgenjs';

export async function POST(req: NextRequest) {
  try {
    const data = await req.json();
    const pptx = new pptxgen();

    // 1. 제목 슬라이드
    const titleSlide = pptx.addSlide();
    titleSlide.addText('YouTube Channel Analysis Report', {
      x: 1, y: 1, w: 8, h: 1,
      fontSize: 32, color: '363636', align: 'center', bold: true
    });
    titleSlide.addText(data.channelTitle, {
      x: 1, y: 2, w: 8, h: 1,
      fontSize: 24, color: '0088CC', align: 'center'
    });

    // 2. 채널 개요 슬라이드
    const overviewSlide = pptx.addSlide();
    overviewSlide.addText('Channel Overview', { x: 0.5, y: 0.5, fontSize: 24, bold: true });
    overviewSlide.addText([
      { text: `구독자 수: ${data.subscriberCount.toLocaleString()}명\n` },
      { text: `총 영상 수: ${data.videoCount.toLocaleString()}개\n` },
      { text: `총 조회수: ${data.totalViews.toLocaleString()}회\n` },
      { text: `평균 조회수: ${data.avgViews.toLocaleString()}회` }
    ], { x: 0.5, y: 1.5, w: 9, h: 4, fontSize: 18 });

    // 3. 주요 영상 성과 테이블 슬라이드
    const videoSlide = pptx.addSlide();
    videoSlide.addText('Top 10 Video Performance', { x: 0.5, y: 0.5, fontSize: 24, bold: true });

    const tableData = [
      [{ text: '제목' }, { text: '조회수' }, { text: '기여도' }, { text: '성과도' }],
      ...data.videos.slice(0, 10).map((v: any) => [
        { text: v.title.slice(0, 40) + '...' },
        { text: v.viewCount.toLocaleString() },
        { text: v.contribution },
        { text: v.performance }
      ])
    ];

    videoSlide.addTable(tableData, {
      x: 0.5, y: 1.2, w: 9,
      border: { type: 'solid', color: 'E1E1E1' },
      fill: { color: 'F9F9F9' },
      fontSize: 10,
    });

    // PPT 생성 (Buffer)
    const buffer = await pptx.write({ outputType: 'nodebuffer' });

    return new NextResponse(buffer as any, {
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'Content-Disposition': `attachment; filename="YouTube_Report_${encodeURIComponent(data.channelTitle)}.pptx"`,
      },
    });
  } catch (error) {
    console.error('PPT Generation Error:', error);
    return NextResponse.json({ error: 'Failed to generate PPT' }, { status: 500 });
  }
}
