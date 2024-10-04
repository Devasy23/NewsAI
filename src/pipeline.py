import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from aiohttp import ClientSession
from tenacity import retry, stop_after_attempt, wait_fixed

from src.ingestion.fetch_articles import fetch_article_content
from src.ingestion.newsapi import fetch_news
from src.preprocessing.keyword_extraction import (bert_keyword_extraction,
                                                  extract_keywords)
from src.preprocessing.summarization import summarize_texts
from src.sentiment_analysis.classify import (analyze_sentiments,
                                             classify_sentiments)
# function for reddit post fetching and sentiment analysis
from src.sentiment_analysis.reddit_analysis import fetch_required_reddit_posts
from src.sentiment_analysis.wordcloud import generate_wordcloud
from src.utils.dbconnector import append_to_document, content_manager
from src.utils.logger import setup_logger

# Setup logger
logger = setup_logger()


async def summarize_texts_async(article_id):
    """
    Asynchronous wrapper for summarize_texts.

    Args:
        article_id (str): ID of the article to summarize.

    Returns:
        str: Summarized text.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, summarize_texts, [article_id])


async def extract_keywords_async(article_id):
    """
    Asynchronous wrapper for extract_keywords.

    Args:
        article_id (str): ID of the article to extract keywords from.

    Returns:
        List[str]: List of extracted keywords.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_keywords, [article_id])


async def analyze_sentiments_async(article_id):
    """
    Asynchronous wrapper for analyze_sentiments.

    Args:
        article_id (str): ID of the article to analyze.

    Returns:
        List[Dict[str, float]]: List of sentiment analysis results for each text.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_sentiments, [article_id])


async def process_single_article_async(article_id, session):
    # Check the presence of content, summary, keywords, and sentiment in the DB
    """
    Process a single article asynchronously, by fetching content, summarizing, extracting keywords and analyzing sentiment.

    Args:
        article_id (str): ID of the article to process.
        session (aiohttp.ClientSession): The aiohttp session to use for the request.

    Returns:
        str: The ID of the article that was processed.
    """
    field_status = content_manager(
        article_id, ["content", "summary", "keywords", "sentiment"]
    )

    # Fetch content only if not already present
    if not field_status["content"]:
        content = await fetch_article_content([article_id], session)
        # Save content to MongoDB
        # append_to_document("News_Articles", {"id": article_id}, {"content": content})
    else:
        logger.info(
            f"Content already exists for article {article_id}. Skipping fetch.")

    # Summarize only if summary is not already present
    if not field_status["summary"]:
        if not field_status["content"]:
            content = await fetch_article_content([article_id], session)
        summary = await summarize_texts_async(article_id)
        # Save summary to MongoDB
        # append_to_document("News_Articles", {"id": article_id}, {"summary": summary})
    else:
        logger.info(
            f"Summary already exists for article {article_id}. Skipping summarization."
        )

    # Extract keywords only if not already present
    if not field_status["keywords"]:
        keywords = await extract_keywords_async(article_id)
        # Save keywords to MongoDB
        # append_to_document("News_Articles", {"id": article_id}, {"keywords": keywords})
    else:
        logger.info(
            f"Keywords already exist for article {article_id}. Skipping extraction."
        )

    # Analyze sentiment only if not already present
    if not field_status["sentiment"]:
        sentiment = await analyze_sentiments_async(article_id)
        # Save sentiment to MongoDB
        # append_to_document("News_Articles", {"id": article_id}, {"sentiment": sentiment})
    else:
        logger.info(
            f"Sentiment already exists for article {article_id}. Skipping sentiment analysis."
        )

    return article_id


async def process_articles_async(query, limit=10):
    """
    Process a list of articles asynchronously, by fetching content, summarizing, extracting keywords and analyzing sentiment.

    Args:
        query (str): The query to search for in the NewsAPI.
        limit (int, optional): The number of articles to fetch. Defaults to 10.

    Returns:
        List[str]: The IDs of the articles that were processed.
    """
    logger.info("Starting the processing of articles.")
    article_ids = fetch_news(
        query=query,
        from_date="2024-08-16",
        sort_by="popularity",
        limit=limit,
        to_json=False,
    )
    if not isinstance(article_ids, list):
        raise ValueError("article_ids should be a list")

    async with ClientSession() as session:
        tasks = [
            process_single_article_async(article_id, session)
            for article_id in article_ids
        ]
        await asyncio.gather(*tasks)

    logger.info("Processing completed.")
    return article_ids


def process_articles(query, limit=10):
    """
    Process a list of articles by fetching content, summarizing, extracting keywords and analyzing sentiment.

    Args:
        query (str): The query to search for in the NewsAPI.
        limit (int, optional): The number of articles to fetch. Defaults to 10.

    Returns:
        List[str]: The IDs of the articles that were processed.
    """
    logger.info("Starting the processing of articles.")
    article_ids = asyncio.run(process_articles_async(query, limit))
    return article_ids
    # Fetch articles from NewsAPI
    article_ids = fetch_news(
        query=query,
        from_date="2024-08-04",
        sort_by="popularity",
        limit=limit,
        to_json=False,
    )
    if not isinstance(article_ids, list):
        raise ValueError("article_ids should be a list")

    # Get contents for each article
    article_contents = fetch_article_content(article_ids)

    # contents_file = f"{query.replace(' ', '_')}_contents2.json"
    # with open(contents_file, "w", encoding="utf-8") as f:
    #     json.dump(article_contents, f, ensure_ascii=False, indent=4)

    # Summarize the articles
    logger.info("Summarizing articles.")
    article_summaries = summarize_texts(article_ids)

    # summaries_file = f"{query.replace(' ', '_')}_summaries2.json"
    # with open(summaries_file, "w", encoding="utf-8") as f:
    #     json.dump(article_summaries, f, ensure_ascii=False, indent=4)

    # Extract keywords from summaries
    logger.info("Extracting keywords from summaries.")
    article_keywords = extract_keywords(article_ids, top_n=10)

    # keywords_file = f"{query.replace(' ', '_')}_keywords2.json"
    # with open(keywords_file, "w", encoding="utf-8") as f:
    #     json.dump(article_keywords, f, ensure_ascii=False, indent=4)

    # Analyze sentiments of summaries
    logger.info("Analyzing sentiments of summaries.")
    article_sentiments = analyze_sentiments(article_ids)


if __name__ == "__main__":
    logger.info("Starting the processing of articles.")

    article_ids = process_articles("Adani Hindenburg Report", limit=10)
    logger.info(f"Article IDs: {article_ids}")

    # news_data = fetch_news(
    #     query="Kolkata Murder Case", from_date="2024-08-01", sort_by="popularity", to_json=False
    # )
    # urls = [article.get("url") for article in news_data.get("articles", [])]

    # # Process articles
    # keywords, sentiments, wordcloud = process_articles(urls)
    # logger.info(f"Keywords: {keywords}")
    # logger.info(f"Sentiments: {sentiments}")
    # wordcloud.to_image().save("wordcloud.png")
    # logger.info("Processing of articles completed successfully.")
