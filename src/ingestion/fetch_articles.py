import asyncio
import json
import os
import sys
from typing import Dict, List
from urllib.parse import urlparse

import aiohttp
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, RetryCallState, retry_if_exception_type

from src.utils.dbconnector import (append_to_document, content_manager,
                                   find_documents)
from src.utils.logger import setup_logger

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))

logger = setup_logger()


async def fetch_article_content(article_ids, session):
    """
    Fetches the content of a list of articles asynchronously, by checking if content already exists in the database, and if not, extracting the content from the given URLs.

    Args:
        article_ids (List[str]): List of IDs of the articles to fetch content for.
        session (aiohttp.ClientSession): The aiohttp session to use for the request.

    Returns:
        List[Dict[str, str]]: List of dictionaries, each containing the ID and content of a fetched article.
    """
    try:
        # if not docs:
        #     raise ValueError(
        #         f"No documents found for article IDs: {article_ids}")
        docs = find_documents("News_Articles", {"id": {"$in": article_ids}})
    except Exception as e:
        logger.error(f"Failed to find documents: {e}")
        raise

    urls_to_fetch = []

    # Check if content already exists for each article
    for doc in docs:
        id = doc["id"]
        url = doc["url"]

        # Use the content manager to check if content already exists
        field_status = content_manager(id, ["content"])

        if not field_status["content"]:
            urls_to_fetch.append({"id": id, "url": url})
            logger.info(f"Fetching content for article {id}")
        else:
            logger.info(
                f"Content already exists for article {id}. Skipping fetch.")

    article_contents = []

    # Define an asynchronous function to fetch content
    async def fetch_content(id, url):
        """
        Fetches the content of a single article asynchronously.

        Args:
            id (str): The ID of the article to fetch content for.
            url (str): The URL of the article to fetch content from.

        Returns:
            None
        """
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), "html.parser")

                # Extract the article content based on common HTML structure
                article_content = ""

                # Many articles have a <p> tag structure for paragraphs
                paragraphs = soup.find_all("p")
                if paragraphs:
                    for p in paragraphs:
                        article_content += p.get_text() + "\n"
                else:
                    # Fallback if no <p> tags found, try another structure, e.g., <div>
                    divs = soup.find_all("div")
                    for div in divs:
                        article_content += div.get_text() + "\n"

                # Clean up the content
                article_content = article_content.strip()

                article_obj = {"id": id, "content": article_content}
                article_contents.append(article_obj)

                # Save content to MongoDB
                append_to_document("News_Articles", {"id": id}, article_obj)
                logger.info(f"Content fetched and saved for article {id}")
        except Exception as e:
            logger.error(f"Failed to fetch the article {id}: {e}")

    # Run the fetch operations in parallel using aiohttp
    tasks = [fetch_content(obj["id"], obj["url"]) for obj in urls_to_fetch]
    await asyncio.gather(*tasks)

    logger.info(f"Total articles content fetched: {len(article_contents)}")
    return article_contents

def fetch_content_before_sleep(retry_state: RetryCallState):
    wait_time = retry_state.next_action.sleep
    attempt_number = retry_state.attempt_number
    print(f"Retrying after {wait_time:.2f} seconds (Attempt {attempt_number})...")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    before_sleep=fetch_content_before_sleep,
)
async def fetch_article_content_from_url(url: str, session: aiohttp.ClientSession) -> str:
    """
    Fetches the content of an article from a given URL.

    Args:
        url (str): The URL of the article to fetch content from.
        session (aiohttp.ClientSession): The aiohttp session to use for the request.

    Returns:
        str: Content of the fetched article.
    """
    async def sanitize_content(content):
        """ Removes any unwanted characters from the content.""" 
        content = content.replace("\n", " ")
        content = content.replace("\t", " ")
        content = content.strip()
        return content

    async def parse_html(html):
        """ Parses the HTML content and extracts the article content."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Extract the article content from all the <p> tags
            page = soup.find_all("p")
            content = [await sanitize_content(x.get_text()) for x in page]
            content = " ".join(content)
            return content
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            raise

    try:
        async with session.get(url) as response:
            if response.status == 200:
                response_text = await response.text()
                content = await parse_html(response_text)
                return content
            else:
                raise Exception(
                    f"Failed to fetch article {url}: {response.status}"
                )
    except Exception as e:
        logger.error(f"Error fetching content for article {url}: {e}")
        raise

async def test_fetch_article_content_from_url(urls: List[str]) -> List[List[str]]:
    """
    Tests the fetch_article_content_from_url function by fetching content for a list of article URLs.

    Args:
        urls (List[str]): A list of article URLs to fetch content for.

    Returns:
        List[List[str]]: A list of lists where each list contains the content of a fetched article.
    """
    async with aiohttp.ClientSession() as session:
        contents = await asyncio.gather(*[fetch_article_content_from_url(url, session) for url in urls])
        logger.info(contents)  # Print the fetched content for verification

async def test_fetch_article_content(article_ids: List[str]) -> List[Dict[str, str]]:
    """
    Tests the fetch_article_content function by fetching content for a list of article IDs.

    Args:
        article_ids (List[str]): A list of article IDs to fetch content for.

    Returns:
        List[Dict[str, str]]: A list of dictionaries where each dictionary contains the ID and content of a fetched article.
    """
    async with aiohttp.ClientSession() as session:
        contents = await fetch_article_content(article_ids, session)
        logger.info(contents)  # Print the fetched content for verification


if __name__ == "__main__":
    # url = "https://www.rt.com/india/602908-reclaiming-night-protests-over-rape/"
    # article_ids = [
    #     "b01d85d7-d538-47cc-a7c4-31c13e7f6b4e",
    #     "15133cc7-1522-41f9-8db4-70568e837968",
    # ]
    # asyncio.run(test_fetch_article_content())
    urls = [
        "https://www.rt.com/india/602908-reclaiming-night-protests-over-rape/",
        "https://edition.cnn.com/2024/10/03/politics/abortion-melania-trump/index.html",
        "https://www.androidauthority.com/full-res-pixel-9a-wallpapers-3487229/",
        "https://edition.cnn.com/world/live-news/israel-iran-attack-war-lebanon-10-03-24-intl-hnk/index.html",
    ]
    asyncio.run(test_fetch_article_content_from_url(urls))
