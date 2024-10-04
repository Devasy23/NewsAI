import streamlit as st
import plotly.express as px
import pandas as pd
import asyncio
import re
from PIL import Image, ImageSequence
from io import BytesIO
import io
import requests
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime
from src.pipeline import reddit_wrapper
from src.utils.dbconnector import find_one_document, fetch_and_combine_reddit_posts_and_comments
# from src.dashboard.app import create_and_show_gif


# Sentiment Sunburst Chart
def create_sunburst_chart(posts, comments):
    # Create data for sunburst
    sunburst_data = {
        "Category": [],
        "Post ID": [],
        "Sentiment": [],
        "Count": []
    }

    # Add post data to sunburst_data
    for sentiment in ["positive", "neutral", "negative"]:
        filtered_posts = posts[posts["Sentiment"] == sentiment]
        for post_id in filtered_posts["Post ID"]:
            sunburst_data["Category"].append(sentiment)
            sunburst_data["Post ID"].append(post_id)
            sunburst_data["Sentiment"].append("Posts")
            sunburst_data["Count"].append(1)

            # Add comments data for each post
            filtered_comments = comments[comments["Post ID"] == post_id]
            for comment_sentiment in ["positive", "neutral", "negative"]:
                count = (filtered_comments["Comment Sentiment"] == comment_sentiment).sum()
                if count > 0:
                    sunburst_data["Category"].append(sentiment)
                    sunburst_data["Post ID"].append(post_id)
                    sunburst_data["Sentiment"].append(comment_sentiment)
                    sunburst_data["Count"].append(count)

    df_sunburst = pd.DataFrame(sunburst_data)
    
    # Sunburst plot
    fig_sunburst = px.sunburst(df_sunburst, 
                               path=["Category", "Post ID", "Sentiment"], 
                               values="Count",
                               title="Sentiment Distribution in Posts and Comments")
    st.plotly_chart(fig_sunburst)

# Sentiment Timeline for Posts and Comments
def create_sentiment_timeline(posts, comments):
    # Convert 'Created UTC' to datetime if not already
    posts["Created UTC"] = pd.to_datetime(posts["Created UTC"])
    comments["Comment Created UTC"] = pd.to_datetime(comments["Comment Created UTC"])

    # Prepare posts sentiment timeline data
    posts_sentiment_df = posts[["Created UTC", "Sentiment"]].groupby([pd.Grouper(key="Created UTC", freq="D"), "Sentiment"]).size().reset_index(name="Count")
    
    # Prepare comments sentiment timeline data
    comments_sentiment_df = comments[["Comment Created UTC", "Comment Sentiment"]].groupby([pd.Grouper(key="Comment Created UTC", freq="D"), "Comment Sentiment"]).size().reset_index(name="Count")

    # Plot sentiment timelines
    fig_posts_timeline = px.line(posts_sentiment_df, x="Created UTC", y="Count", color="Sentiment", title="Sentiment Timeline for Posts")
    fig_comments_timeline = px.line(comments_sentiment_df, x="Comment Created UTC", y="Count", color="Comment Sentiment", title="Sentiment Timeline for Comments")

    st.plotly_chart(fig_posts_timeline)
    st.plotly_chart(fig_comments_timeline)

def download_images(image_urls, save_dir="downloaded_images"):
    # if not os.path.exists(save_dir):
    #     os.makedirs(save_dir)
    """
    Downloads a list of images from the given URLs and returns a list of PIL Image objects.

    Args:
        image_urls (List[str]): List of URLs of the images to download.
        save_dir (str, optional): Directory to save the downloaded images. Defaults to "downloaded_images".

    Returns:
        List[PIL.Image.Image]: List of PIL Image objects downloaded from the URLs.
    """
    image_files = []
    for _, url in enumerate(image_urls):
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content))
            # img_path = os.path.join(save_dir, f'image_{idx}.png')
            # img.save(img_path)
            image_files.append(img)
        except Exception as e:
            print(f"Failed to download {url}: {e}")

    return image_files
def create_and_show_gif(image_files):
    """
    Creates a GIF from a list of PIL Image objects and displays it in Streamlit.

    Args:
        image_files (List[PIL.Image.Image]): List of PIL Image objects to create the GIF from.

    Returns:
        None
    """
    if not all(isinstance(img, Image.Image) for img in image_files):
        raise ValueError("All items in image_files must be PIL.Image objects.")
    images = [img.convert("RGBA") for img in image_files]
    frames = []
    for image in images:
        frames.append(image)
    frames[0].save(
        "mygif.gif", save_all=True, append_images=frames[1:], duration=300, loop=0
    )
    st.image("mygif.gif", use_column_width=True)
