import { GoogleGenerativeAI } from '@google/generative-ai';

// API Key 설정 (환경변수 또는 클라이언트에서 전달)
const getGeminiKey = () => process.env.GEMINI_API_KEY || process.env.YOUTUBE_API_KEY || '';

/**
 * 채널의 상위 성과 영상들을 분석하여 성공 패턴과 전략을 도출합니다.
 */
export async function analyzeChannelInsights(
  channelTitle: string,
  videos: Array<{ title: string; viewCount: number; contribution: number }>,
  apiKey?: string
) {
  const key = apiKey || getGeminiKey();
  if (!key) throw new Error('Gemini API Key가 설정되지 않았습니다.');

  const genAI = new GoogleGenerativeAI(key);
  const model = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });

  // 상위 10개 영상으로 제한하여 프롬프트 구성
  const topVideos = videos
    .slice(0, 10)
    .map((v, i) => `${i + 1}. ${v.title} (조회수: ${v.viewCount.toLocaleString()}회, 기여도: ${v.contribution.toFixed(1)}%)`)
    .join('\n');

  const prompt = `
당신은 유튜브 성장 전략 전문가입니다. 다음은 유튜브 채널 '${channelTitle}'의 상위 성과 영상 목록입니다.

${topVideos}

이 데이터를 바탕으로 다음 항목들을 분석하여 한국어로 답변해 주세요:
1. **성공 요인 분석**: 이 채널이 시청자들의 클릭을 유도하는 핵심 '후킹(Hooking)' 포인트와 주제 선정의 특징은 무엇인가요?
2. **콘텐츠 패턴**: 제목의 구성 방식이나 타겟팅하는 시청자층의 특징을 분석해 주세요.
3. **향후 전략 제안**: 이 채널이 더 성장하기 위해 어떤 주제나 형식을 시도해 보면 좋을까요?

답변은 마크다운(Markdown) 형식으로 작성해 주세요.
`;

  const result = await model.generateContent(prompt);
  const response = await result.response;
  return response.text();
}

/**
 * 특정 영상의 제목과 설명을 바탕으로 핵심 내용을 요약합니다.
 */
export async function summarizeVideoContent(
  videoTitle: string,
  description: string,
  apiKey?: string
) {
  const key = apiKey || getGeminiKey();
  if (!key) throw new Error('Gemini API Key가 설정되지 않았습니다.');

  const genAI = new GoogleGenerativeAI(key);
  const model = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });

  const prompt = `
다음 유튜브 영상의 제목과 설명을 바탕으로 핵심 내용을 3문장 이내로 요약해 주세요.
영상 제목: ${videoTitle}
영상 설명: ${description.slice(0, 1000)} // 설명이 너무 길면 자름

요약 결과:
`;

  const result = await model.generateContent(prompt);
  const response = await result.response;
  return response.text().trim();
}
