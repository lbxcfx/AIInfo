"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  Clock3,
  DatabaseZap,
  ExternalLink,
  FileText,
  Flame,
  GitFork,
  Bookmark,
  BookmarkCheck,
  Loader2,
  MessageCircle,
  Newspaper,
  RefreshCcw,
  Search,
  Send,
  Sparkles,
  TrendingUp,
} from "lucide-react";

type ApiResponse<T> = {
  data: T | null;
  error: { code: string; message: string } | null;
};

type Source = {
  id: string;
  name: string;
  url: string;
  tier: string;
  source_type: string;
  language: string;
  category_hint: string | null;
  crawl_interval_minutes: number;
  is_enabled: boolean;
  reliability_score: number;
};

type Item = {
  id: string;
  source_id: string;
  canonical_url: string;
  title_original: string;
  title_zh: string | null;
  summary_short: string;
  category: string;
  published_at: string | null;
  final_score: number;
  is_featured: boolean;
  is_favorite: boolean;
  llm_processed_at: string | null;
  score_details: {
    reason?: string;
    model_scores?: Record<string, number>;
  };
  source: {
    id: string;
    name: string;
    tier: string;
    source_type: string;
  };
};

type SourceHealth = {
  source: Source;
  latest_health: {
    status: string;
    checked_at: string;
    fetched_count: number;
    new_count: number;
    error_message: string | null;
  } | null;
};

type DailyDigest = {
  total: number;
  groups: Array<{ category: string; items: Item[] }>;
};

type GithubWechatDraft = {
  id: string;
  item_id: string;
  draft_type: string;
  title: string;
  digest: string;
  markdown: string;
  image_plan: {
    items?: Array<{ type?: string; source?: string; note?: string }>;
  };
  style_notes: Record<string, unknown>;
  submission_status: string;
  submit_result: { message?: string; generation_fallback?: string };
  created_at: string;
  updated_at: string;
};

type TabKey = "timeline" | "featured" | "favorites" | "search" | "daily" | "sources";
type SortKey = "time" | "score";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

const categoryOrder = ["全部", "模型发布/更新", "产品发布/更新", "论文研究", "技巧与观点", "行业动态"];
const timeWindows = [
  { label: "24小时", days: 1 },
  { label: "7天", days: 7 },
  { label: "30天", days: 30 },
  { label: "全部", days: 0 },
];

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  const payload = (await response.json()) as ApiResponse<T>;
  if (payload.error) {
    throw new Error(payload.error.message);
  }
  return payload.data as T;
}

async function apiPost<T>(path: string, method = "POST"): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { method });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  const payload = (await response.json()) as ApiResponse<T>;
  if (payload.error) {
    throw new Error(payload.error.message);
  }
  return payload.data as T;
}

