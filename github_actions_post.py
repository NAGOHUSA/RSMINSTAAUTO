#!/usr/bin/env python3
"""
GitHub Actions Instagram Auto-Poster
Uses Username/Password authentication with proper CSRF handling
"""

import json
import logging
import os
import shutil
import sys
import time
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
    
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %message)s')
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
        
        if isinstance(posts_data, dict):
            posts_data = [posts_data]
        
        logger.info(f"Loaded {len(posts_data)} posts")
        return posts_data
    except Exception as e:
        logger.error(f"Error loading posts: {e}")
        return []


def should_post_today(post_date_str: str, logger: logging.Logger) -> bool:
    """Check if post should be published today"""
    try:
        post_datetime = datetime.strptime(post_date_str, "%Y-%m-%d %H:%M")
        post_datetime = post_datetime.replace(tzinfo=tz.gettz("US/Eastern"))
        now_est = datetime.now(tz.gettz("US/Eastern"))
        return post_datetime.date() == now_est.date()
    except Exception as e:
        logger.error(f"Error parsing date: {e}")
        return False


def archive_post(post: Dict, current_dir: str, logger: logging.Logger) -> bool:
    """Archive posted content"""
    try:
        archive_dir = os.path.join(current_dir, "data", "processed_posts")
        os.makedirs(archive_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = os.path.basename(post.get('image_path', 'unknown')).replace('.', '_')
        archive_path = os.path.join(archive_dir, f"posted_{image_name}_{timestamp}.json")
        
        with open(archive_path, 'w') as f:
            json.dump(post, f, indent=2)
        
        logger.info(f"Archived to {archive_path}")
        return True
    except Exception as e:
        logger.error(f"Archive failed: {e}")
        return False


def post_to_instagram(post: Dict, logger: logging.Logger) -> bool:
    """
    Post to Instagram using username/password authentication
    """
    try:
        from instagrapi import Client
        
        description = post.get('description', '')
        image_path = post.get('image_path', '')
        
        # Get credentials from environment
        username = os.environ.get('INSTAGRAM_USERNAME')
        password = os.environ.get('INSTAGRAM_PASSWORD')
        
        if not username or not password:
            logger.error("INSTAGRAM_USERNAME or PASSWORD not set")
            return False
        
        # Check if image exists
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_image_path = os.path.join(current_dir, image_path)
        
        if not os.path.exists(full_image_path):
            logger.error(f"Image not found: {full_image_path}")
            return False
        
        logger.info("Initializing Instagram client...")
        client = Client()
        
        # Set delay between requests to avoid rate limiting
        client.delay_range = [3, 6]
        
        logger.info(f"Logging in as {username}...")
        
        # Login with username/password
        client.login(username, password)
        
        logger.info("✅ Successfully logged in")
        
        # Get user info
        user_id = client.user_id
        logger.info(f"User ID: {user_id}")
        
        # Wait a moment before upload
        time.sleep(3)
        
        # Upload photo
        logger.info(f"Uploading: {full_image_path}")
        logger.info(f"Caption: {description[:100]}...")
        
        result = client.photo_upload(
            path=full_image_path,
            caption=description
        )
        
        logger.info("=" * 40)
        logger.info("✅ SUCCESS! Posted to Instagram!")
        logger.info(f"Post URL: https://www.instagram.com/p/{result.code}/")
        logger.info("=" * 40)
        
        # Logout
        client.logout()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to post: {e}")
        
        # Try alternative method with more settings
        try:
            logger.info("Trying alternative method...")
            from instagrapi import Client
            
            client = Client()
            
            # Set custom settings
            client.set_settings({
                "user_agent": "Instagram 269.0.0.18.71 Android",
                "csrf_token": None
            })
            
            # Set device
            client.set_device({
                "app_version": "269.0.0.18.71",
                "android_version": 26,
                "android_release": "8.0.0",
                "manufacturer": "samsung",
                "device": "SM-G960F",
                "model": "SM-G960F"
            })
            
            client.login(username, password)
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            full_image_path = os.path.join(current_dir, post.get('image_path', ''))
            
            result = client.photo_upload(
                path=full_image_path,
                caption=post.get('description', '')
            )
            
            logger.info(f"✅ Alternative method succeeded!")
            logger.info(f"Post URL: https://www.instagram.com/p/{result.code}/")
            return True
            
        except Exception as e2:
            logger.error(f"Alternative method failed: {e2}")
            return False


def main() -> None:
    """Main function"""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Instagram Auto-Poster Starting")
    logger.info(f"Run time: {datetime.now(tz.gettz('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    to_post_path = os.path.join(current_dir, "data", "to-post.json")
    
    if not os.path.exists(to_post_path):
        logger.error(f"Posts file not found: {to_post_path}")
        return
    
    # Check credentials
    username = os.environ.get('INSTAGRAM_USERNAME')
    password = os.environ.get('INSTAGRAM_PASSWORD')
    
    if not username or not password:
        logger.error("=" * 60)
        logger.error("Instagram credentials not set in GitHub Secrets!")
        logger.error("Please add:")
        logger.error("  - INSTAGRAM_USERNAME")
        logger.error("  - INSTAGRAM_PASSWORD")
        logger.error("=" * 60)
        return
    
    # Load posts
    all_posts = load_posts(to_post_path, logger)
    
    if not all_posts:
        logger.info("No posts to process")
        return
    
    # Find today's posts
    posts_to_post = []
    remaining_posts = []
    
    for post in all_posts:
        post_date = post.get('post_date')
        if not post_date:
            remaining_posts.append(post)
            continue
        
        if should_post_today(post_date, logger):
            posts_to_post.append(post)
            logger.info(f"📅 Posting today: {post_date}")
        else:
            remaining_posts.append(post)
    
    if not posts_to_post:
        logger.info("No posts scheduled for today")
        return
    
    # Process posts
    successful_posts = []
    failed_posts = []
    
    for post in posts_to_post:
        logger.info("-" * 40)
        logger.info(f"Post: {post.get('description', '')[:50]}...")
        
        if post_to_instagram(post, logger):
            successful_posts.append(post)
            archive_post(post, current_dir, logger)
        else:
            failed_posts.append(post)
            remaining_posts.append(post)
    
    # Update file
    if successful_posts:
        backup_path = to_post_path + ".backup"
        shutil.copy(to_post_path, backup_path)
        
        with open(to_post_path, 'w') as f:
            json.dump(remaining_posts, f, indent=2)
        
        logger.info(f"Updated posts file, {len(remaining_posts)} remaining")
    
    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info(f"Total: {len(all_posts)}")
    logger.info(f"Today: {len(posts_to_post)}")
    logger.info(f"✅ Success: {len(successful_posts)}")
    logger.info(f"❌ Failed: {len(failed_posts)}")
    logger.info("=" * 60)
    
    if successful_posts:
        logger.info("🎉 Check your Instagram feed!")
    
    sys.exit(1 if failed_posts else 0)


if __name__ == "__main__":
    main()
