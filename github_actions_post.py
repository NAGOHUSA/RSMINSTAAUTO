#!/usr/bin/env python3
"""
GitHub Actions Instagram Auto-Poster
Uses Session ID and CSRF token for authentication
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
    Post to Instagram using Session ID and CSRF token
    """
    try:
        from instagrapi import Client
        
        description = post.get('description', '')
        image_path = post.get('image_path', '')
        
        # Get session ID from environment variable
        session_id = os.environ.get('INSTAGRAM_SESSION_ID')
        
        if not session_id:
            logger.error("INSTAGRAM_SESSION_ID not found in environment variables")
            return False
        
        # Check if image exists
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_image_path = os.path.join(current_dir, image_path)
        
        if not os.path.exists(full_image_path):
            logger.error(f"Image not found: {full_image_path}")
            return False
        
        logger.info("Initializing Instagram client...")
        client = Client()
        
        # Set up device and user agent properly
        client.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Set device settings
        client.set_device({
            "app_version": "269.0.0.18.71",
            "android_version": 26,
            "android_release": "8.0.0",
            "manufacturer": "OnePlus",
            "device": "ONEPLUS A3010",
            "model": "ONEPLUS A3010",
            "cpu": "qcom"
        })
        
        # Login with session ID
        logger.info("Logging in with Session ID...")
        client.login_by_sessionid(session_id)
        logger.info("✅ Successfully logged in with Session ID")
        
        # Get user info
        user_id = client.user_id
        logger.info(f"Logged in as user ID: {user_id}")
        
        # Small delay before upload
        import time
        time.sleep(2)
        
        # Upload photo
        logger.info(f"Uploading photo: {full_image_path}")
        logger.info(f"Caption: {description[:100]}...")
        
        result = client.photo_upload(
            path=full_image_path,
            caption=description,
            extra_data={
                "like_and_view_counts_disabled": 0,
                "disable_comments": 0
            }
        )
        
        logger.info(f"✅ SUCCESS! Posted to Instagram!")
        logger.info(f"Post ID: {result.id}")
        logger.info(f"Post URL: https://www.instagram.com/p/{result.code}/")
        
        # Logout
        client.logout()
        logger.info("Logged out successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to post to Instagram: {e}")
        logger.error("Trying alternative method...")
        
        # Alternative method using settings
        try:
            from instagrapi import Client
            
            client = Client()
            session_id = os.environ.get('INSTAGRAM_SESSION_ID')
            
            # Set settings before login
            client.set_settings({
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "csrf_token": session_id.split('%')[0] if '%' in session_id else session_id
            })
            
            client.login_by_sessionid(session_id)
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            full_image_path = os.path.join(current_dir, post.get('image_path', ''))
            
            result = client.photo_upload(
                path=full_image_path,
                caption=post.get('description', '')
            )
            
            logger.info(f"✅ SUCCESS with alternative method!")
            logger.info(f"Post URL: https://www.instagram.com/p/{result.code}/")
            return True
            
        except Exception as e2:
            logger.error(f"Alternative method also failed: {e2}")
            return False


def update_posts_file(all_posts: List[Dict], remaining_posts: List[Dict], 
                     to_post_path: str, logger: logging.Logger) -> None:
    """Update the main posts file by removing posted items"""
    try:
        backup_path = to_post_path + ".backup"
        shutil.copy(to_post_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        
        with open(to_post_path, 'w') as f:
            json.dump(remaining_posts, f, indent=2)
        
        logger.info(f"Updated {to_post_path} with {len(remaining_posts)} remaining posts")
    except Exception as e:
        logger.error(f"Failed to update posts file: {e}")


def main() -> None:
    """Main function for GitHub Actions Instagram posting"""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Instagram Auto-Poster Starting")
    logger.info(f"Run time: {datetime.now(tz.gettz('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    to_post_path = os.path.join(current_dir, "data", "to-post.json")
    
    # Check if posts file exists
    if not os.path.exists(to_post_path):
        logger.error(f"No posts file found at {to_post_path}")
        return
    
    # Check if Session ID is set
    session_id = os.environ.get('INSTAGRAM_SESSION_ID')
    if not session_id:
        logger.error("=" * 60)
        logger.error("INSTAGRAM_SESSION_ID is not set in GitHub Secrets!")
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
            remaining_posts.append(post)
            continue
        
        if should_post_today(post_date, logger):
            posts_to_post.append(post)
            logger.info(f"📅 Post scheduled for today: {post_date}")
        else:
            remaining_posts.append(post)
    
    if not posts_to_post:
        logger.info("No posts scheduled for today")
        return
    
    # Post each scheduled item
    successful_posts = []
    failed_posts = []
    
    for post in posts_to_post:
        logger.info("-" * 40)
        logger.info(f"Processing post for {post.get('post_date')}")
        logger.info(f"Description: {post.get('description', '')[:100]}")
        
        if post_to_instagram(post, logger):
            successful_posts.append(post)
            archive_post(post, current_dir, logger)
        else:
            failed_posts.append(post)
            remaining_posts.append(post)
    
    # Update the main posts file
    if successful_posts:
        update_posts_file(all_posts, remaining_posts, to_post_path, logger)
    
    # Summary
    logger.info("=" * 60)
    logger.info("POSTING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total posts: {len(all_posts)}")
    logger.info(f"Scheduled today: {len(posts_to_post)}")
    logger.info(f"✅ Successful: {len(successful_posts)}")
    logger.info(f"❌ Failed: {len(failed_posts)}")
    logger.info("=" * 60)
    
    if failed_posts:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
