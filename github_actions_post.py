#!/usr/bin/env python3
"""
GitHub Actions Instagram Auto-Poster
Uses Session ID authentication to bypass IP blocking
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime
from typing import Dict, List

from dateutil import tz


def setup_logging() -> logging.Logger:
    """Setup logging for GitHub Actions run"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(current_dir, "logs", "post-activity.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    logger = logging.getLogger("instagram_auto_post")
    logger.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    
    # Console handler for GitHub Actions output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
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
            posts_data = json.loads(content)
        
        # Handle both array format and single object format
        if isinstance(posts_data, dict):
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
        post_datetime = datetime.strptime(post_date_str, "%Y-%m-%d %H:%M")
        post_datetime = post_datetime.replace(tzinfo=tz.gettz("US/Eastern"))
        now_est = datetime.now(tz.gettz("US/Eastern"))
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
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = os.path.basename(post.get('image_path', 'unknown')).replace('.', '_')
        archive_path = os.path.join(archive_dir, f"posted_{image_name}_{timestamp}.json")
        
        with open(archive_path, 'w') as f:
            json.dump(post, f, default=str, indent=2)
        
        logger.info(f"Archived post to {archive_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to archive post: {e}")
        return False


def post_to_instagram(post: Dict, logger: logging.Logger) -> bool:
    """
    Post to Instagram using Session ID authentication
    This bypasses IP blocking issues common with GitHub Actions
    """
    try:
        from instagrapi import Client
        
        description = post.get('description', '')
        image_path = post.get('image_path', '')
        extra_data = post.get('extra_data', {})
        
        # Get session ID from environment variable
        session_id = os.environ.get('INSTAGRAM_SESSION_ID')
        
        if not session_id:
            logger.error("INSTAGRAM_SESSION_ID not found in environment variables")
            logger.error("Please add INSTAGRAM_SESSION_ID to GitHub Secrets")
            logger.error("How to get session ID: https://github.com/instaloader/instaloader#how-to-get-the-sessionid-cookie")
            return False
        
        # Check if image exists
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_image_path = os.path.join(current_dir, image_path)
        
        if not os.path.exists(full_image_path):
            logger.error(f"Image not found: {full_image_path}")
            return False
        
        logger.info("Initializing Instagram client...")
        client = Client()
        
        # Set user agent to look like a real browser
        client.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Set device settings to look like a real phone
        client.set_device({
            "app_version": "269.0.0.18.71",
            "android_version": 26,
            "android_release": "8.0.0",
            "manufacturer": "OnePlus",
            "device": "ONEPLUS A3010",
            "model": "ONEPLUS A3010",
            "cpu": "qcom"
        })
        
        logger.info("Logging in with Session ID...")
        client.login_by_sessionid(session_id)
        logger.info("✅ Successfully logged in with Session ID")
        
        # Get user info to confirm login
        user_id = client.user_id
        logger.info(f"Logged in as user ID: {user_id}")
        
        # Prepare extra parameters
        extra_params = {}
        if extra_data.get('custom_accessibility_caption'):
            extra_params['custom_accessibility_caption'] = extra_data['custom_accessibility_caption']
            logger.info(f"Using accessibility caption: {extra_data['custom_accessibility_caption']}")
        
        # Upload photo
        logger.info(f"Uploading photo: {full_image_path}")
        logger.info(f"Caption: {description[:100]}{'...' if len(description) > 100 else ''}")
        
        result = client.photo_upload(
            path=full_image_path,
            caption=description,
            **extra_params
        )
        
        logger.info(f"✅ Successfully posted to Instagram!")
        logger.info(f"Post ID: {result.id}")
        logger.info(f"Post URL: https://www.instagram.com/p/{result.code}/")
        
        # Handle comment disabling if requested
        if extra_data.get('disable_comments', 0) == 1:
            logger.info("Disabling comments on post")
            client.comment_disabled(result.id, True)
        
        if extra_data.get('like_and_view_counts_disabled', 0) == 1:
            logger.info("Disabling like/view counts on post")
            client.disable_like_and_view_counts(result.id, True)
        
        # Logout
        client.logout()
        logger.info("Logged out successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to post to Instagram: {e}")
        logger.error("Troubleshooting tips:")
        logger.error("1. Make sure your Session ID is valid and not expired")
        logger.error("2. Try logging into Instagram manually in a browser to refresh the session")
        logger.error("3. Your Session ID might need to be renewed (they expire after a few weeks)")
        return False


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
    """Main function for GitHub Actions Instagram posting"""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Instagram Auto-Poster Starting (Session ID Mode)")
    logger.info(f"Run time: {datetime.now(tz.gettz('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    to_post_path = os.path.join(current_dir, "data", "to-post.json")
    
    # Check if posts file exists
    if not os.path.exists(to_post_path):
        logger.error(f"No posts file found at {to_post_path}")
        logger.info("Creating sample posts file for testing...")
        
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
        logger.warning("⚠ Please update data/to-post.json with your actual posts")
        logger.warning("⚠ Remember: No comments (#) allowed in JSON files!")
        return
    
    # Check if Session ID is set
    session_id = os.environ.get('INSTAGRAM_SESSION_ID')
    if not session_id:
        logger.error("=" * 60)
        logger.error("INSTAGRAM_SESSION_ID is not set in GitHub Secrets!")
        logger.error("")
        logger.error("To fix this:")
        logger.error("1. Go to your repository Settings → Secrets and variables → Actions")
        logger.error("2. Click 'New repository secret'")
        logger.error("3. Name: INSTAGRAM_SESSION_ID")
        logger.error("4. Value: Your Instagram session ID cookie")
        logger.error("")
        logger.error("How to get your Session ID:")
        logger.error("1. Log into Instagram in Chrome/Firefox")
        logger.error("2. Open Developer Tools (F12)")
        logger.error("3. Go to Application/Storage tab → Cookies → https://www.instagram.com")
        logger.error("4. Find the cookie named 'sessionid' and copy its value")
        logger.error("=" * 60)
        return
    
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
            logger.info(f"📅 Post scheduled for today: {post_date}")
        else:
            remaining_posts.append(post)
            logger.debug(f"Post not scheduled for today: {post_date}")
    
    if not posts_to_post:
        logger.info("No posts scheduled for today")
        return
    
    # Post each scheduled item
    successful_posts = []
    failed_posts = []
    
    for post in posts_to_post:
        logger.info("-" * 40)
        logger.info(f"Processing post scheduled for {post.get('post_date')}")
        logger.info(f"Description: {post.get('description', 'No description')[:100]}")
        logger.info(f"Image: {post.get('image_path', 'No image')}")
        
        # Attempt to post
        if post_to_instagram(post, logger):
            successful_posts.append(post)
            archive_post(post, current_dir, logger)
        else:
            failed_posts.append(post)
            logger.error(f"Failed to post, will retry tomorrow")
            remaining_posts.append(post)
    
    # Update the main posts file
    if successful_posts:
        update_posts_file(all_posts, remaining_posts, to_post_path, logger)
    
    # Summary
    logger.info("=" * 60)
    logger.info("POSTING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total posts checked: {len(all_posts)}")
    logger.info(f"Scheduled for today: {len(posts_to_post)}")
    logger.info(f"✅ Successfully posted: {len(successful_posts)}")
    logger.info(f"❌ Failed: {len(failed_posts)}")
    logger.info(f"Remaining for future: {len(remaining_posts)}")
    logger.info("=" * 60)
    
    if successful_posts:
        logger.info("🎉 Success! Check your Instagram feed for the new post!")
    
    if failed_posts:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
