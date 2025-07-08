import requests
from bs4 import BeautifulSoup
import csv
import json
import argparse
import os
import re
from datetime import datetime
from urllib.parse import urljoin

# --- Part 1: Scrape Category and Save URLs to CSV ---

def scrape_category_to_csv(base_url, category, csv_name):
    """
    Scrapes a specific category page on the news website to find article URLs
    and saves them to a CSV file.
    """
    category_url = urljoin(base_url, category)
    print(f"[*] Scraping category page: {category_url}")

    try:
        # Using headers to mimic a real browser visit
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(category_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[!] Error fetching category page: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # --- UPDATED SELECTOR ---
    # The old selector 'a[href*="/story/"]' did not work for /culture.
    # The new selector 'a[href*="/article/"]' is more general and works for
    # categories like /culture, /travel, and /worklife.
    article_links = soup.select('a[href*="/article/"]')
    
    if not article_links:
        print(f"[!] No article links found on {category_url}. The website structure may have changed, or the selector needs an update.")
        return

    print(f"[*] Found {len(article_links)} potential article links.")

    with open(csv_name, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['website', 'category', 'article_url'])
        
        seen_urls = set()
        for link in article_links:
            relative_url = link.get('href')
            if relative_url:
                full_url = urljoin(base_url, relative_url)
                if full_url not in seen_urls:
                    writer.writerow([base_url, category, full_url])
                    seen_urls.add(full_url)
    
    print(f"[+] Successfully saved article URLs to {csv_name}")


# --- Part 2: Load CSV and Scrape Metadata to JSON ---

def scrape_article_metadata(article_url):
    """
    Scrapes a single article URL to extract its metadata.
    """
    print(f"    -> Scraping article: {article_url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(article_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"    [!] Failed to fetch article {article_url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # --- UPDATED METADATA SELECTORS ---
    # Selectors have been refined to be more robust for current BBC article layouts.
    
    title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Title not found"
    
    summary_tag = soup.find('meta', {'name': 'description'})
    summary = summary_tag['content'] if summary_tag else "Summary not found"

    # The <time> tag is more reliable without the data-testid
    time_tag = soup.find('time')
    publish_date = time_tag.get_text(strip=True) if time_tag else "Publish date not found"

    image_tag = soup.find('meta', {'property': 'og:image'})
    article_image = image_tag['content'] if image_tag else "Image not found"

    # The main article body is now within <main id="main-content">. We find all <p> tags inside it.
    main_content_area = soup.find('main', {'id': 'main-content'})
    if main_content_area:
        # Find all direct paragraph children of divs within the main content area
        paragraphs = main_content_area.find_all('p', recursive=True)
        article_content = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
    else:
        article_content = "Article content not found."

    # Image credit is often in a span with "Image source" or "Image credit"
    credit_tag = soup.find(string=re.compile(r'Image (source|credit)', re.IGNORECASE))
    image_credit = credit_tag.parent.get_text(strip=True) if credit_tag else "Image credit not found"

    # Tags are under "Related Topics", usually in a following list.
    tags_heading = soup.find('h2', string='Related Topics')
    tags = []
    if tags_heading:
        # Find the list (ul) that comes after the heading
        tags_list = tags_heading.find_next_sibling('ul')
        if tags_list:
            tags = [a.get_text(strip=True) for a in tags_list.find_all('a')]
    
    metadata = {
        'title': title,
        'summary': summary,
        'publish_date': publish_date,
        'article_image': article_image,
        'article_content': article_content,
        'image_credit': image_credit,
        'tags': ", ".join(tags)
    }
    
    return metadata

def process_csv_to_json(csv_name, website_name, category):
    """
    Loads the CSV file, iterates through each URL, scrapes metadata,
    and saves it to a unique JSON file.
    """
    try:
        with open(csv_name, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            articles = list(reader)
    except FileNotFoundError:
        print(f"[!] CSV file not found: {csv_name}")
        return

    print(f"\n[*] Starting to process {len(articles)} articles from {csv_name}")

    output_dir = "json_output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"[*] JSON files will be saved in the '{output_dir}/' directory.")

    for row in articles:
        article_url = row['article_url']
        metadata = scrape_article_metadata(article_url)
        
        if metadata:
            safe_title = re.sub(r'[^\w-]', '_', metadata['title'])[:50]
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            filename = f"{website_name}_{category}_{safe_title}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(metadata, jsonfile, indent=4, ensure_ascii=False)
            
            print(f"    [+] Successfully saved metadata to {filepath}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a news website category, save URLs to CSV, then extract article metadata to JSON.")
    parser.add_argument('--base_url', required=True, help='The base URL of the news website (e.g., "https://www.bbc.com")')
    parser.add_argument('--category', required=True, help='The news category to scrape (e.g., "culture", "worklife", "travel")')
    parser.add_argument('--csv_name', required=True, help='The name for the output CSV file (e.g., "bbc_articles.csv")')
    
    args = parser.parse_args()

    scrape_category_to_csv(args.base_url, args.category, args.csv_name)
    
    website_name = args.base_url.replace('https://', '').replace('www.', '').split('/')[0].replace('.', '_')
    process_csv_to_json(args.csv_name, website_name, args.category)

    print("[*] All tasks completed.")