#!/usr/bin/env python3
"""
GitHub Actions compatible media posting script
This replaces the crontab-based scheduling with direct execution
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime
from typing import Dict, List, Optional

from dateutil import tz

# Add the src directory to the module search path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

try:
    from src import logger_config, post_list
except ImportError as e:
    print(f"Error importing src modules: {e}")
    print("Make sure your src directory contains logger_config.py and post_list.py")
    sys.exit(1)


def setup_logging() -> logging.Logger:
    """Setup logging for GitHub Actions run"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(current_dir, "logs", "post-activity.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    # Simple logging configuration since logger_config might have dependencies
    logger = logging.getLogger("media_post")
    logger.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    
    # Console handler for GitHub Actions output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def load_posts(posts_file_path: str, logger: logging.Logger) -> List[Dict]:
    """Load posts from JSON file"""
    try:
        with open(posts_file_path, 'r') as f:
            posts_data = json.load(f)
        logger.info(f"Successfully loaded {len(posts_data)} posts from {posts_file_path}")
        return posts_data
    except FileNotFoundError:
        logger.error(f"Posts file not found: {posts_file_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from {posts_file_path}: {e}")
        return []


def should_post_today(post_date_str: str, logger: logging.Logger) -> bool:
    """Check if the post should be published today"""
    try:
        # Parse the post date (expected format: "2024-12-25 09:00")
        post_datetime = datetime.strptime(post_date_str, "%Y-%m-%d %H:%M")
        
        # Make it timezone aware
        post_datetime = post_datetime.replace(tzinfo=tz.gettz("US/Eastern"))
        
        # Get current time in EST
        now_est = datetime.now(tz.gettz("US/Eastern"))
        
        # Check if it's the same day
        return post_datetime.date() == now_est.date()
    except ValueError as e:
        logger.error(f"Error parsing post date '{post_date_str}': {e}")
        return False


def archive_post(post: Dict, current_dir: str, logger: logging.Logger) -> bool:
    """Move posted content to archive"""
    try:
        archive_dir = os.path.join(current_dir, "data", "processed_posts")
        os.makedirs(archive_dir, exist_ok=True)
        
        # Create archive filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        post_id = post.get('id', timestamp)
        archive_path = os.path.join(archive_dir, f"posted_{post_id}_{timestamp}.json")
        
        with open(archive_path, 'w') as f:
            json.dump(post, f, default=str, indent=2)
        
        logger.info(f"Archived post to {archive_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to archive post: {e}")
        return False


def post_to_instagram(post: Dict, logger: logging.Logger) -> bool:
    """
    Actual posting logic - REPLACE THIS with your actual posting code
    """
    logger.info(f"Attempting to post: {post.get('caption', 'No caption')[:50]}...")
    
    # TODO: Add your actual Instagram posting logic here
    # Example with instagrapi:
    # from instagrapi import Client
    # client = Client()
    # client.login(username, password)
    # 
    # if post.get('media_type') == 'photo':
    #     client.photo_upload(post['media_path'], caption=post['caption'])
    # elif post.get('media_type') == 'video':
    #     client.video_upload(post['media_path'], caption=post['caption'])
    
    # Placeholder success
    logger.warning("Posting logic not implemented - this is a placeholder")
    return True


def update_posts_file(all_posts: List[Dict], remaining_posts: List[Dict], 
                     to_post_path: str, logger: logging.Logger) -> None:
    """Update the main posts file by removing posted items"""
    try:
        # Backup original
        backup_path = to_post_path + ".backup"
        shutil.copy(to_post_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        
        # Write remaining posts
        with open(to_post_path, 'w') as f:
            json.dump(remaining_posts, f, indent=2)
        
        logger.info(f"Updated {to_post_path} with {len(remaining_posts)} remaining posts")
    except Exception as e:
        logger.error(f"Failed to update posts file: {e}")


def main() -> None:
    """Main function for GitHub Actions posting"""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Starting media posting process (GitHub Actions mode)")
    logger.info(f"Run time: {datetime.now(tz.gettz('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    to_post_path = os.path.join(current_dir, "data", "to-post.json")
    
    # Check if posts file exists
    if not os.path.exists(to_post_path):
        logger.error(f"No posts file found at {to_post_path}")
        logger.info("Creating sample posts file for testing...")
        
        # Create sample data directory and file
        os.makedirs(os.path.dirname(to_post_path), exist_ok=True)
        sample_posts = [
            {
                "id": "1",
                "post_date": datetime.now(tz.gettz("US/Eastern")).strftime("%Y-%m-%d 09:00"),
                "caption": "Sample post - Replace with your content",
                "media_type": "photo",
                "media_path": "path/to/your/media.jpg"
            }
        ]
        with open(to_post_path, 'w') as f:
            json.dump(sample_posts, f, indent=2)
        logger.info(f"Created sample posts file at {to_post_path}")
        logger.warning("Please update data/to-post.json with your actual posts")
    
    # Load all posts
    all_posts = load_posts(to_post_path, logger)
    
    if not all_posts:
        logger.info("No posts to process")
        return
    
    # Find posts scheduled for today
    posts_to_post = []
    remaining_posts = []
    
    for post in all_posts:
        post_date = post.get('post_date')
        if not post_date:
            logger.warning(f"Post missing 'post_date' field: {post}")
            remaining_posts.append(post)
            continue
        
        if should_post_today(post_date, logger):
            posts_to_post.append(post)
            logger.info(f"Post scheduled for today: {post_date}")
        else:
            remaining_posts.append(post)
            logger.debug(f"Post not scheduled for today: {post_date}")
    
    # Post each scheduled item
    successful_posts = []
    failed_posts = []
    
    for post in posts_to_post:
        logger.info(f"Processing post: {post.get('caption', 'No caption')[:50]}...")
        
        # Attempt to post
        if post_to_instagram(post, logger):
            successful_posts.append(post)
            # Archive successful post
            archive_post(post, current_dir, logger)
        else:
            failed_posts.append(post)
            logger.error(f"Failed to post: {post.get('caption', 'No caption')[:50]}")
            remaining_posts.append(post)  # Keep failed posts for retry
    
    # Update the main posts file
    if successful_posts:
        update_posts_file(all_posts, remaining_posts, to_post_path, logger)
    
    # Summary
    logger.info("=" * 60)
    logger.info(f"POSTING SUMMARY:")
    logger.info(f"  Total posts checked: {len(all_posts)}")
    logger.info(f"  Scheduled for today: {len(posts_to_post)}")
    logger.info(f"  Successfully posted: {len(successful_posts)}")
    logger.info(f"  Failed: {len(failed_posts)}")
    logger.info(f"  Remaining for future: {len(remaining_posts)}")
    logger.info("=" * 60)
    
    if failed_posts:
        logger.warning(f"Failed posts will be retried tomorrow")
        sys.exit(1)  # Exit with error to flag in GitHub Actions
    else:
        logger.info("All scheduled posts processed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