function formatDate(value: string | null) {
  if (!value) {
    return "时间未知";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDay(value: string | null) {
  if (!value) {
    return "时间未知";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  }).format(new Date(value));
}

function isMostlyChinese(value: string) {
  const chinese = value.match(/[\u4e00-\u9fff]/g)?.length ?? 0;
  return chinese >= Math.max(4, value.length * 0.25);
}

function cleanOriginalTitle(item: Item) {
  const title = item.title_original.replace(/\s*\|\s*Epoch AI\s*$/i, "").trim();
  if (item.source.source_type.startsWith("github")) {
    return title.replace(/:\s*GitHub repository\s*$/i, "").trim();
  }
  return title;
}

function displayTitle(item: Item) {
  return cleanOriginalTitle(item);
}

function displayTitleZh(item: Item) {
  if (item.title_zh?.trim()) {
    return item.title_zh.trim();
  }
  return "中文翻译待生成";
}

function displaySummary(item: Item) {
  if (item.llm_processed_at && isMostlyChinese(item.summary_short)) {
    return item.summary_short;
  }
  if (item.score_details?.reason) {
    return item.score_details.reason;
  }
  return item.summary_short || "该条信息已入库，尚未完成中文增强。点击页面右上角“AI增强”后，可生成中文标题、摘要、实体和排序理由。";
}

function sourceTypeLabel(type: string) {
  const labels: Record<string, string> = {
    rss: "媒体/博客",
    web_page_list: "研究机构",
    github_trending: "GitHub热门",
    github_trending_page: "GitHub官方趋势",
    github_topic_page: "GitHub官方专题",
    x_recent_search: "X热议",
  };
  return labels[type] ?? "其他来源";
}

function sourceIcon(type: string) {
  if (type === "github_trending") return GitFork;
  if (type === "github_trending_page") return GitFork;
  if (type === "github_topic_page") return GitFork;
  if (type === "x_recent_search") return MessageCircle;
  return Newspaper;
}

function isGithubItem(item: Item) {
  return item.source.source_type.startsWith("github");
}

function withinWindow(item: Item, days: number) {
  if (!days || !item.published_at) return true;
  const since = Date.now() - days * 24 * 60 * 60 * 1000;
  return new Date(item.published_at).getTime() >= since;
}

function groupByDay(items: Item[]) {
  return items.reduce<Array<{ day: string; items: Item[] }>>((groups, item) => {
    const day = formatDay(item.published_at);
    const group = groups.find((entry) => entry.day === day);
    if (group) {
      group.items.push(item);
    } else {
      groups.push({ day, items: [item] });
    }
    return groups;
  }, []);
}

function ItemRow({
  item,
  generatingDraft,
  togglingFavorite,
  onGenerateDraft,
  onToggleFavorite,
}: {
  item: Item;
  generatingDraft: boolean;
  togglingFavorite: boolean;
  onGenerateDraft: (itemId: string) => void;
  onToggleFavorite: (item: Item) => void;
}) {
  const Icon = sourceIcon(item.source.source_type);
  return (
    <article className="border-b border-line py-5 last:border-b-0">
      <div className="flex items-start gap-4">
        <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-field text-accent">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink/55">
            <span>{formatDate(item.published_at)}</span>
            <span>{sourceTypeLabel(item.source.source_type)}</span>
            <span>{item.source.name}</span>
            <span>{item.category}</span>
            {item.llm_processed_at ? <span className="text-accent">已中文增强</span> : null}
          </div>
          <a
            href={item.canonical_url}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-flex items-start gap-2 text-lg font-semibold leading-7 hover:text-accent"
          >
            {displayTitle(item)}
            <ExternalLink className="mt-1 h-4 w-4 shrink-0" />
          </a>
          <p
            className={cx(
              "mt-1 text-sm leading-6",
              item.title_zh ? "font-medium text-accent" : "text-ink/45",
            )}
          >
            {displayTitleZh(item)}
          </p>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">{displaySummary(item)}</p>
          {item.score_details?.reason && item.llm_processed_at ? (
            <p className="mt-3 border-l-2 border-accent pl-3 text-xs leading-5 text-ink/60">
              排序理由：{item.score_details.reason}
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              onClick={() => onToggleFavorite(item)}
              disabled={togglingFavorite}
              className={cx(
                "inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60",
                item.is_favorite
                  ? "border-accent bg-accent text-white"
                  : "border-line bg-white text-ink/75 hover:border-accent",
              )}
            >
              {togglingFavorite ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : item.is_favorite ? (
                <BookmarkCheck className="h-4 w-4" />
              ) : (
                <Bookmark className="h-4 w-4" />
              )}
              {item.is_favorite ? "已收藏" : "收藏"}
            </button>
            {isGithubItem(item) ? (
              <button
                onClick={() => onGenerateDraft(item.id)}
                disabled={generatingDraft}
                className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm text-ink/75 hover:border-accent disabled:cursor-not-allowed disabled:opacity-60"
              >
                {generatingDraft ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                发布草稿箱
              </button>
            ) : null}
          </div>
        </div>
        <div className="w-16 shrink-0 text-right">
          <p className="text-2xl font-semibold text-accent">{Math.round(item.final_score)}</p>
          <p className="text-xs text-ink/45">热度</p>
          {item.is_featured ? <p className="mt-2 text-xs text-amber">精选</p> : null}
        </div>
      </div>
    </article>
  );
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabKey>("timeline");
  const [allItems, setAllItems] = useState<Item[]>([]);
  const [featuredItems, setFeaturedItems] = useState<Item[]>([]);
  const [searchItems, setSearchItems] = useState<Item[]>([]);
  const [daily, setDaily] = useState<DailyDigest | null>(null);
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("全部");
  const [timeWindow, setTimeWindow] = useState(7);
  const [sortBy, setSortBy] = useState<SortKey>("time");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [githubDraft, setGithubDraft] = useState<GithubWechatDraft | null>(null);

  const categories = useMemo(() => {
    const values = new Set(allItems.map((item) => item.category));
    return categoryOrder.filter((item) => item === "全部" || values.has(item));
  }, [allItems]);

  const filteredItems = useMemo(() => {
    const source =
      activeTab === "featured"
        ? featuredItems
        : activeTab === "favorites"
          ? allItems.filter((item) => item.is_favorite)
          : activeTab === "search"
            ? searchItems
            : allItems;
    const filtered = source.filter((item) => {
      const categoryMatched = category === "全部" || item.category === category;
      return categoryMatched && withinWindow(item, timeWindow);
    });
    return [...filtered].sort((a, b) => {
      if (sortBy === "score") {
        return b.final_score - a.final_score;
      }
      return new Date(b.published_at ?? 0).getTime() - new Date(a.published_at ?? 0).getTime();
    });
  }, [activeTab, allItems, category, featuredItems, searchItems, sortBy, timeWindow]);

  const groupedItems = useMemo(() => groupByDay(filteredItems), [filteredItems]);

  const categoryStats = useMemo(() => {
    return categories
      .filter((item) => item !== "全部")
      .map((name) => ({ name, count: allItems.filter((item) => item.category === name).length }))
      .sort((a, b) => b.count - a.count);
  }, [allItems, categories]);

  const sourceStats = useMemo(() => {
    return sources.map((entry) => ({
      id: entry.source.id,
      name: entry.source.name,
      type: sourceTypeLabel(entry.source.source_type),
      enabled: entry.source.is_enabled,
      latest: entry.latest_health,
    }));
  }, [sources]);

  async function loadCore() {
    setLoading(true);
    try {
      const [itemsData, featuredData, sourceData, dailyData] = await Promise.all([
        apiGet<Item[]>("/items?limit=100&sort_by=time"),
        apiGet<Item[]>("/featured?limit=50"),
        apiGet<SourceHealth[]>("/sources/health/summary"),
        apiGet<DailyDigest>("/daily"),
      ]);
      setAllItems(itemsData);
      setFeaturedItems(featuredData);
      setSources(sourceData);
      setDaily(dailyData);
      setMessage(null);
    } catch (error) {
      setMessage(`加载失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setLoading(false);
    }
  }

  async function runSearch() {
    setActionLoading("search");
    try {
      const params = new URLSearchParams({ q: query || "AI", limit: "80" });
      if (category !== "全部") params.set("category", category);
      const data = await apiGet<Item[]>(`/search?${params.toString()}`);
      setSearchItems(data);
      setActiveTab("search");
      setMessage(`搜索完成：找到 ${data.length} 条相关情报`);
    } catch (error) {
      setMessage(`搜索失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setActionLoading(null);
    }
  }

  async function runAction(kind: "seed" | "crawl" | "enrich" | "translate") {
    setActionLoading(kind);
    try {
      if (kind === "seed") {
        const result = await apiPost<{ created: number }>("/admin/sources/seed");
        setMessage(`信源已更新：新增 ${result.created} 个来源`);
      }
      if (kind === "crawl") {
        const result = await apiPost<{ items_created: number; errors: string[] }>("/admin/crawl/run");
        setMessage(`采集完成：新增 ${result.items_created} 条情报，异常 ${result.errors.length} 个`);
      }
      if (kind === "enrich") {
        const result = await apiPost<{ processed: number; failed: number }>("/admin/items/enrich?limit=5&include_embeddings=true&reindex_after=true");
        setMessage(`AI增强完成：成功 ${result.processed} 条，失败 ${result.failed} 条`);
      }
      if (kind === "translate") {
        const result = await apiPost<{ translated: number; failed: number }>("/admin/items/translate-titles?limit=20&reindex_after=true");
        setMessage(`标题翻译完成：成功 ${result.translated} 条，失败 ${result.failed} 条`);
      }
      await loadCore();
    } catch (error) {
      setMessage(`操作失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setActionLoading(null);
    }
  }

  async function generateGithubDraft(itemId?: string) {
    const key = itemId ? `github-draft-${itemId}` : "github-draft";
    setActionLoading(key);
    try {
      const params = new URLSearchParams({ submit: "true" });
      if (itemId) params.set("item_id", itemId);
      const result = await apiPost<GithubWechatDraft>(`/admin/github-wechat/drafts?${params.toString()}`);
      setGithubDraft(result);
      setMessage(`发布草稿箱已生成：${result.title}`);
    } catch (error) {
      setMessage(`发布草稿箱生成失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setActionLoading(null);
    }
  }

  function replaceItem(updated: Item) {
    const replace = (items: Item[]) => items.map((item) => (item.id === updated.id ? updated : item));
    setAllItems(replace);
    setFeaturedItems(replace);
    setSearchItems(replace);
    setDaily((current) =>
      current
        ? {
            ...current,
            groups: current.groups.map((group) => ({
              ...group,
              items: replace(group.items),
            })),
          }
        : current,
    );
  }

  async function toggleFavorite(item: Item) {
    const next = !item.is_favorite;
    setActionLoading(`favorite-${item.id}`);
    try {
      const updated = await apiPost<Item>(`/items/${item.id}/favorite?favorite=${String(next)}`);
      replaceItem(updated);
      setMessage(next ? "已加入收藏夹" : "已取消收藏");
    } catch (error) {
      setMessage(`收藏操作失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setActionLoading(null);
    }
  }

  useEffect(() => {
    void loadCore();
  }, []);

  return (
    <main className="min-h-screen bg-field text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-normal">AI 情报站</h1>
              <p className="mt-1 text-sm text-ink/60">
                按时间、类别、来源和热度追踪 AI 最新动态。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => void runAction("seed")} className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm hover:border-accent">
                <DatabaseZap className="h-4 w-4" />
                更新信源
              </button>
              <button onClick={() => void runAction("crawl")} className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm hover:border-accent">
                {actionLoading === "crawl" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                采集最新
              </button>
              <button onClick={() => void runAction("translate")} className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm hover:border-accent">
                {actionLoading === "translate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                翻译标题
              </button>
              <button onClick={() => void generateGithubDraft()} className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm hover:border-accent">
                {actionLoading === "github-draft" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                发布草稿箱
              </button>
              <button onClick={() => void runAction("enrich")} className="inline-flex items-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-medium text-white">
                {actionLoading === "enrich" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                AI增强
              </button>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
            <div className="flex min-h-11 items-center gap-2 rounded-md border border-line bg-white px-3">
              <Search className="h-4 w-4 text-ink/45" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void runSearch();
                }}
                placeholder="搜索模型、产品、公司、论文、开源项目"
                className="h-10 min-w-0 flex-1 bg-transparent text-sm outline-none"
              />
              <button onClick={() => void runSearch()} className="rounded-md bg-ink px-3 py-1.5 text-sm text-white">
                搜索
              </button>
            </div>

            <div className="flex overflow-hidden rounded-md border border-line bg-white">
              {timeWindows.map((window) => (
                <button
                  key={window.label}
                  onClick={() => setTimeWindow(window.days)}
                  className={cx(
                    "px-3 py-2 text-sm",
                    timeWindow === window.days ? "bg-accent text-white" : "text-ink/70 hover:bg-field",
                  )}
                >
                  {window.label}
                </button>
              ))}
            </div>

            <div className="flex overflow-hidden rounded-md border border-line bg-white">
              <button onClick={() => setSortBy("time")} className={cx("px-3 py-2 text-sm", sortBy === "time" ? "bg-accent text-white" : "text-ink/70 hover:bg-field")}>
                按时间
              </button>
              <button onClick={() => setSortBy("score")} className={cx("px-3 py-2 text-sm", sortBy === "score" ? "bg-accent text-white" : "text-ink/70 hover:bg-field")}>
                按热度
              </button>
            </div>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-6 px-5 py-6 lg:grid-cols-[220px_1fr_300px]">
        <aside className="space-y-6">
          <nav className="space-y-1">
            {[
              ["timeline", "时间线", Clock3],
              ["featured", "精选", Flame],
              ["favorites", "收藏夹", BookmarkCheck],
              ["search", "搜索结果", Search],
              ["daily", "日报", CalendarDays],
              ["sources", "来源", DatabaseZap],
            ].map(([key, label, Icon]) => (
              <button
                key={key as string}
                onClick={() => setActiveTab(key as TabKey)}
                className={cx(
                  "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm",
                  activeTab === key ? "bg-white font-medium text-accent" : "text-ink/70 hover:bg-white",
                )}
              >
                <Icon className="h-4 w-4" />
                {label as string}
              </button>
            ))}
          </nav>

          <section>
            <h2 className="text-sm font-semibold">分类</h2>
            <div className="mt-3 space-y-1">
              {categories.map((item) => (
                <button
                  key={item}
                  onClick={() => setCategory(item)}
                  className={cx(
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm",
                    category === item ? "bg-white text-accent" : "text-ink/70 hover:bg-white",
                  )}
                >
                  <span>{item}</span>
                  <span className="text-xs text-ink/45">
                    {item === "全部" ? allItems.length : allItems.filter((entry) => entry.category === item).length}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="min-w-0 space-y-5">
          {message ? (
            <div className="flex items-start gap-2 border border-line bg-white px-4 py-3 text-sm text-ink/75">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber" />
              <span>{message}</span>
            </div>
          ) : null}

          {loading ? (
            <div className="flex items-center gap-3 border border-line bg-white px-5 py-10 text-sm text-ink/60">
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
              正在加载中文情报...
            </div>
          ) : null}

          {githubDraft ? (
            <section className="border border-line bg-white p-5">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-normal text-accent">GitHub 发布草稿箱</p>
                  <h2 className="mt-1 text-lg font-semibold">{githubDraft.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-ink/65">{githubDraft.digest}</p>
                </div>
                <div className="shrink-0 rounded-md bg-field px-3 py-2 text-xs text-ink/60">
                  {githubDraft.submission_status}
                </div>
              </div>
              <p className="mt-4 border-l-2 border-accent pl-3 text-sm text-ink/65">
                {githubDraft.submit_result?.message ?? "草稿已保存。"}
              </p>
              {githubDraft.image_plan?.items?.length ? (
                <div className="mt-4 grid gap-2 text-sm md:grid-cols-3">
                  {githubDraft.image_plan.items.map((image, index) => (
                    <div key={`${image.type ?? "image"}-${index}`} className="border border-line bg-field p-3">
                      <p className="font-medium">{image.type ?? "配图"}</p>
                      <p className="mt-1 break-words text-xs text-ink/55">{image.source ?? "editorial"}</p>
                      <p className="mt-2 text-xs leading-5 text-ink/65">{image.note ?? "需人工确认版权和预览效果。"}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              <textarea
                readOnly
                value={githubDraft.markdown}
                className="mt-4 h-72 w-full resize-y rounded-md border border-line bg-field p-4 font-mono text-xs leading-5 text-ink outline-none"
              />
            </section>
          ) : null}

          {activeTab === "daily" ? (
            <div className="space-y-5">
              <div>
                <h2 className="text-xl font-semibold">AI 日报</h2>
                <p className="mt-1 text-sm text-ink/60">按分类汇总的高价值情报，共 {daily?.total ?? 0} 条。</p>
              </div>
              {daily?.groups.map((group) => (
                <section key={group.category} className="bg-white px-5">
                  <div className="border-b border-line py-4">
                    <h3 className="font-semibold">{group.category}</h3>
                  </div>
                  {group.items.map((item) => (
                    <ItemRow
                      key={item.id}
                      item={item}
                      generatingDraft={actionLoading === `github-draft-${item.id}`}
                      togglingFavorite={actionLoading === `favorite-${item.id}`}
                      onGenerateDraft={(selectedId) => void generateGithubDraft(selectedId)}
                      onToggleFavorite={(selectedItem) => void toggleFavorite(selectedItem)}
                    />
                  ))}
                </section>
              ))}
            </div>
          ) : activeTab === "sources" ? (
            <div className="space-y-5">
              <div>
                <h2 className="text-xl font-semibold">情报来源</h2>
                <p className="mt-1 text-sm text-ink/60">覆盖媒体博客、GitHub 趋势和 X/Twitter 热议源。</p>
              </div>
              <div className="bg-white px-5">
                {sources.map((entry) => {
                  const Icon = sourceIcon(entry.source.source_type);
                  return (
                    <div key={entry.source.id} className="grid gap-4 border-b border-line py-5 last:border-b-0 md:grid-cols-[1fr_130px_120px]">
                      <div className="flex gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-field text-accent">
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <h3 className="font-semibold">{entry.source.name}</h3>
                          <p className="mt-1 text-sm text-ink/60">{sourceTypeLabel(entry.source.source_type)}</p>
                        </div>
                      </div>
                      <div className="text-sm text-ink/65">
                        <p>可靠性 {entry.source.reliability_score}</p>
                        <p>{entry.source.is_enabled ? "已启用" : "待启用"}</p>
                      </div>
                      <div className="text-sm">
                        <p className={entry.latest_health?.status === "ok" ? "text-accent" : "text-amber"}>
                          {entry.latest_health?.status === "ok" ? "正常" : entry.latest_health?.status === "skipped" ? "待配置" : "待检查"}
                        </p>
                        <p className="text-ink/55">新增 {entry.latest_health?.new_count ?? 0}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">
                    {activeTab === "featured" ? "精选情报" : activeTab === "favorites" ? "收藏夹" : activeTab === "search" ? "搜索结果" : "最新时间线"}
                  </h2>
                  <p className="mt-1 text-sm text-ink/60">
                    当前显示 {filteredItems.length} 条，按{sortBy === "time" ? "发布时间" : "热度分"}排序。
                  </p>
                </div>
                <div className="hidden items-center gap-2 text-sm text-ink/55 md:flex">
                  <TrendingUp className="h-4 w-4" />
                  {category}
                </div>
              </div>

              {groupedItems.length === 0 ? (
                <div className="border border-dashed border-line bg-white px-5 py-12 text-sm text-ink/60">
                  当前筛选条件下没有情报。可以扩大时间范围，或点击“采集最新”。
                </div>
              ) : (
                groupedItems.map((group) => (
                  <section key={group.day} className="bg-white px-5">
                    <div className="sticky top-[145px] z-[1] border-b border-line bg-white py-4">
                      <h3 className="font-semibold">{group.day}</h3>
                    </div>
                    {group.items.map((item) => (
                      <ItemRow
                        key={item.id}
                        item={item}
                        generatingDraft={actionLoading === `github-draft-${item.id}`}
                        togglingFavorite={actionLoading === `favorite-${item.id}`}
                        onGenerateDraft={(selectedId) => void generateGithubDraft(selectedId)}
                        onToggleFavorite={(selectedItem) => void toggleFavorite(selectedItem)}
                      />
                    ))}
                  </section>
                ))
              )}
            </div>
          )}
        </section>

        <aside className="space-y-5">
          <section className="bg-white p-5">
            <h2 className="font-semibold">今日概览</h2>
            <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-ink/55">入库情报</dt>
                <dd className="mt-1 text-2xl font-semibold">{allItems.length}</dd>
              </div>
              <div>
                <dt className="text-ink/55">精选</dt>
                <dd className="mt-1 text-2xl font-semibold">{featuredItems.length}</dd>
              </div>
              <div>
                <dt className="text-ink/55">中文增强</dt>
                <dd className="mt-1 text-2xl font-semibold">{allItems.filter((item) => item.llm_processed_at).length}</dd>
              </div>
              <div>
                <dt className="text-ink/55">来源</dt>
                <dd className="mt-1 text-2xl font-semibold">{sources.length}</dd>
              </div>
            </dl>
          </section>

          <section className="bg-white p-5">
            <h2 className="font-semibold">热门分类</h2>
            <div className="mt-4 space-y-3">
              {categoryStats.map((entry) => (
                <button key={entry.name} onClick={() => setCategory(entry.name)} className="flex w-full items-center justify-between text-left text-sm">
                  <span>{entry.name}</span>
                  <span className="text-ink/50">{entry.count}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="bg-white p-5">
            <h2 className="font-semibold">趋势源</h2>
            <div className="mt-4 space-y-3 text-sm">
              {sourceStats
              .filter((entry) => entry.type.startsWith("GitHub") || entry.type === "X热议")
                .map((entry) => (
                  <div key={entry.id} className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{entry.name}</p>
                      <p className="text-ink/55">{entry.type}</p>
                    </div>
                    {entry.enabled ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 text-accent" />
                    ) : (
                      <span className="text-xs text-amber">待配置</span>
                    )}
                  </div>
                ))}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}