# Mock Reddit Wrapper (replace with actual function)
# Function to extract subreddit from post URL
def extract_subreddit(url):
    match = re.search(r"reddit.com/r/([^/]+)/", url)
    return match.group(1) if match else "Unknown"

# Function to create a GIF from image URLs


# Function to generate word cloud
def generate_wordcloud(keywords, title):
    wordcloud = WordCloud(width=800, height=400, background_color="white").generate(" ".join(keywords))
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    plt.title(title)
    st.pyplot(plt)
# Function to flatten Reddit data for visualization
def process_reddit_data(data):
    posts = []
    comments = []
    
    for post in data:
        post_dict = {
            "Title": post["title"],
            "Post ID": post["id"],
            "Content": post["content"],
            "URL": post["url"],
            "Created UTC": post["created_utc"],
            "Discussion Topic": post["discussion_topic"],
            "Sentiment": post.get("sentiment", "neutral"),
        }
        posts.append(post_dict)
        
        for comment in post["top_comments"]:
            comment_dict = {
                "Post ID": post["id"],
                "Comment ID": comment["comment_id"],
                "Comment Content": comment["comment_content"],
                "Comment Score": comment["comment_score"],
                "Comment Created UTC": comment["comment_created_utc"],
                "Comment Sentiment": comment.get("comment_sentiment", "neutral"),
            }
            comments.append(comment_dict)
    
    return pd.DataFrame(posts), pd.DataFrame(comments)

# Streamlit Dashboard Layout
st.title("Reddit Topic Visualization Dashboard")

# Query box
keyword = st.text_input("Enter a discussion topic to search on Reddit")
submit_button = st.button("Submit")

if submit_button and keyword:
    with st.spinner("Fetching Reddit data..."):
        prev = find_one_document("reddit_cache", {"keyword": keyword})
        if prev:
            data = prev["post_ids"]
        else:
            data = reddit_wrapper(keyword=keyword, limit=10)
    
    # Process Reddit Data
    res = fetch_and_combine_reddit_posts_and_comments(data)
    posts_df, comments_df = process_reddit_data(res)

    # Extract subreddits and create pie chart
    posts_df["Subreddit"] = posts_df["URL"].apply(extract_subreddit)
    st.write("### Posts by Subreddit")
    fig_subreddit = px.pie(posts_df, names="Subreddit", title="Subreddit Distribution", hover_data=["Title"])
    st.plotly_chart(fig_subreddit)

    # Handle contentless posts with image URLs
    # image_urls = [post["url"] for post in res if not post["content"] and post["url"].endswith(('.png', '.jpg', '.jpeg'))]
    # if image_urls:
    #     st.write("### Image Posts GIF")
    #     # st.write(image_urls)
    #     gif = create_and_show_gif(download_images(image_urls))
    #     # st.image(gif)

    # Line chart of comments over time
    comments_df["Comment Created UTC"] = pd.to_datetime(comments_df["Comment Created UTC"])
    # sort the dataframe by created UTC
    st.write("### Comment Activity Over Time")
    fig_comments = px.line(comments_df[['Post ID', 'Comment Created UTC']].resample("D", on="Comment Created UTC").count(), title="Comment Activity Over Time")
    st.plotly_chart(fig_comments)

    # Reaction time analysis (post vs. comments)
    posts_df["Created UTC"] = pd.to_datetime(posts_df["Created UTC"])
    # sort the dataframe by created UTC
    st.write("### Reaction Time: Posts vs Comments")
    fig_reaction = px.line(posts_df[['Title', 'Created UTC']].resample("D", on="Created UTC").count(), title="Reaction Time: Posts vs. Comments")
    # fig_comments.update_traces(yaxis="y2")  # Add comments on secondary axis
    st.plotly_chart(fig_reaction)


    # Sunburst chart for sentiments
    st.write("### Sentiment Distribution in Posts and Comments")
    create_sunburst_chart(posts_df, comments_df)

    # Sentiment timeline for posts and comments
    st.write("### Sentiment Timeline for Posts and Comments")
    create_sentiment_timeline(posts_df, comments_df)

    # Generate word cloud for important topics
    keywords = [post["title"] for post in res]  # Mock keyword extraction
    st.write("### Word Cloud of Most Discussed Topics")
    generate_wordcloud(keywords, "Important Topics")

    # Add sentiment-based word cloud (if sentiments are available)
    # sentiments = [post["sentiment"] for post in res]  # Mock sentiment extraction
    # if sentiments:
    #     st.write("### Word Cloud with Sentiments")
    #     generate_wordcloud(sentiments, "Sentiment Analysis")