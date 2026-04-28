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


def setup_logging() -> logging.Logger:
    """Setup logging for GitHub Actions run"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(current_dir, "logs", "post-activity.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    # Simple logging configuration
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
            content = f.read()
            # Parse JSON
            posts_data = json.loads(content)
        
        # Handle both array format and single object format
        if isinstance(posts_data, dict):
            # Single post object, convert to list
            posts_data = [posts_data]
            logger.info("Converted single post object to list format")
        
        logger.info(f"Successfully loaded {len(posts_data)} posts from {posts_file_path}")
        return posts_data
    except FileNotFoundError:
        logger.error(f"Posts file not found: {posts_file_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from {posts_file_path}: {e}")
        logger.error("Make sure your JSON file doesn't have comments (#) and uses double quotes")
        return []


def should_post_today(post_date_str: str, logger: logging.Logger) -> bool:
    """Check if the post should be published today"""
    try:
        # Parse the post date (expected format: "2024-12-25 09:00")
        post_datetime = datetime.strptime(post_date_str, "%Y-%m-%d %H:%M")
        
        # Make it timezone aware (EST/EDT)
        post_datetime = post_datetime.replace(tzinfo=tz.gettz("US/Eastern"))
        
        # Get current time in EST/EDT
        now_est = datetime.now(tz.gettz("US/Eastern"))
        
        # Check if it's the same day
        return post_datetime.date() == now_est.date()
    except ValueError as e:
        logger.error(f"Error parsing post date '{post_date_str}': {e}")
        logger.error("Date format should be: YYYY-MM-DD HH:MM (e.g., 2026-04-28 08:45)")
        return False


def archive_post(post: Dict, current_dir: str, logger: logging.Logger) -> bool:
    """Move posted content to archive"""
    try:
        archive_dir = os.path.join(current_dir, "data", "processed_posts")
        os.makedirs(archive_dir, exist_ok=True)
        
        # Create archive filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        post_id = post.get('image_path', timestamp).replace('/', '_').replace('.', '_')
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
    description = post.get('description', 'No description')
    image_path = post.get('image_path', '')
    
    logger.info(f"Attempting to post: {description[:50]}...")
    logger.info(f"Image path: {image_path}")
    
    # Log extra data if present
    extra_data = post.get('extra_data', {})
    if extra_data:
        logger.info(f"Extra settings: {extra_data}")
    
    # TODO: Add your actual Instagram posting logic here
    # Example with instagrapi:
    # from instagrapi import Client
    # client = Client()
    # client.login(username, password)
    # 
    # # Check if image exists
    # if os.path.exists(image_path):
    #     client.photo_upload(
    #         image_path, 
    #         caption=description,
    #         extra_data=extra_data
    #     )
    # else:
    #     logger.error(f"Image not found: {image_path}")
    #     return False
    
    # Placeholder success - REPLACE WITH ACTUAL POSTING CODE
    logger.warning("=== POSTING LOGIC NOT IMPLEMENTED ===")
    logger.warning(f"This would post: {description}")
    logger.warning(f"Image: {image_path}")
    logger.warning("Please implement post_to_instagram() function with your actual Instagram API")
    
    # For testing, return True to simulate success
    # Change to False if you want to test failure handling
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
        os.makedirs(os.path.join(current_dir, "assets"), exist_ok=True)
        
        sample_posts = [
            {
                "image_path": "assets/sample_image.png",
                "description": "Sample post - Replace with your content",
                "post_date": datetime.now(tz.gettz("US/Eastern")).strftime("%Y-%m-%d 09:00"),
                "extra_data": {
                    "custom_accessibility_caption": "Sample accessibility caption",
                    "like_and_view_counts_disabled": 0,
                    "disable_comments": 0
                }
            }
        ]
        with open(to_post_path, 'w') as f:
            json.dump(sample_posts, f, indent=2)
        logger.info(f"Created sample posts file at {to_post_path}")
        logger.warning("Please update data/to-post.json with your actual posts")
        logger.warning("Remember: No comments (#) allowed in JSON files!")
    
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
            logger.warning(f"Post missing 'post_date' field: {post.get('description', 'Unknown')}")
            remaining_posts.append(post)
            continue
        
        if should_post_today(post_date, logger):
            posts_to_post.append(post)
            logger.info(f"✓ Post scheduled for today: {post_date}")
        else:
            remaining_posts.append(post)
            logger.debug(f"Post not scheduled for today: {post_date}")
    
    # Post each scheduled item
    successful_posts = []
    failed_posts = []
    
    for post in posts_to_post:
        logger.info(f"--- Processing post scheduled for {post.get('post_date')} ---")
        logger.info(f"Description: {post.get('description', 'No description')[:100]}")
        logger.info(f"Image: {post.get('image_path', 'No image')}")
        
        # Check if image exists (warning only, not fatal)
        image_path = post.get('image_path', '')
        if image_path and os.path.exists(image_path):
            logger.info(f"✓ Image found at {image_path}")
        elif image_path:
            logger.warning(f"⚠ Image not found at {image_path}")
        
        # Attempt to post
        if post_to_instagram(post, logger):
            successful_posts.append(post)
            logger.info(f"✓ Successfully posted: {post.get('description', '')[:50]}")
            # Archive successful post
            archive_post(post, current_dir, logger)
        else:
            failed_posts.append(post)
            logger.error(f"✗ Failed to post: {post.get('description', '')[:50]}")
            remaining_posts.append(post)  # Keep failed posts for retry
    
    # Update the main posts file
    if successful_posts:
        update_posts_file(all_posts, remaining_posts, to_post_path, logger)
    
    # Summary
    logger.info("=" * 60)
    logger.info("POSTING SUMMARY:")
    logger.info(f"  Total posts checked: {len(all_posts)}")
    logger.info(f"  Scheduled for today: {len(posts_to_post)}")
    logger.info(f"  Successfully posted: {len(successful_posts)}")
    logger.info(f"  Failed: {len(failed_posts)}")
    logger.info(f"  Remaining for future: {len(remaining_posts)}")
    logger.info("=" * 60)
    
    if failed_posts:
        logger.warning("Failed posts will be retried tomorrow")
        sys.exit(1)  # Exit with error to flag in GitHub Actions
    else:
        logger.info("All scheduled posts processed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
