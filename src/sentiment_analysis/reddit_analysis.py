import os
import sys

from textblob import TextBlob

from src.ingestion.prawapi import fetch_reddit_posts_by_keyword
from src.utils.dbconnector import append_to_document, find_documents

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))


def extract_post_content(posts):
    """
    First it concate the content of each post
    then it reduces the redunduncy from the content

    Args:
        posts (list): A list of posts
    """
    content = ""
    for post in posts:
        content += post["content"].strip()
        content += " "

    return content


def sentiment_analysis(text):
    """
    Analyzes the sentiment of the given text.

    Args:
        text (str): The text to analyze

    Returns:
        str: The sentiment of the text, either "positive", "neutral", or "negative"
    """

    analysis = TextBlob(text)
    print(analysis.sentiment.polarity)
    if analysis.sentiment.polarity > 0.25:
        return "positive"
        print("positive")
    elif analysis.sentiment.polarity < -0.25:
        return "negative"
        print("negative")
    else:
        return "neutral"
        print("neutral")


def fetch_required_reddit_posts(keyword, limit):
    """
    Fetches the records from mongodb collection for the given keyword

    Args:
        keyword (str): The keyword to search for

    Returns:
        list: A list of documents
    """
    # posts = find_documents("reddit_posts", {"discussion_topic": keyword})
    posts = fetch_reddit_posts_by_keyword(
        keyword=keyword, limit=limit, to_json=True)

    for post in posts:
        update_data = {"sentiment": sentiment_analysis(post["content"])}
        append_to_document("reddit_posts", {"id": post["id"]}, update_data)
        for comment in post["top_comments"]:
            comment["comment_sentiment"] = sentiment_analysis(
                comment["comment_content"]
            )
        update_data = {"top_comments": post["top_comments"]}
        append_to_document("reddit_posts", {"id": post["id"]}, update_data)

    return posts


if __name__ == "__main__":
    posts = fetch_required_reddit_posts(
        keyword="kolkata murder case", limit=10)
    # content = extract_post_content(posts)
    # sentiment_analysis(content)
    # for post in posts:
    #     print(post["title"])
