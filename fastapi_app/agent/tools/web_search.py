from langchain.tools import tool
from typing import List, Dict, Any
import trafilatura
from pydantic import BaseModel, Field
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ddgs import DDGS


class WebSearchInput(BaseModel):
    """Входные данные для веб-поискового инструмента."""
    queries_list: List[str] = Field(
        ...,
        description="Список поисковых запросов для выполнения веб-поиска.",
        min_length=1,
        max_length=5 
    )

@tool(args_schema=WebSearchInput)
def web_search_tool(queries_list: List[str]) -> str:
    """
    Выполняет веб-поиск и возвращает найденные данные как сырой текст.
    НЕ вызывает LLM, НЕ суммаризует — только собирает данные.
    """
    results = perform_web_search(queries_list)
    if not results:
        return "Не найдено релевантных источников в интернете."

    # Ограничиваем размер для предотвращения перегрузки контекста
    raw_text = "\n\n".join([
        f"Источник: {res['url']}\nЗаголовок: {res['title']}\nКонтент: {res['content'][:300]}"
        for res in results[:3]  # Берем только первые 3 источника
    ])
    return raw_text

def perform_web_search(queries: List[str]) -> List[Dict[str, Any]]:
    """Выполнение поиска с обработкой таймаутов и фильтрацией видеоссылок"""

    VIDEO_PLATFORMS = [
        "youtube.com", "youtu.be", "rutube.ru", "vk.com/video", 
        "dzen.ru/video", "ok.ru/video", "tiktok.com", "instagram.com/reel",
        "vimeo.com", "coub.com", "my.mail.ru/video"
    ]
    
    results = []
    seen_urls = set()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, RuntimeError, ConnectionError))
    )
    def safe_search(query: str, max_results: int = 1):
        """Безопасный поиск с повторными попытками"""


        with DDGS() as ddgs:
            results = ddgs.text(
                query=query,
                region="ru-ru",
                max_results=max_results,
            )
        return results

    for query in queries:
        try:
            # Добавляем географический контекст к запросу, ps Я лучше не придумал
            localized_query = f"{query} Россия Санкт-Петербург медицина"
            
            print("Searching for query:", localized_query)
            raw_results = safe_search(localized_query, max_results=2)
            if raw_results:
                for res in raw_results:
                    url = res["href"]
                    print("Found URL:", url)
                    if any(video_domain in url.lower() for video_domain in VIDEO_PLATFORMS):
                        continue
                    
                    seen_urls.add(url)
                    try:
                        content = scrape_page_content(url)
                        if content and len(content) > 100:
                            results.append({
                                "title": res["title"],
                                "url": url,
                                "snippet": res["body"],
                                "content": content[:800]  # Уменьшено с 2000 до 800
                            })
                    except Exception as e:
                        continue
        
        except Exception as e:
            print(f"Ошибка при поиске по запросу '{query}': {str(e)}")
            continue
        
        # Добавляем задержку между запросами, чтобы избежать блокировки
        time.sleep(1.5)

    return results[:3]  # Уменьшено с 5 до 3 для оптимизации контекста


def scrape_page_content(url: str) -> str:
    """Парсинг основного контента страницы с использованием trafilatura"""
    try:
        config = trafilatura.settings.use_config()
        config.set("DEFAULT", "EXTRACTION_TIMEOUT", "10")
        
        downloaded = trafilatura.fetch_url(
            url,
            config=config,
        )
        
        if not downloaded:
            return ""
        
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_images=False,
            include_links=False,
            output_format="txt",
            config=config
        )

        if content:
            return content[:800]  # Уменьшено с 2000 до 800
        return ""
            
    except Exception as e:
        print(f"Ошибка при парсинге {url}: {str(e)}")
        return ""

