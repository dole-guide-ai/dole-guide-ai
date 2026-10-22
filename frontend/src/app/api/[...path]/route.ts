/**
 * 브라우저가 부르는 /api/* 요청을 받아 백엔드로 넘기는 BFF 라우트입니다.
 * 모든 메서드를 lib/bff.ts의 proxyToBackend로 보내고, 경로(/api/accounts/lee → /accounts/lee)를 그대로 이어 붙입니다.
 * 쿠키와 스트림을 다루므로 캐시 없이 요청마다 실행합니다.
 */

import type { NextRequest } from 'next/server';

import { proxyToBackend } from '@/lib/bff';

// 쿠키·스트림을 다루므로 항상 요청마다 실행합니다(Node 런타임).
export const dynamic = 'force-dynamic';

interface Context {
  params: Promise<{ path: string[] }>;
}

const handle = async (request: NextRequest, { params }: Context) =>
  proxyToBackend(request, (await params).path);

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
