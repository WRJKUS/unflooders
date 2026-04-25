import { execFile } from "node:child_process"
import { promisify } from "node:util"
import { NextResponse } from "next/server"

const execFileAsync = promisify(execFile)

let cache: unknown = null
let cacheAt = 0
const CACHE_TTL_MS = 5 * 60 * 1000

export const runtime = "nodejs"

export async function GET() {
  const now = Date.now()
  if (cache && now - cacheAt < CACHE_TTL_MS) {
    return NextResponse.json(cache, {
      headers: {
        "Cache-Control": "public, max-age=60"
      }
    })
  }

  try {
    const { stdout } = await execFileAsync("python3", ["scripts/sqlite_snapshot_json.py"], {
      cwd: process.cwd(),
      maxBuffer: 64 * 1024 * 1024
    })

    const payload = JSON.parse(stdout)
    cache = payload
    cacheAt = now

    return NextResponse.json(payload, {
      headers: {
        "Cache-Control": "public, max-age=60"
      }
    })
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to load snapshot",
        details: error instanceof Error ? error.message : "unknown"
      },
      { status: 500 }
    )
  }
}
